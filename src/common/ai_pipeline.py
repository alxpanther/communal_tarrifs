"""Pipeline for a country whose tariffs are read from live sources, city by city.

Ukraine gets every city from one aggregated table. Most other countries have no such
table: each city is regulated separately and publishes its own decree, so the unit of work
here is one city and one service, with its own source URL in config/<cc>/sources.json.

The shape of a run is the same as Ukraine's and the guarantee is the same too:

    previous file -> fetch -> extract -> validate -> merge what passed -> save

A city that fails at any stage keeps the tariff it had, and the reason goes to Telegram.
The file is always written; it is never emptied by a failure. Nothing in this module knows
a country, a URL, a supplier or a price — all of that lives in config.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime

from common import llm, prompts
from common.countries import Country
from common.fetching import fetch_all
from common.jsonio import build_root, empty_city_block, load_previous, save_country_json
from common.overrides import (CITY_BLOCKS, apply_base_rate_to_zones, apply_manual_overrides,
                              resolve_periods)
from common.paths import sources_path
from common.registry import HEAT_SECTION, WATER_SECTION, reconcile_cities
from common.validation import Rejected, as_number, validate_city

logger = logging.getLogger(__name__)

# Unit published for each block. The app reads these, so they are part of the output
# schema rather than a per-country choice.
BLOCK_UNITS = {"water": "m3", "hot_water": "m3", "heating": "Gcal"}


class ConfigError(Exception):
    pass


def load_config(country: Country) -> dict:
    path = sources_path(country.code)
    if not os.path.exists(path):
        raise ConfigError(f"Configuration file missing at {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if not config.get("cities"):
        raise ConfigError(
            f"{country.code}: config needs a 'cities' section — this pipeline reads tariffs "
            f"from the sources declared there, it has no other way to obtain a number"
        )
    return config


def _sources_of(city: dict, block: str) -> list:
    """URLs to read for one city and one block. A list, because a tariff is often split:
    the water component on the водоканал site, the heat component on the regulator's."""
    block_config = (city.get("sources") or {}).get(block)
    if not block_config:
        return []
    if isinstance(block_config, str):
        return [block_config]
    urls = block_config.get("url") or block_config.get("urls") or []
    return [urls] if isinstance(urls, str) else list(urls)


def _hint_of(city: dict, block: str) -> str:
    """A line from config telling the model which of several tariffs on the page is the one.

    A heat supplier prints a tariff before and after the heat substation, a водоканал
    prints drinking and technical water, a regulator prints every price zone it governs.
    Which one a household in this city actually pays is knowledge about the city, not about
    the tariff, so it belongs in config next to the URL rather than in a prompt template.
    """
    block_config = (city.get("sources") or {}).get(block)
    if isinstance(block_config, dict):
        return str(block_config.get("hint") or "")
    return ""


# Keys of `settings.llm` a single source may override, next to its URLs.
SOURCE_LLM_OPTIONS = ("model", "json_mode", "extra_params")


def _llm_options_of(city: dict, block: str) -> dict:
    """What one source changes about how the model is called.

    The country's settings are chosen for the price of reading every city. A source too dense
    for them — the eighteen-column tariff menu of a Moscow heat company, where the default
    model mixed up rows and columns — gets a stronger model, or reasoning switched on, of its
    own instead of moving the whole country to the expensive setup.
    """
    block_config = (city.get("sources") or {}).get(block)
    if not isinstance(block_config, dict):
        return {}
    return {key: block_config[key] for key in SOURCE_LLM_OPTIONS if key in block_config}


def _supplier_of(city: dict, block: str) -> str:
    block_config = (city.get("sources") or {}).get(block)
    if isinstance(block_config, dict) and block_config.get("supplier"):
        return str(block_config["supplier"])
    return str(city.get("supplier") or "")


def _aliases_of(city: dict, block: str) -> list:
    """How the source spells the supplier, when that differs from the canonical name."""
    block_config = (city.get("sources") or {}).get(block)
    if isinstance(block_config, dict):
        aliases = block_config.get("supplier_aka") or []
        return [aliases] if isinstance(aliases, str) else list(aliases)
    return []


def _previous_city(previous_block: dict, code: str) -> dict:
    for city in (previous_block or {}).get("cities", []) or []:
        if city.get("city_code") == code:
            return city
    return {}


