"""Electricity tariffs: every household tariff a source prints, read as printed.

A source rarely prints one price. Armenia prices a flat by how much it uses in a month and by
day and night; Belarus prices a flat with an electric stove apart from one with a gas stove and
prints two- and three-zone prices for both; Azerbaijan adds a fixed monthly charge; Ukraine
prices electric heating by season. All of that is published as `plans`: one entry per group of
consumers config names, one row per printed price. Nothing is derived from a coefficient kept
in config — config holds names and hints, the numbers come from the document.

The file keeps the older fields as well, because the released app bills by them: `base_rate`
and `zones` are taken from the plan config marks as the default, so an app that knows nothing
of plans keeps charging what it charged before.

The same reading serves a country-wide tariff (`electricity.source` in config) and the tariff of
one city (`cities.<code>.sources.electricity`), published into `electricity_cities`.
"""

import logging
import re
from datetime import date

from common import prompts
from common.fetching import fetch_all
from common.overrides import resolve_periods
from common.validation import DATE_FORMAT, Rejected, as_date, as_number, clean_decree

logger = logging.getLogger(__name__)

# The zones each kind of meter is billed by. A single-rate meter has one zone that covers the
# whole day; its name is the one the app already uses for the base rate.
METER_ZONES = {
    "single": ("all",),
    "two_zone": ("day", "night"),
    "three_zone": ("peak", "half_peak", "night"),
}

# How a price tied to a band of monthly consumption applies. "part": each part of the month's
# consumption is billed at the price of its band, as Azerbaijan prints it. "whole": the whole
# month's consumption is billed at the price of the band it reaches.
TIER_BASES = ("whole", "part")

SEASON = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")

# Every currency the pipeline publishes has a hundred subunits: tetri, bani, qəpik, dirams,
# tyiyn, kopecks. A regulator printing prices in them is told apart by the model; the division
# is done here, where it can be checked.
SUBUNITS_PER_UNIT = 100

ZONE_DESCRIPTIONS = {
    "two_zone": ("Двухзонный тариф (День/Ночь)", "Двухзонный тариф (не применяется, ставка одна)"),
    "three_zone": ("Трехзонный тариф (Пик/Полупик/Ночь)",
                   "Трехзонный тариф (не применяется, ставка одна)"),
}

# Which of the published zones the released app reads for each meter, and which printed zone
# fills it.
LEGACY_ZONES = {"two_zone": ("day", "night"), "three_zone": ("peak", "half_peak", "night")}


def plans_of(source: dict) -> dict:
    """code -> {name, hint, default} as config declares them, in config order."""
    return dict((source or {}).get("plans") or {})


def default_plan_of(source: dict) -> str:
    """The plan whose prices fill the older fields. Exactly one is marked; without a mark the
    first plan is the default, which is what a source with a single plan needs."""
    plans = plans_of(source)
    marked = [code for code, plan in plans.items() if (plan or {}).get("default")]
    return marked[0] if marked else next(iter(plans), "")


def _row_key(row: dict) -> tuple:
    return (row["meter"], row["zone"], row["tier"], row["above_kwh"], row["up_to_kwh"],
            row["season_from"], row["season_to"])


TIME = re.compile(r"(\d{1,2})[:.](\d{2})")


def _hours(value) -> str:
    """Zone hours spelled one way: '7:00 – 23:00' and '07.00-23.00' both become '07:00 - 23:00'."""
    text = TIME.sub(lambda m: f"{int(m.group(1)):02d}:{m.group(2)}", str(value or ""))
    text = re.sub(r"\s*[-–—]\s*", " - ", text)
    return re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", text)).strip()


def _kwh(value):
    """A band boundary as printed: a whole number of kWh stays whole in the file."""
    number = as_number(value)
    return int(number) if number is not None and number == int(number) else number


