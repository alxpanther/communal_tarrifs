"""The extraction model, whichever provider serves it.

    extractor = llm.from_config(config, notifier)
    answer = extractor.extract([document, ...], instruction)

The provider is chosen per country by `settings.llm.provider` in config/<cc>/sources.json.
A config without `settings.llm` is read the old way — Gemini, `settings.gemini_model`.
"""

from common.llm import gemini, openai_compatible
from common.llm.base import Extractor, LLMUnavailable, parse_json_response
from common.llm.gemini import resolve_model

PROVIDERS = {
    "gemini": gemini.build,
    "openai_compatible": openai_compatible.build,
}

__all__ = ["Extractor", "LLMUnavailable", "from_config", "parse_json_response", "resolve_model"]


def from_config(config: dict, notifier=None) -> Extractor:
    settings = config.get("settings", {}) or {}
    llm_settings = settings.get("llm")
    if not llm_settings:
        llm_settings = {
            "provider": "gemini",
            "model": settings.get("gemini_model"),
            "auto_select_latest_model": settings.get("auto_select_latest_model", True),
        }
    provider = llm_settings.get("provider")
    builder = PROVIDERS.get(provider)
    if not builder:
        raise LLMUnavailable(f"unknown settings.llm.provider '{provider}', "
                             f"expected one of: {', '.join(PROVIDERS)}")
    return builder(llm_settings, notifier)