# Exactly the fields the published schema defines for each block. A validated record can
# carry more — the two components of a hot water tariff, for instance — and they stay out
# of the file: the field list is a contract with a released app, not a place to improvise.
PUBLISHED_FIELDS = {
    "water": ("water_supply", "sewage", "total_rate", "effective_date", "decree_info"),
    "hot_water": ("rate", "effective_date", "decree_info"),
    "heating": ("tariff_type", "rate_gcal", "rate_gcal_hour", "effective_date", "decree_info"),
}


def _publish(record: dict, code: str, block: str, today: date) -> dict:
    """Flattens a validated record to the single set of values published today."""
    resolved, stale = resolve_periods(record, today, f"{block}.{code}")
    if stale:
        logger.warning(stale)
    published = {"city_code": code, "city_name": resolved["city_name"],
                 "supplier": resolved["supplier"], "unit": BLOCK_UNITS[block]}
    for field in PUBLISHED_FIELDS[block]:
        if field in resolved:
            published[field] = resolved[field]
    return published


@dataclass
class BlockResult:
    """What one block of a run produced."""

    cities: list     # the full list to publish: refreshed cities and carried-over ones
    refreshed: list  # codes refreshed from a source on this run
    failures: list   # one line per reason something was not refreshed
    records: dict    # code -> validated record, with every period the source listed
    raw: dict        # code -> the model's answer as it came, kept to diagnose a rejection


def collect_block(country: Country, config: dict, block: str, previous_block: dict,
                  extractor, only: list = None) -> BlockResult:
    """Reads one block for every city that declares a source for it.

    With `only`, just those cities are read and every other city is carried over as it was
    published — that is what makes testing a single city cost one model call.
    """
    timeout = int((config.get("settings", {}) or {}).get("timeout_seconds") or 30)
    limits = config.get("validation", {}) or {}
    today = date.today()

    published = {c.get("city_code"): dict(c) for c in (previous_block or {}).get("cities", [])}
    refreshed, failures, records, raw = [], [], {}, {}

    def failed(reason: str):
        """A miss is a normal outcome, but it must never be silent: the city keeps its old
        tariff, and someone has to be able to see why from the run log alone."""
        logger.warning(f"{country.code} {block}: {reason}")
        failures.append(reason)

    for code, city in (config.get("cities") or {}).items():
        if only and code not in only:
            continue
        urls = _sources_of(city, block)
        if not urls:
            continue

        label = city.get("city_name") or code
        documents = fetch_all(urls, timeout)
        if not documents:
            failed(f"{label}: ни один источник не открылся ({', '.join(urls)})")
            continue

        instruction = prompts.city_prompt(
            block, city.get("city_name", code), _supplier_of(city, block),
            country.currency, BLOCK_UNITS[block], _hint_of(city, block),
        )
        extracted = extractor.extract([d.as_llm_part() for d in documents], instruction,
                                      _llm_options_of(city, block))
        raw[code] = extracted
        if not extracted:
            failed(f"{label}: модель ничего не извлекла из источника")
            continue
        if not extracted.get("periods"):
            failed(f"{label}: в источнике не найден тариф для этого города")
            continue

        identity = {"city_name": city.get("city_name", code),
                    "supplier": _supplier_of(city, block),
                    "aliases": _aliases_of(city, block)}
        try:
            record = validate_city(block, code, identity, extracted,
                                   _previous_city(previous_block, code), limits)
        except Rejected as rejection:
            for reason in rejection.reasons:
                failed(reason)
            continue

        published[code] = _publish(record, code, block, today)
        records[code] = record
        refreshed.append(code)
        logger.info(f"{country.code} {block}: {label} refreshed from source")

    return BlockResult(list(published.values()), refreshed, failures, records, raw)


def sync_zone_schedule(electricity: dict, config: dict):
    """Copies the zone schedule from config onto the block being published.

    Hours and coefficients are a description of the tariff, not a tariff, so they live in
    config — and editing them there has to reach the file. Without this the block is carried
    over from the previous run and a corrected coefficient never takes effect. The rates
    themselves stay derived from base_rate.
    """
    configured = (config.get("electricity", {}) or {}).get("zones")
    if not configured:
        return
    electricity["zones"] = json.loads(json.dumps(configured))
    apply_base_rate_to_zones(electricity, float(electricity.get("base_rate") or 0.0))