def _check_row(raw: dict, scale: float, limits: dict, label: str, reasons: list) -> dict:
    """One printed price. Returns the clean row or None."""
    meter = str(raw.get("meter") or "").strip()
    zone = str(raw.get("zone") or "").strip()
    if zone not in METER_ZONES.get(meter, ()):
        reasons.append(f"{label}: счётчик «{meter}» с зоной «{zone}» не бывает")
        return None

    rate = as_number(raw.get("rate"))
    if rate is None or rate <= 0:
        reasons.append(f"{label}: цена {raw.get('rate')!r} ({meter}/{zone}) не положительное число")
        return None
    rate = round(rate * scale, 4)
    ceiling = as_number((limits.get("electricity") or {}).get("max_rate"))
    if ceiling and rate > ceiling:
        reasons.append(f"{label}: цена {rate} ({meter}/{zone}) выше предела {ceiling}")
        return None

    above, up_to = _kwh(raw.get("above_kwh")), _kwh(raw.get("up_to_kwh"))
    if (above is not None and above < 0) or (up_to is not None and up_to <= 0) or \
            (above is not None and up_to is not None and above >= up_to):
        reasons.append(f"{label}: ступень потребления {above}–{up_to} кВт·ч не имеет смысла")
        return None
    # A band is numbered as printed — «1 уровень», «минимальный тариф» — because Almaty prints
    # the price of each level and leaves its bounds to a picture.
    tier = raw.get("tier")
    if tier is not None and (isinstance(tier, bool) or not isinstance(tier, int) or tier < 1):
        reasons.append(f"{label}: номер ступени {tier!r} не натуральное число")
        return None
    if tier is None and (above is not None or up_to is not None):
        reasons.append(f"{label}: у ступени {above}–{up_to} кВт·ч нет номера")
        return None

    season = (raw.get("season_from") or None, raw.get("season_to") or None)
    if any(season) and not all(value and SEASON.match(str(value)) for value in season):
        reasons.append(f"{label}: сезон {season[0]!r}–{season[1]!r} не в формате MM-DD")
        return None

    hours = _hours(raw.get("hours"))
    return {"meter": meter, "zone": zone, "hours": hours,
            "tier": tier, "above_kwh": above, "up_to_kwh": up_to,
            "season_from": season[0], "season_to": season[1], "rate": rate}


def _check_plan(raw: dict, configured: dict, scale: float, tax: float, limits: dict, label: str,
                reasons: list) -> dict:
    """One group of consumers with every price printed for it. Returns the clean plan or None.

    `scale` turns a printed price into the published one — tax added, subunits divided out.
    A monthly charge is printed in whole currency units even where prices are not, so it only
    gets the tax."""
    code = str(raw.get("plan") or "").strip()
    if code not in configured:
        reasons.append(f"{label}: группа «{code}» не объявлена в конфиге")
        return None
    where = f"{label}, группа {code}"

    rows = []
    for item in raw.get("rates") or []:
        row = _check_row(item, scale, limits, where, reasons) if isinstance(item, dict) else None
        if row is None:
            return None
        rows.append(row)
    if not rows:
        reasons.append(f"{where}: ни одной цены")
        return None
    keys = [_row_key(row) for row in rows]
    if len(set(keys)) != len(keys):
        reasons.append(f"{where}: одна и та же цена встречается дважды")
        return None

    basis = raw.get("tier_basis") or None
    if basis not in (None,) + TIER_BASES:
        reasons.append(f"{where}: tier_basis «{basis}» — ожидалось {', '.join(TIER_BASES)} или null")
        return None
    tiered = any(row["tier"] is not None for row in rows)
    per_resident = raw.get("tiers_per_resident")
    if per_resident not in (True, False, None):
        reasons.append(f"{where}: tiers_per_resident «{per_resident}» — ожидалось true, false или null")
        return None

    charge = as_number(raw.get("monthly_charge"))
    if charge is not None and charge < 0:
        reasons.append(f"{where}: отрицательная абонентская плата {charge}")
        return None

    return {"plan_code": code,
            "name": str((configured[code] or {}).get("name") or code),
            "is_default": False,
            "tier_basis": basis if tiered else None,
            "tiers_per_resident": per_resident if tiered else None,
            "monthly_charge": round(charge * tax, 4) if charge else None,
            "rates": sorted(rows, key=lambda r: (list(METER_ZONES).index(r["meter"]),
                                                 METER_ZONES[r["meter"]].index(r["zone"]),
                                                 r["season_from"] or "", r["tier"] or 0))}


