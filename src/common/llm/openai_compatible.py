"""Any chat-completions API that speaks the OpenAI wire format.

Qwen on Alibaba Cloud Model Studio today; OpenRouter, GLM or a local server the day a
country is moved to one — only `settings.llm` in that country's config changes.

These APIs take text and images, not PDFs. A PDF with a text layer is sent as its text; a
scan, or a PDF whose source sets `pdf_as_images`, is rendered to page images and sent to the
vision model instead. HTTP is spoken
directly: one POST is all extraction needs, and `requests` is already a dependency.
"""

import base64
import logging
import os

import requests

from common import pdf
from common.llm.base import TEMPERATURE, Extractor, LLMUnavailable, parse_json_response

logger = logging.getLogger(__name__)


class OpenAICompatibleExtractor(Extractor):
    provider = "openai_compatible"

    def __init__(self, model: str, base_url: str, api_key: str, timeout: int,
                 vision_model: str = "", json_mode: bool = True, extra_params: dict = None,
                 notifier=None):
        super().__init__(model, notifier)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.vision_model = vision_model
        self.json_mode = json_mode
        self.extra_params = dict(extra_params or {})

    def _content(self, parts: list, instruction: str, pdf_as_images: bool = False) -> tuple:
        """Flattens the documents into one message. Returns (content, has_images).

        Every document gets a numbered header, because a source hint in config may refer to
        "the second document" — the order the URLs are listed in.
        """
        texts, images = [], []
        for number, part in enumerate(parts, start=1):
            if not isinstance(part, tuple):
                texts.append(f"=== Документ {number} ===\n{part}")
                continue
            mime, data = part
            if mime == "application/pdf":
                text = "" if pdf_as_images else pdf.text_of(data)
                if text and not pdf.is_scan(text):
                    texts.append(f"=== Документ {number} ===\n{text}")
                    continue
                pages = pdf.page_images(data)
                texts.append(f"=== Документ {number}: PDF, {len(pages)} стр. — "
                             f"изображения страниц приложены ===")
                images.extend(("image/png", page) for page in pages)
            else:
                texts.append(f"=== Документ {number}: изображение приложено ===")
                images.append((mime, data))

        prompt = "\n\n".join(texts + [instruction])
        if not images:
            return prompt, False
        blocks = [{"type": "text", "text": prompt}]
        for mime, data in images:
            encoded = base64.b64encode(data).decode("ascii")
            blocks.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}})
        return blocks, True

    def extract(self, parts: list, instruction: str, options: dict = None) -> dict:
        options = options or {}
        content, has_images = self._content(parts, instruction, bool(options.get("pdf_as_images")))
        if has_images and not self.vision_model:
            self._report_failure("Источник — скан, а settings.llm.vision_model не задан",
                                 "документ не прочитан")
            return {}

        # A scan always goes to the vision model; a per-source model is for text.
        model = self.vision_model if has_images else (options.get("model") or self.model)
        json_mode = options.get("json_mode", self.json_mode)
        body = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": TEMPERATURE,
        }
        # JSON mode is a text-model feature; for a vision request the answer is parsed from
        # the text, which parse_json_response tolerates.
        if json_mode and not has_images:
            body["response_format"] = {"type": "json_object"}
        body.update(self.extra_params)
        body.update(options.get("extra_params") or {})

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
                timeout=self.timeout,
            )
        except Exception as e:
            self._report_failure("Ошибка вызова модели", e)
            return {}
        if response.status_code != 200:
            self._report_failure("Ошибка вызова модели",
                                 f"HTTP {response.status_code}: {response.text[:300]}")
            return {}

        payload = response.json()
        usage = payload.get("usage") or {}
        self._count(model, usage.get("prompt_tokens"), usage.get("completion_tokens"))
        choices = payload.get("choices") or []
        text = (choices[0].get("message") or {}).get("content") if choices else None
        if not text:
            logger.warning(f"{self.provider}:{model}: empty answer")
            return {}
        return parse_json_response(text)


def build(settings: dict, notifier=None) -> OpenAICompatibleExtractor:
    """Builds the extractor from `settings.llm`. Every value comes from config or env.

    The endpoint may be named by an env variable (`base_url_env`) so that an account-specific
    address stays out of a public repository; `base_url` is the fallback.
    """
    key_env = settings.get("api_key_env")
    api_key = os.getenv(key_env or "")
    if not api_key:
        raise LLMUnavailable(f"{key_env or 'settings.llm.api_key_env'} is not set")

    base_url = os.getenv(settings.get("base_url_env") or "") or settings.get("base_url") or ""
    for field, value in (("base_url", base_url), ("model", settings.get("model")),
                         ("timeout_seconds", settings.get("timeout_seconds"))):
        if not value:
            raise LLMUnavailable(f"settings.llm.{field} is missing")

    return OpenAICompatibleExtractor(
        model=settings["model"],
        base_url=base_url,
        api_key=api_key,
        timeout=int(settings["timeout_seconds"]),
        vision_model=settings.get("vision_model") or "",
        json_mode=settings.get("json_mode", True),
        extra_params=settings.get("extra_params"),
        notifier=notifier,
    )
