"""Access to the extraction model, shared by every country that reads a live source.

Kept apart from any one country so that a change of model, of the way a document is
handed over, or of how a refusal is reported, happens once rather than per country.

Nothing here decides *what* to extract: callers pass the document and the instruction.
No model name, key or timeout is written in this file — they come from config and env.
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# The response is asked for as JSON, so the model must not wrap it in prose.
JSON_MIME = "application/json"

# Extraction must be reproducible: the same page has to give the same numbers on every
# run, otherwise a re-run silently rewrites published tariffs.
TEMPERATURE = 0.0


class LLMUnavailable(Exception):
    """No API key, or the model could not be reached. The caller keeps previous data."""


def _client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMUnavailable("GEMINI_API_KEY is not set")
    from google import genai
    return genai.Client(api_key=api_key)


def parse_json_response(raw_text: str) -> dict:
    """Reads the JSON out of a model answer, tolerating a ```json fence around it."""
    if not raw_text or not isinstance(raw_text, str):
        return {}
    cleaned = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"Could not parse JSON from the model answer ({e}): {cleaned[:200]}")
        return {}


def resolve_model(config: dict) -> str:
    """The model to extract with: env override, else the newest Flash, else config.

    `settings.gemini_model` in config/<cc>/sources.json is the floor: auto-selection only
    ever replaces it with a newer model of the same family.
    """
    settings = config.get("settings", {}) or {}
    configured = settings.get("gemini_model")
    if not configured:
        raise LLMUnavailable("settings.gemini_model is missing from the country config")

    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        logger.info(f"Using GEMINI_MODEL from the environment: {env_model}")
        return env_model

    if not settings.get("auto_select_latest_model", True):
        return configured

    try:
        # The client has to outlive the listing: the SDK pages lazily, and a client left
        # to the garbage collector closes mid-iteration.
        client = _client()
        models = list(client.models.list())
    except Exception as e:
        logger.warning(f"Could not list models ({e}), falling back to '{configured}'")
        return configured

    # Only a plain `gemini-<version>-flash` qualifies. The listing is full of relatives
    # that share the name and cannot do this job — image, tts, audio, live, lite and
    # preview variants — and picking one of those would break extraction silently.
    plain_flash = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash$", re.IGNORECASE)

    def version_of(name: str) -> float:
        match = plain_flash.match(name)
        return float(match.group(1)) if match else 0.0

    family = [str(getattr(m, "name", m)).replace("models/", "") for m in models]
    family = [name for name in family if plain_flash.match(name)]
    if not family:
        logger.warning(f"No plain flash model in the listing, keeping '{configured}'")
        return configured

    newest = max(family, key=version_of)
    if version_of(newest) < version_of(configured):
        return configured
    if newest != configured:
        logger.info(f"Auto-selected '{newest}' over the configured '{configured}'")
    return newest


def _content_parts(parts: list) -> list:
    """Turns the caller's parts into what the SDK expects.

    A part is either a string, or a (mime_type, bytes) pair — that pair is how a PDF
    reaches the model, including a scanned one with no text layer.
    """
    from google.genai import types
    prepared = []
    for part in parts:
        if isinstance(part, tuple):
            mime, data = part
            prepared.append(types.Part.from_bytes(data=data, mime_type=mime))
        else:
            prepared.append(str(part))
    return prepared


def extract(parts: list, instruction: str, model: str, notifier=None) -> dict:
    """Reads structured data out of the given documents. Returns {} on any failure.

    An empty answer is never an error the caller may ignore: it means "nothing was
    extracted", and every caller must then keep the previously published values.
    """
    from google.genai import types
    try:
        client = _client()
    except LLMUnavailable as e:
        logger.warning(f"Extraction skipped: {e}")
        return {}

    try:
        response = client.models.generate_content(
            model=model,
            contents=_content_parts(parts) + [instruction],
            config=types.GenerateContentConfig(
                response_mime_type=JSON_MIME,
                temperature=TEMPERATURE,
            ),
        )
    except Exception as e:
        message = f"❌ <b>Ошибка вызова модели <code>{model}</code>:</b>\n<code>{e}</code>"
        logger.error(message)
        if notifier:
            notifier.send_message(message, parse_mode="HTML")
        return {}

    text = getattr(response, "text", None)
    if not text:
        logger.warning("The model returned an empty answer")
        return {}
    return parse_json_response(text)


def search(query: str, instruction: str, model: str, notifier=None) -> dict:
    """Asks the model to look the tariff up on the open web. Advisory only.

    Used to cross-check what was scraped; it must never write a value into the file,
    because a search answer cannot be traced back to a document the way a source page can.
    """
    from google.genai import types
    try:
        client = _client()
    except LLMUnavailable as e:
        logger.warning(f"Cross-check skipped: {e}")
        return {}

    try:
        response = client.models.generate_content(
            model=model,
            contents=[query, instruction],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=TEMPERATURE,
            ),
        )
    except Exception as e:
        message = f"❌ <b>Ошибка сверки через поиск (<code>{model}</code>):</b>\n<code>{e}</code>"
        logger.error(message)
        if notifier:
            notifier.send_message(message, parse_mode="HTML")
        return {}

    text = getattr(response, "text", None)
    if not text:
        return {}
    return parse_json_response(text)
