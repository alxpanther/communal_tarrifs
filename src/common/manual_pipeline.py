"""Pipeline for a country whose tariffs are not scraped but declared in config.

Some countries publish their regulated tariffs only as a decision of the regulator, with no
machine-readable page to scrape: today Armenia and Azerbaijan. For those, config/<cc>/
sources.json -> manual_override *is* the source, and this module turns it into the same
JSON file the Ukrainian scraper produces.

It is deliberately the same shape as a scraping pipeline: start from the previous file,
patch it, never write an empty block. When a real source for such a country appears, its
src/countries/<cc>/fetcher.py grows a scraping stage in front of this one.
"""

import json
import logging
import os
from datetime import datetime

from common.countries import Country
from common.jsonio import build_root, empty_city_block, load_previous, save_country_json
from common.overrides import CITY_BLOCKS, apply_base_rate_to_zones, apply_manual_overrides
from common.paths import sources_path
from common.registry import HEAT_SECTION, WATER_SECTION, reconcile_cities

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    pass


def load_config(country: Country) -> dict:
    path = sources_path(country.code)
    if not os.path.exists(path):
        raise ConfigError(f"Configuration file missing at {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    manual = config.get("manual_override", {})
    if not manual.get("enabled"):
        raise ConfigError(
            f"{country.code} has no scraping source, so manual_override must be enabled "
            f"in {path}"
        )
    return config


def build_skeleton(country: Country, config: dict) -> dict:
    """The empty shape to patch when there is no previous file to start from.

    Every value here comes from config: no rate, URL or zone schedule is hardcoded.
    """
    ref = config.get("reference_sources", {}) or {}
    electricity = config.get("electricity", {}) or {}
    zones = electricity.get("zones") or {}
    if not zones:
        raise ConfigError(
            f"{country.code}: config needs an 'electricity.zones' section to build the "
            f"first file (zone schedule and coefficients)"
        )

    return {
        "electricity": {
            "source_url": ref.get("electricity") or "",
            "base_rate": 0.0,
            "unit": electricity.get("unit", "kWh"),
            "effective_date": "",
            "update_date": datetime.now().strftime("%Y-%m-%d"),
            "decree_info": "",
            "zones": json.loads(json.dumps(zones))
        },
        "water": empty_city_block(ref.get("water")),
        "hot_water": empty_city_block(ref.get("hot_water")),
        "heating": empty_city_block(ref.get("heating"))
    }


def sync_zone_schedule(data: dict, config: dict):
    """Keeps the zone schedule of an existing file in step with config.

    Hours and coefficients live in config, so editing them there must reach the published
    file; the rates themselves stay derived from base_rate.
    """
    configured = (config.get("electricity", {}) or {}).get("zones")
    if not configured:
        return
    data["electricity"]["zones"] = json.loads(json.dumps(configured))
    apply_base_rate_to_zones(data["electricity"], float(data["electricity"].get("base_rate") or 0.0))


def run(country: Country, notifier=None) -> dict:
    """Generates and saves the country file. Returns the written JSON."""
    config = load_config(country)

    previous = load_previous(country)
    if previous:
        logger.info(f"{country.code}: starting from the previous published file")
        data = {block: previous.get(block, empty_city_block()) for block in CITY_BLOCKS}
        data["electricity"] = previous.get("electricity", {})
    else:
        logger.info(f"{country.code}: no previous file, building the first one from config")
        data = build_skeleton(country, config)

    sync_zone_schedule(data, config)
    data = apply_manual_overrides(data, config, notifier)

    if not data["electricity"].get("base_rate"):
        raise ConfigError(
            f"{country.code}: electricity base_rate is missing — refusing to publish a file "
            f"with a zero electricity tariff"
        )

    reconcile_cities(country.code, data["water"].get("cities", []), WATER_SECTION, notifier)
    for block in ("hot_water", "heating"):
        reconcile_cities(country.code, data[block].get("cities", []), HEAT_SECTION, notifier)

    final = build_root(country, data)
    save_country_json(country, final)
    return final
