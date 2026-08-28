"""The permanent supplier -> city_code registry, config/<cc>/city_registry.json.

A city_code is the user's saved choice inside the Android app, so once a supplier has been
given a code that code never changes. The registry is the memory that guarantees it, and
it is committed to git for exactly that reason.
"""

import json
import logging
import os
import re

from common.paths import registry_path

logger = logging.getLogger(__name__)

# Water utilities and heat suppliers are different companies, so they live in separate
# sections; hot water and heating share one because it is the same companies.
WATER_SECTION = "suppliers"
HEAT_SECTION = "heat_suppliers"

REGISTRY_COMMENT = (
    "PERMANENT registry of city_code values. Never edit or delete existing entries: "
    "the Android app stores city_code as the user's saved selection."
)


def normalize_name(text: str) -> str:
    """Supplier names differ between runs in quotes, case and spacing only."""
    return re.sub(r"[^\w]+", "", str(text or "").lower())


def load_registry_file(code: str) -> dict:
    path = registry_path(code)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read city registry {path}: {e}")
        return {}


def load_section(code: str, section: str = WATER_SECTION) -> dict:
    data = load_registry_file(code)
    return data.get(section, {}) or {}


def save_section(code: str, suppliers: dict, section: str = WATER_SECTION):
    path = registry_path(code)
    data = load_registry_file(code)
    data["_comment"] = REGISTRY_COMMENT
    data.setdefault(WATER_SECTION, {})
    data.setdefault(HEAT_SECTION, {})
    data[section] = suppliers
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def reconcile_cities(code: str, cities: list, section: str, notifier=None) -> list:
    """Forces registry city_code / city_name onto the given cities and records new suppliers.

    Returns the list of suppliers registered for the first time by this call.
    """
    known = load_section(code, section)
    by_normalized = {normalize_name(name): (name, entry) for name, entry in known.items()}
    taken = {entry.get("city_code") for entry in known.values() if entry.get("city_code")}

    added = []
    for city in cities:
        supplier = str(city.get("supplier") or "").strip()
        declared_code = str(city.get("city_code") or "").strip().lower()
        match = by_normalized.get(normalize_name(supplier)) if supplier else None

        if match:
            _, entry = match
            registered = entry.get("city_code")
            if registered and registered != declared_code:
                # The registry always wins: a code, once published, is a user's saved choice.
                logger.warning(
                    f"{code}: keeping registered city_code '{registered}' for '{supplier}' "
                    f"instead of '{declared_code}'"
                )
                city["city_code"] = registered
            if entry.get("city_name"):
                city["city_name"] = entry["city_name"]
            continue

        if not supplier or not declared_code:
            continue
        if declared_code in taken:
            logger.warning(
                f"{code}: city_code '{declared_code}' is already taken in section '{section}', "
                f"supplier '{supplier}' not registered"
            )
            continue

        known[supplier] = {"city_code": declared_code, "city_name": city.get("city_name", "")}
        by_normalized[normalize_name(supplier)] = (supplier, known[supplier])
        taken.add(declared_code)
        added.append(supplier)

    if added:
        save_section(code, known, section)
        message = (f"🆕 <b>{code}</b>: в реестр добавлены поставщики "
                   f"({section}):\n" + "\n".join(f"• {name}" for name in added))
        logger.info(f"{code}: registered new suppliers in '{section}': {', '.join(added)}")
        if notifier:
            notifier.send_message(message, parse_mode="HTML")

    return added
