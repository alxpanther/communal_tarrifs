"""Gemini, through Google's own SDK.

The only provider that takes a PDF as bytes and reads it itself — a scan with no text layer
included — and the only one with web search built in, which Ukraine's cross-check uses.
"""

import logging
import os
import re

from common.llm.base import TEMPERATURE, Extractor, LLMUnavailable, parse_json_response

logger = logging.getLogger(__name__)

DEFAULT_KEY_ENV = "GEMINI_API_KEY"

# The response is asked for as JSON, so the model must not wrap it in prose.
JSON_MIME = "application/json"

# Only a plain `gemini-<version>-flash` qualifies for auto-selection. The listing is full of
# relatives that share the name and cannot do this job — image, tts, audio, live, lite and
# preview variants — and picking one of those would break extraction silently.
PLAIN_FLASH = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash$", re.IGNORECASE)


def _client(key_env: str = DEFAULT_KEY_ENV):
    api_key = os.getenv(key_env)
    if not api_key:
        raise LLMUnavailable(f"{key_env} is not set")
    from google import genai
    return genai.Client(api_key=api_key)


def _version_of(name: str) -> float:
    match = PLAIN_FLASH.match(name or "")
    return float(match.group(1)) if match else 0.0


def _resolve(configured: str, auto_select: bool, key_env: str = DEFAULT_KEY_ENV) -> str:
    """The model to use: env override, else the newest plain flash, else config.

    The configured model is the floor: auto-selection only ever replaces it with a newer
    model of the same family. Listing models costs nothing.
    """
    if not configured:
        raise LLMUnavailable("no Gemini model is configured")

    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        logger.info(f"Using GEMINI_MODEL from the environment: {env_model}")
        return env_model
    if not auto_select:
        return configured

    try:
        # The client has to outlive the listing: the SDK pages lazily, and a client left to
        # the garbage collector closes mid-iteration.
        client = _client(key_env)
        names = [str(getattr(m, "name", m)).replace("models/", "") for m in client.models.list()]
    except Exception as e:
        logger.warning(f"Could not list models ({e}), falling back to '{configured}'")
        return configured

    family = [name for name in names if PLAIN_FLASH.match(name)]
    if not family:
        logger.warning(f"No plain flash model in the listing, keeping '{configured}'")
        return configured
    newest = max(family, key=_version_of)
    if _version_of(newest) < _version_of(configured):
        return configured
    if newest != configured:
        logger.info(f"Auto-selected '{newest}' over the configured '{configured}'")
    return newest


def resolve_model(config: dict) -> str:
    """Model name for a country config, old layout (`settings.gemini_model`) or new
    (`settings.llm`). Kept for Ukraine, whose fetcher still calls Gemini directly."""
    settings = config.get("settings", {}) or {}
    llm = settings.get("llm") or {}
    configured = llm.get("model") or settings.get("gemini_model")
    auto = llm.get("auto_select_latest_model", settings.get("auto_select_latest_model", True))
    return _resolve(configured, auto, llm.get("api_key_env") or DEFAULT_KEY_ENV)


class GeminiExtractor(Extractor):
    provider = "gemini"

    def __init__(self, model: str, key_env: str = DEFAULT_KEY_ENV, notifier=None):
        super().__init__(model, notifier)
        self.key_env = key_env

    def _parts(self, parts: list) -> list:
        from google.genai import types
        prepared = []
        for part in parts:
            if isinstance(part, tuple):
                mime, data = part
                prepared.append(types.Part.from_bytes(data=data, mime_type=mime))
            else:
                prepared.append(str(part))
        return prepared

    def _generate(self, contents: list, config, what: str, model: str = "") -> dict:
        model = model or self.model
        try:
            # The client has to be held in a name of its own: the SDK closes its transport
            # when the Client object is collected, and a temporary is collected the moment
            # `.models` has been read — the request then fails with "client has been closed".
            client = _client(self.key_env)
            response = client.models.generate_content(
                model=model, contents=contents, config=config)
        except LLMUnavailable as e:
            logger.warning(f"{what} skipped: {e}")
            return {}
        except Exception as e:
            self._report_failure(what, e)
            return {}

        meta = getattr(response, "usage_metadata", None)
        self._count(model, getattr(meta, "prompt_token_count", 0),
                    getattr(meta, "candidates_token_count", 0))
        text = getattr(response, "text", None)
        if not text:
            logger.warning(f"{self.name}: empty answer")
            return {}
        return parse_json_response(text)

    def extract(self, parts: list, instruction: str, options: dict = None) -> dict:
        from google.genai import types
        return self._generate(
            self._parts(parts) + [instruction],
            types.GenerateContentConfig(response_mime_type=JSON_MIME, temperature=TEMPERATURE),
            "Ошибка вызова модели",
            (options or {}).get("model", ""),
        )

    def search(self, query: str, instruction: str) -> dict:
        from google.genai import types
        return self._generate(
            [query, instruction],
            types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())], temperature=TEMPERATURE),
            "Ошибка сверки через поиск",
        )


def build(settings: dict, notifier=None) -> GeminiExtractor:
    key_env = settings.get("api_key_env") or DEFAULT_KEY_ENV
    model = _resolve(settings.get("model"), settings.get("auto_select_latest_model", True), key_env)
    return GeminiExtractor(model, key_env, notifier)