def drop_retired_cities(data: dict, config: dict) -> list:
    """Removes cities config has retired, and says which ones were removed.

    A city is retired when it has no source that can be read and the values still published
    for it are not trustworthy — an entry nobody can refresh is worse than no entry, because
    the app shows it as a current tariff. The `city_code` stays in city_registry.json
    forever, so retiring is not the same as freeing the code for reuse: if a usable source
    appears later the city comes back under the code its users already saved.
    """
    retired = {str(code) for code in (config.get("retired_cities") or [])}
    if not retired:
        return []

    removed = []
    for block in CITY_BLOCKS:
        cities = data.get(block, {}).get("cities", [])
        kept = [c for c in cities if c.get("city_code") not in retired]
        if len(kept) != len(cities):
            removed.extend(f"{block}: {c.get('city_code')}" for c in cities
                           if c.get("city_code") in retired)
            data[block]["cities"] = kept
    return removed


def collect_electricity(country: Country, config: dict, previous: dict, extractor) -> tuple:
    """Reads the country-wide electricity tariff, when a source is declared for it."""
    source = (config.get("electricity", {}) or {}).get("source")
    if not source:
        return previous, [], 0

    timeout = int((config.get("settings", {}) or {}).get("timeout_seconds") or 30)
    urls = [source] if isinstance(source, str) else list(source.get("urls") or [source.get("url")])
    documents = fetch_all([u for u in urls if u], timeout)
    if not documents:
        return previous, ["электроэнергия: источник не открылся"], 0

    unit = (config.get("electricity", {}) or {}).get("unit", "kWh")
    region = (config.get("electricity", {}) or {}).get("region") or country.code
    hint = source.get("hint", "") if isinstance(source, dict) else ""
    extracted = extractor.extract(
        [d.as_llm_part() for d in documents],
        prompts.electricity_prompt(region, country.currency, unit, hint=hint),
    )

    periods = extracted.get("periods") if isinstance(extracted, dict) else None
    if not periods:
        return previous, ["электроэнергия: тариф не извлечён из источника"], 0

    record = {"city_name": region, "supplier": region, "periods": []}
    for raw in periods:
        rate = as_number(raw.get("base_rate"))
        if not rate or rate <= 0:
            continue
        entry = {"from": raw.get("from"), "base_rate": round(rate, 4),
                 "decree_info": str(raw.get("decree_info") or "").strip()}
        if raw.get("to"):
            entry["to"] = raw["to"]
        record["periods"].append(entry)

    if not record["periods"]:
        return previous, ["электроэнергия: извлечён нулевой или нечисловой тариф"], 0

    ceiling = as_number((config.get("validation", {}) or {}).get("electricity", {}).get("max_rate"))
    resolved, stale = resolve_periods(record, date.today(), "electricity")
    if stale:
        logger.warning(stale)
    rate = float(resolved["base_rate"])
    if ceiling and rate > ceiling:
        return previous, [f"электроэнергия: тариф {rate} выше предела {ceiling}"], 0

    was = as_number(previous.get("base_rate"))
    ratio = as_number((config.get("validation", {}) or {}).get("max_change_ratio"))
    if was and ratio and abs(rate - was) / was > ratio:
        return previous, [f"электроэнергия: тариф изменился с {was} на {rate}, "
                          f"больше порога {round(ratio * 100)}%"], 0

    # A rate with no decree behind it is still published — it was read from a real page and
    # the alternative is keeping a two-year-old number — but the run says so, because a
    # tariff whose source names no document cannot be checked against anything later.
    notes = []
    if not resolved.get("decree_info"):
        notes.append("электроэнергия: тариф обновлён, но источник не назвал реквизиты документа")

    updated = dict(previous)
    updated["base_rate"] = rate
    updated["effective_date"] = resolved.get("effective_date", "")
    updated["decree_info"] = resolved.get("decree_info", "")
    updated["update_date"] = date.today().strftime("%Y-%m-%d")
    if isinstance(source, dict) and source.get("url"):
        updated["source_url"] = source["url"]
    apply_base_rate_to_zones(updated, rate)
    return updated, notes, 1