def _in_season(row: dict, today: date) -> bool:
    if not row["season_from"]:
        return True
    day = today.strftime("%m-%d")
    start, end = row["season_from"], row["season_to"]
    return start <= day <= end if start <= end else (day >= start or day <= end)


def _lowest(rows: list, meter: str, zone: str, today: date):
    """The price of the first band of consumption for one zone, in the season of `today`."""
    found = [r for r in rows if r["meter"] == meter and r["zone"] == zone and _in_season(r, today)]
    return min(found, key=lambda r: r["tier"] or 0) if found else None


def legacy_fields(plan: dict, today: date) -> tuple:
    """(base_rate, zones) for the released app, from the prices of the default plan.

    The released app knows one rate per zone. It gets the first band of consumption, the one an
    ordinary flat stays in. A source that prints no single-rate price at all — Armenia prints
    day and night only — has its households on a single-rate meter billed at the day price, so
    that price stands in for it.
    """
    rows = plan["rates"]
    single = _lowest(rows, "single", "all", today) or _lowest(rows, "two_zone", "day", today)
    if not single:
        return 0.0, {}
    base = single["rate"]
    zones = {}
    for meter, names in LEGACY_ZONES.items():
        printed = {name: _lowest(rows, meter, name, today) for name in names}
        applies = all(printed.values())
        zones[meter] = {"description": ZONE_DESCRIPTIONS[meter][0 if applies else 1]}
        for name in names:
            row = printed[name] if applies else None
            rate = row["rate"] if row else base
            zones[meter][name] = {"hours": row["hours"] if row else "",
                                  "coefficient": round(rate / base, 4), "rate": rate}
    return base, zones


def validate(extracted: dict, source: dict, limits: dict, label: str) -> dict:
    """Checks one extraction. Returns a record with dated periods of plans, or raises Rejected."""
    if not isinstance(extracted, dict) or not isinstance(extracted.get("periods"), list) \
            or not extracted["periods"]:
        raise Rejected([f"{label}: тариф не извлечён из источника"])

    configured = plans_of(source)
    default = default_plan_of(source)
    vat = as_number(source.get("vat_percent")) or 0.0
    reasons, periods = [], []
    for index, raw in enumerate(extracted["periods"]):
        where = f"{label}, период #{index + 1}"
        if not isinstance(raw, dict):
            reasons.append(f"{where}: не объект")
            continue
        start = as_date(raw.get("from"))
        end = as_date(raw.get("to")) if raw.get("to") else None
        if not start or (end and end < start):
            reasons.append(f"{where}: даты периода {raw.get('from')!r}–{raw.get('to')!r} не разбираются")
            continue
        tax = 1 + vat / 100
        scale = tax / (SUBUNITS_PER_UNIT if raw.get("prices_in_subunits") is True else 1)
        plans = []
        for item in raw.get("plans") or []:
            plan = _check_plan(item, configured, scale, tax, limits, where, reasons) \
                if isinstance(item, dict) else None
            if plan is None:
                plans = None
                break
            plans.append(plan)
        if plans is None:
            continue
        codes = [plan["plan_code"] for plan in plans]
        if len(set(codes)) != len(codes):
            reasons.append(f"{where}: одна группа встречается дважды")
            continue
        if default not in codes:
            reasons.append(f"{where}: нет цен группы по умолчанию «{default}»")
            continue
        order = list(configured)
        plans.sort(key=lambda plan: order.index(plan["plan_code"]))
        for plan in plans:
            plan["is_default"] = plan["plan_code"] == default
        period = {"from": start.strftime(DATE_FORMAT), "plans": plans,
                  "decree_info": clean_decree(raw.get("decree_info"))}
        if end:
            period["to"] = end.strftime(DATE_FORMAT)
        periods.append(period)

    if reasons:
        raise Rejected(reasons)
    periods.sort(key=lambda p: p["from"])
    if len({p["from"] for p in periods}) != len(periods):
        raise Rejected([f"{label}: два периода начинаются в один день"])
    return {"periods": periods}


def _default(period: dict) -> dict:
    return next(plan for plan in period["plans"] if plan["is_default"])


