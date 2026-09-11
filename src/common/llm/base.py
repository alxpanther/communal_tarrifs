"""What every extraction provider has in common.

A provider is one way of asking a model to read a document: Gemini through its own SDK, or
any API that speaks the OpenAI chat-completions format. The pipeline only ever talks to an
`Extractor` and never learns which provider is behind it, so a country moves to another
provider by editing `settings.llm` in its config and nothing else.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# Extraction must be reproducible: the same page has to give the same numbers on every run,
# otherwise a re-run silently rewrites published tariffs.
TEMPERATURE = 0.0


class LLMUnavailable(Exception):
    """No key, no model or no endpoint configured. The country keeps its previous file."""


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
    except Exception:
        pass
    # Without JSON mode — a vision request, or a model reasoning before it answers — the
    # object can arrive wrapped in a sentence. The outermost braces are the answer.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(cleaned[start:end + 1])
        except Exception:
            pass
    logger.warning(f"Could not parse JSON from the model answer: {cleaned[:200]}")
    return {}


class Extractor:
    """One configured model of one provider.

    Every call is paid for, so an extractor also keeps count of what it spent: the run log
    and the single-city tool print the totals, which is how a costly source gets noticed.
    """

    provider = ""

    def __init__(self, model: str, notifier=None):
        self.model = model
        self.notifier = notifier
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        # A provider may answer with more than one model — a vision model for scans — and the
        # bill differs per model, so the totals say which ones were actually used.
        self.models_used = []

    @property
    def name(self) -> str:
        return f"{self.provider}:{self.model}"

    def extract(self, parts: list, instruction: str, options: dict = None) -> dict:
        """Reads structured data out of the documents. Returns {} on any failure.

        A part is text, or a (mime_type, bytes) pair for a PDF or an image. An empty answer
        means "nothing was extracted", and the caller must keep the published values.

        `options` override `settings.llm` for this one call — `model`, `json_mode`,
        `extra_params` — for a source too dense for the country's default model. A provider
        ignores the options it has no use for.
        """
        raise NotImplementedError

    def search(self, query: str, instruction: str) -> dict:
        """Looks a tariff up on the open web. Advisory only, never written to the file."""
        logger.info(f"{self.name}: web search is not supported by this provider, skipped")
        return {}

    def _count(self, model: str, input_tokens, output_tokens):
        if model not in self.models_used:
            self.models_used.append(model)
        self.usage["calls"] += 1
        self.usage["input_tokens"] += int(input_tokens or 0)
        self.usage["output_tokens"] += int(output_tokens or 0)
        logger.info(f"{self.provider}:{model}: {input_tokens} tokens in, {output_tokens} out")

    def usage_line(self) -> str:
        u = self.usage
        models = " + ".join(self.models_used) or self.model
        return (f"{self.provider}:{models}: {u['calls']} calls, {u['input_tokens']} tokens in, "
                f"{u['output_tokens']} tokens out")

    def _report_failure(self, what: str, error):
        message = f"❌ <b>{what} (<code>{self.name}</code>):</b>\n<code>{error}</code>"
        logger.error(message)
        if self.notifier:
            self.notifier.send_message(message, parse_mode="HTML")