def _report(country: Country, refreshed: dict, failures: dict, notifier,
            scope: str = "", usage: str = ""):
    """One message per run: what was refreshed, what it cost, and every reason something
    was not refreshed."""
    if not notifier:
        return
    total_failures = sum(len(v) for v in failures.values())
    title = f"<b>{country.code}: обновление тарифов</b>"
    if scope:
        title += f"\nтолько: {scope}"
    lines = [title]
    for block, count in refreshed.items():
        lines.append(f"• {block}: обновлено {count}")
    if usage:
        lines.append(f"• модель: <code>{usage}</code>")
    if total_failures:
        lines.append(f"\n⚠️ <b>Не обновлено ({total_failures}) — опубликованы прежние значения:</b>")
        shown = 0
        for block, reasons in failures.items():
            for reason in reasons:
                if shown >= 20:
                    break
                lines.append(f"• <code>{block}: {reason}</code>")
                shown += 1
        if total_failures > shown:
            lines.append(f"… и ещё {total_failures - shown}")
    notifier.send_message("\n".join(lines), parse_mode="HTML")


def _scope(cities: list, blocks: list) -> str:
    return " / ".join(", ".join(part) for part in (cities, blocks) if part)


def collect(country: Country, config: dict, previous: dict, extractor,
            cities: list = None, blocks: list = None) -> tuple:
    """Reads the selected part of a country from its sources. Writes nothing.

    `cities` and `blocks` narrow the run; everything outside them is carried over from the
    previous file untouched. Returns (data, refreshed, failures, results), where results
    maps each block that was read to its BlockResult.
    """
    today = date.today().strftime("%Y-%m-%d")
    data = {block: previous.get(block, empty_city_block()) for block in CITY_BLOCKS}
    data["electricity"] = previous.get("electricity", {})
    refreshed, failures, results = {}, {}, {}

    for block in CITY_BLOCKS:
        if blocks and block not in blocks:
            continue
        result = collect_block(country, config, block, data[block], extractor, cities)
        data[block] = dict(data[block])
        data[block]["cities"] = result.cities
        if result.refreshed:
            data[block]["update_date"] = today
        refreshed[block] = len(result.refreshed)
        results[block] = result
        if result.failures:
            failures[block] = result.failures

    # Electricity is one value for the whole country, so a run narrowed to cities leaves it
    # alone unless it is asked for by name.
    if (blocks and "electricity" in blocks) or (not blocks and not cities):
        data["electricity"], notes, count = collect_electricity(
            country, config, data["electricity"], extractor)
        refreshed["electricity"] = count
        if notes:
            for reason in notes:
                logger.warning(f"{country.code} electricity: {reason}")
            failures["electricity"] = notes

    return data, refreshed, failures, results


def run(country: Country, notifier=None, cities: list = None, blocks: list = None,
        config: dict = None) -> dict:
    """Generates and saves the country file from its live sources.

    `cities` and `blocks` publish part of a country and keep the rest as it was. Without them
    the whole country is collected — the most expensive thing this repository does, and never
    the way to check a fix in one city: that is what src/run_city.py is for.
    """
    config = config or load_config(country)
    extractor = llm.from_config(config, notifier)
    logger.info(f"{country.code}: extracting with {extractor.name}")

    previous = load_previous(country)
    if not previous:
        raise ConfigError(
            f"{country.code}: no previously published file to build on. The first file of a "
            f"country is created by its manual pipeline; this one only refreshes."
        )

    data, refreshed, failures, _ = collect(country, config, previous, extractor, cities, blocks)
    logger.info(f"{country.code}: {extractor.usage_line()}")

    data = apply_manual_overrides(data, config, notifier)
    sync_zone_schedule(data["electricity"], config)

    removed = drop_retired_cities(data, config)
    if removed:
        logger.info(f"{country.code}: retired cities dropped — {', '.join(removed)}")

    if not data["electricity"].get("base_rate"):
        raise ConfigError(f"{country.code}: refusing to publish a zero electricity tariff")

    reconcile_cities(country.code, data["water"].get("cities", []), WATER_SECTION, notifier)
    for block in ("hot_water", "heating"):
        reconcile_cities(country.code, data[block].get("cities", []), HEAT_SECTION, notifier)

    _report(country, refreshed, failures, notifier, _scope(cities, blocks), extractor.usage_line())

    final = build_root(country, data)
    save_country_json(country, final)
    return final