def _unchanged_since(periods: list, effective: str, base: float, today: date) -> str:
    """The day the published base rate took effect.

    Periods are shared by every plan, so a source that reprices electric heating on 1 June splits
    the year there even though the ordinary flat has paid the same price since March. The date
    published next to `base_rate` is the start of that price, not of the period the split made.
    """
    starts = [p for p in periods if p["from"] <= effective]
    for earlier, later in zip(reversed(starts[:-1]), reversed(starts[1:])):
        if earlier.get("to") and as_date(earlier["to"]).toordinal() + 1 != as_date(later["from"]).toordinal():
            break
        if legacy_fields(_default(earlier), today)[0] != base:
            break
        effective = earlier["from"]
    return effective


def _check_against_previous(base: float, effective: str, previous: dict, limits: dict,
                            label: str) -> list:
    """The two guards every city block has: no jump by a multiple, and no new number for a
    period already published. See validation._check_against_previous."""
    was = as_number(previous.get("base_rate"))
    if not was:
        return []
    ratio = as_number(limits.get("max_change_ratio"))
    if ratio and abs(base - was) / was > ratio:
        return [f"{label}: тариф изменился с {was} на {base}, больше порога {round(ratio * 100)}%"]
    tolerance = as_number(limits.get("same_period_tolerance"))
    if tolerance is not None and previous.get("effective_date") == effective \
            and abs(base - was) / was > tolerance:
        return [f"{label}: период с {effective} уже опубликован со значением {was}, а извлечено "
                f"{base} — вероятно, прочитана не та строка"]
    return []


def publish(record: dict, previous: dict, limits: dict, label: str, today: date) -> dict:
    """The fields published for the period in force today. Raises Rejected."""
    resolved, stale = resolve_periods(record, today, label)
    if stale:
        logger.warning(stale)
    base, zones = legacy_fields(_default(resolved), today)
    if not base:
        raise Rejected([f"{label}: у группы по умолчанию нет цены ни для однотарифного счётчика, "
                        f"ни дневной зоны"])
    effective = _unchanged_since(record["periods"], resolved.get("effective_date", ""), base, today)
    reasons = _check_against_previous(base, effective, previous, limits, label)
    if reasons:
        raise Rejected(reasons)

    unchanged = previous.get("decree_info") and previous.get("effective_date") == effective \
        and as_number(previous.get("base_rate")) == base
    return {"base_rate": base, "effective_date": effective,
            "decree_info": clean_decree(previous["decree_info"] if unchanged
                                        else resolved.get("decree_info", "")),
            "zones": zones, "plans": resolved["plans"]}


def read(source: dict, region: str, currency: str, unit: str, previous: dict, config: dict,
         extractor, label: str, supplier: str = "") -> tuple:
    """Fetches, extracts and validates one electricity source.

    Returns (published fields or None, reasons it was not refreshed, the model's raw answer).
    """
    timeout = int((config.get("settings", {}) or {}).get("timeout_seconds") or 30)
    urls = [u for u in (source.get("urls") or [source.get("url")]) if u]
    problems = []
    documents = fetch_all(urls, timeout, bool(source.get("read_images")),
                          source.get("read_documents") or False, problems)
    if not documents:
        return None, [f"{label}: источник не открылся ({'; '.join(problems) or ', '.join(urls)})"], None

    instruction = prompts.electricity_prompt(region, currency, unit, plans_of(source),
                                             hint=source.get("hint", ""), supplier=supplier)
    options = {key: source[key] for key in ("model", "json_mode", "extra_params") if key in source}
    extracted = extractor.extract([d.as_llm_part() for d in documents], instruction, options)
    limits = config.get("validation", {}) or {}
    try:
        record = validate(extracted, source, limits, label)
        published = publish(record, previous or {}, limits, label, date.today())
    except Rejected as rejection:
        return None, rejection.reasons, extracted

    if not published["decree_info"]:
        logger.warning(f"{label}: тариф обновлён, но источник не назвал реквизиты документа")
    published["source_url"] = urls[0]
    return published, [], extracted


def merge(previous: dict, published: dict, unit: str) -> dict:
    """The block as it goes into the file: the previous one with the fresh fields on top."""
    updated = dict(previous or {})
    updated.update(published)
    updated["unit"] = unit
    updated["update_date"] = date.today().strftime(DATE_FORMAT)
    return updated
