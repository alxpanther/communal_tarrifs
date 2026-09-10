"""manual_override — values the maintainer forces on top of whatever a pipeline produced.

Shared by every country: overrides are the only way to correct a published tariff without
touching a generated file by hand, so their semantics must not differ between countries.

`null` means "do not override this field". To zero a tariff, write `0.0`.
"""

import logging
from datetime import date, datetime

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

# A city record may carry `periods` instead of flat values: the regulator publishes the
# whole indexation schedule years ahead, so the maintainer enters every dated version once
# and the pipeline picks the one in force on the day it runs.
PERIOD_KEY = "periods"
PERIOD_BOUNDS = ("from", "to")
DATE_FORMAT = "%Y-%m-%d"


def _parse_date(value, field: str, where: str) -> date:
    try:
        return datetime.strptime(str(value), DATE_FORMAT).date()
    except (TypeError, ValueError):
        raise ValueError(f"{where}: '{field}' must be a {DATE_FORMAT} date, got {value!r}")


def resolve_periods(fields: dict, today: date, where: str = "") -> tuple:
    """Flattens a dated city record down to the version in force on `today`.

    Returns (fields, warning). A record without `periods` is returned untouched. The
    period in force is the last one that has already started; its `from` becomes the
    default `effective_date`, so the date is written once rather than twice.

    An expired last period is still published, with a warning: a tariff nobody entered yet
    is stale data, and stale data beats no data — the app would otherwise lose the city.
    """
    periods = fields.get(PERIOD_KEY)
    if not periods:
        return fields, None

    if not isinstance(periods, list):
        raise ValueError(f"{where}: '{PERIOD_KEY}' must be a list")

    dated = []
    for index, period in enumerate(periods):
        if not isinstance(period, dict):
            raise ValueError(f"{where}: '{PERIOD_KEY}[{index}]' must be an object")
        start = _parse_date(period.get("from"), "from", f"{where} {PERIOD_KEY}[{index}]")
        end = period.get("to")
        end = _parse_date(end, "to", f"{where} {PERIOD_KEY}[{index}]") if end else None
        if end and end < start:
            raise ValueError(f"{where}: '{PERIOD_KEY}[{index}]' ends before it starts")
        dated.append((start, end, period))
    dated.sort(key=lambda item: item[0])

    warning = None
    started = [item for item in dated if item[0] <= today]
    if started:
        start, end, period = started[-1]
        if end and end < today:
            warning = (f"{where}: последний период закончился {end.isoformat()}, "
                       f"публикуется устаревший тариф")
    else:
        # Every version is still in the future: the first one is the closest thing to a
        # current tariff there is, and publishing nothing would drop the city instead.
        start, end, period = dated[0]
        warning = (f"{where}: первый период начинается {start.isoformat()}, "
                   f"тарифа на сегодня нет")

    resolved = {key: value for key, value in fields.items() if key != PERIOD_KEY}
    resolved.update({key: value for key, value in period.items()
                     if key not in PERIOD_BOUNDS and value is not None})
    resolved.setdefault("effective_date", start.strftime(DATE_FORMAT))
    return resolved, warning


def apply_base_rate_to_zones(elec_data: dict, base_rate: float):
    """Recomputes every zone rate from the base rate and the coefficient of that zone."""
    for zone in elec_data.get("zones", {}).values():
        if not isinstance(zone, dict):
            continue
        for part in zone.values():
            if isinstance(part, dict) and "coefficient" in part:
                part["rate"] = round(base_rate * float(part["coefficient"]), 4)


def merge_city_overrides(cities: list, overrides: dict, block: str, notifier=None,
                        today: date = None) -> list:
    """
    Applies manual per-city overrides keyed by city_code. A city already present is patched
    field by field, an unknown one is appended — the only way to publish a supplier the
    source site does not list at all, such as КП "КИЇВТЕПЛОЕНЕРГО" for heating.

    A record written as `periods` is collapsed to the version in force today first, so the
    rest of the function never sees the difference.
    """
    if not overrides:
        return cities

    today = today or date.today()
    by_code = {city.get("city_code"): city for city in cities}
    incomplete = []
    stale = []

    for code, fields in overrides.items():
        if not isinstance(fields, dict):
            continue

        fields, expired = resolve_periods(fields, today, f"{block}.{code}")
        if expired:
            logger.warning(expired)
            stale.append(expired)

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

    if stale and notifier:
        # Not an error: the file keeps the last known tariff. It is a reminder that the
        # regulator has moved on and the next period has to be entered by hand.
        notifier.send_message(
            f"🗓 <b>manual_override: истёк срок тарифов в блоке «{block}»</b>\n"
            + "\n".join(f"• <code>{i}</code>" for i in stale),
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
            target.get("cities", []), override.get("cities", {}) or {}, block, notifier,
            today=date.today()
        )
        if before != target["cities"]:
            target["update_date"] = today

    return data
