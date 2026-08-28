"""manual_override — values the maintainer forces on top of whatever a pipeline produced.

Shared by every country: overrides are the only way to correct a published tariff without
touching a generated file by hand, so their semantics must not differ between countries.

`null` means "do not override this field". To zero a tariff, write `0.0`.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# A city that the pipeline did not produce at all can only be added by hand if the record
# is complete: a half-filled city would reach the app as a broken tariff.
MANUAL_CITY_REQUIRED_FIELDS = {
    "water": ("city_name", "supplier", "water_supply", "sewage", "total_rate",
              "unit", "effective_date", "decree_info"),
    "hot_water": ("city_name", "supplier", "rate", "unit", "effective_date", "decree_info"),
    "heating": ("city_name", "supplier", "tariff_type", "rate_gcal", "rate_gcal_hour",
                "unit", "effective_date", "decree_info"),
}

CITY_BLOCKS = ("water", "hot_water", "heating")


def apply_base_rate_to_zones(elec_data: dict, base_rate: float):
    """Recomputes every zone rate from the base rate and the coefficient of that zone."""
    for zone in elec_data.get("zones", {}).values():
        if not isinstance(zone, dict):
            continue
        for part in zone.values():
            if isinstance(part, dict) and "coefficient" in part:
                part["rate"] = round(base_rate * float(part["coefficient"]), 4)


def merge_city_overrides(cities: list, overrides: dict, block: str, notifier=None) -> list:
    """
    Applies manual per-city overrides keyed by city_code. A city already present is patched
    field by field, an unknown one is appended — the only way to publish a supplier the
    source site does not list at all, such as КП "КИЇВТЕПЛОЕНЕРГО" for heating.
    """
    if not overrides:
        return cities

    by_code = {city.get("city_code"): city for city in cities}
    incomplete = []

    for code, fields in overrides.items():
        if not isinstance(fields, dict):
            continue

        target = by_code.get(code)
        if target is not None:
            for key, value in fields.items():
                if value is not None:
                    target[key] = value
            logger.info(f"Manual override patched city '{code}' in '{block}'")
            continue

        missing = [f for f in MANUAL_CITY_REQUIRED_FIELDS[block] if fields.get(f) is None]
        if missing:
            incomplete.append(f"{code}: не хватает полей {', '.join(missing)}")
            continue

        added = {"city_code": code}
        added.update({k: v for k, v in fields.items() if v is not None})
        cities.append(added)
        by_code[code] = added
        logger.info(f"Manual override added a new city '{code}' to '{block}'")

    if incomplete:
        logger.warning(f"{len(incomplete)} manual override cities skipped in '{block}'")
        if notifier:
            notifier.send_message(
                f"⚠️ <b>manual_override: города не добавлены в блок «{block}»</b>\n"
                + "\n".join(f"• <code>{i}</code>" for i in incomplete),
                parse_mode="HTML"
            )

    return cities


def apply_manual_overrides(data: dict, config: dict, notifier=None) -> dict:
    """
    Merges config/<cc>/sources.json -> manual_override on top of the data a pipeline built.
    It runs on the normal path, so pinning one value by hand never disables the rest of the
    pipeline: everything not overridden keeps refreshing itself.
    """
    manual = config.get("manual_override", {})
    if not manual.get("enabled"):
        return data

    logger.info("Manual override is enabled. Merging manual values on top of the pipeline data...")
    today = datetime.now().strftime("%Y-%m-%d")

    elec_override = manual.get("electricity", {}) or {}
    elec_data = data.get("electricity", {})
    for key in ("source_url", "effective_date", "decree_info"):
        if elec_override.get(key):
            elec_data[key] = elec_override[key]

    if elec_override.get("base_rate") is not None:
        elec_data["base_rate"] = float(elec_override["base_rate"])
        # Zone rates are derived from the base rate, so they have to follow it
        apply_base_rate_to_zones(elec_data, elec_data["base_rate"])
        elec_data["update_date"] = today

    for block in CITY_BLOCKS:
        override = manual.get(block, {}) or {}
        target = data.get(block, {})
        if not override or not isinstance(target, dict):
            continue

        if override.get("source_url"):
            target["source_url"] = override["source_url"]
        before = [dict(city) for city in target.get("cities", [])]
        target["cities"] = merge_city_overrides(
            target.get("cities", []), override.get("cities", {}) or {}, block, notifier
        )
        if before != target["cities"]:
            target["update_date"] = today

    return data
