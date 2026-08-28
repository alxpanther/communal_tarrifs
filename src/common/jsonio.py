"""Reading the previous file and writing the new one.

Both output files of a country are byte-identical; the only difference is where they go.
Every pipeline goes through save_country_json(), so the root object is stamped in exactly
one place and stays consistent between countries.
"""

import json
import logging
import os
from datetime import datetime

from common.countries import Country
from common.paths import assets_output_path, docs_output_path

logger = logging.getLogger(__name__)

# Schema version of a country tariff file. Documented in docs/en/JSON_SPECIFICATION.md.
SCHEMA_VERSION = "1.0"

# Order of the root keys in the written file. Purely cosmetic, but it keeps the git diff
# of a regenerated file readable.
ROOT_ORDER = ("version", "last_updated_at", "country", "country_names", "currency",
              "electricity", "water", "hot_water", "heating")


def empty_city_block(source_url: str = "") -> dict:
    return {
        "source_url": source_url or "",
        "update_date": datetime.now().strftime("%Y-%m-%d"),
        "cities": []
    }


def load_previous(country: Country) -> dict:
    """Previous run's output, or None when there is nothing usable to build on.

    The published file wins over the bundled asset: they are written together, but the
    published one is the file the Android app actually reads.
    """
    for path in (docs_output_path(country.code), assets_output_path(country.code)):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to parse previous output {path}: {e}")
            continue
        if data and "electricity" in data and "water" in data:
            return data
    return None


def build_root(country: Country, blocks: dict) -> dict:
    """Assembles the root object from the four tariff blocks."""
    return {
        "version": SCHEMA_VERSION,
        "last_updated_at": datetime.now().isoformat(),
        "country": country.code,
        "country_names": dict(country.country_names),
        "currency": country.currency,
        "electricity": blocks.get("electricity", {}),
        "water": blocks.get("water", empty_city_block()),
        "hot_water": blocks.get("hot_water", empty_city_block()),
        "heating": blocks.get("heating", empty_city_block())
    }


def _ordered(data: dict) -> dict:
    ordered = {key: data[key] for key in ROOT_ORDER if key in data}
    for key, value in data.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def save_country_json(country: Country, data: dict) -> list:
    """Writes docs/tariffs_<cc>.json and assets/tariffs_<cc>_default.json.

    Refuses to write a file without an electricity block: a run that lost its data must
    leave the previous file in place rather than publish an empty one.
    """
    if not data.get("electricity"):
        raise ValueError(f"Refusing to write {country.code}: electricity block is empty")

    payload = _ordered(data)
    written = []
    for path in (docs_output_path(country.code), assets_output_path(country.code)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        written.append(path)
    logger.info(f"{country.code}: saved " + " and ".join(written))
    return written
