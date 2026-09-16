"""Natural gas for households: the price of the gas, the price of delivering it, and the
consumption norms a household without a meter is billed by.

Gas is priced more ways than any other service. Ukraine lets a household choose its supplier and
bills delivery separately, per distribution network; Russia prints one price per thousand m³ with
delivery included; Azerbaijan prices bands of annual consumption; Georgia prices winter apart from
summer. All of that is published as `plans` with `rates`, shaped like the electricity plans, and
every city also carries the plain `supplier` + `rate` + `distribution_rate`, so an app that reads
nothing else can still bill a metered household.

This module holds what every gas source shares: the checks, the shape of the published city and
the reading of a per-city source by the model. How one aggregate page is parsed stays with the
country that has it (Ukraine).
"""

import logging
import re
from datetime import date

from common import prompts
from common.fetching import fetch_all
from common.overrides import resolve_periods
from common.validation import DATE_FORMAT, Rejected, as_date, as_number, clean_decree

logger = logging.getLogger(__name__)

BLOCK = "gas"
UNIT = "m3"

CONTRACTS = ("annual", "monthly")
USAGES = ("cooking", "heating")
TIER_PERIODS = ("month", "year")

# What a consumption norm is for, and what it is multiplied by.
NORM_USAGES = ("stove_with_hot_water", "stove_without_hot_water", "stove_and_water_heater",
               "water_heater", "heating")
NORM_BASES = ("per_person", "per_m2")

# How a source prints its price. A thousand m³ is converted here, where it can be checked.
PRICE_UNITS = {"m3": 1, "thousand_m3": 1000}

SEASON = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _m3(value):
    """A band boundary as printed: a whole number of m³ stays whole in the file."""
    number = as_number(value)
    return int(number) if number is not None and number == int(number) else number


def check_rate(raw: dict, scale: float, limits: dict, label: str, reasons: list) -> dict:
    """One printed price of a plan. Returns the clean row or None."""
    rate = as_number(raw.get("rate"))
    if rate is None or rate <= 0:
        reasons.append(f"{label}: цена {raw.get('rate')!r} не положительное число")
        return None
    rate = round(rate * scale, 5)
    ceiling = as_number((limits.get(BLOCK) or {}).get("max_rate"))
    if ceiling and rate > ceiling:
        reasons.append(f"{label}: цена {rate} за м³ выше предела {ceiling}")
        return None

    above, up_to = _m3(raw.get("above_m3")), _m3(raw.get("up_to_m3"))
    if (above is not None and above < 0) or (up_to is not None and up_to <= 0) or \
            (above is not None and up_to is not None and above >= up_to):
        reasons.append(f"{label}: ступень потребления {above}–{up_to} м³ не имеет смысла")
        return None
    tier = raw.get("tier")
    if tier is not None and (isinstance(tier, bool) or not isinstance(tier, int) or tier < 1):
        reasons.append(f"{label}: номер ступени {tier!r} не натуральное число")
        return None
    if tier is None and (above is not None or up_to is not None):
        reasons.append(f"{label}: у ступени {above}–{up_to} м³ нет номера")
        return None
    period = raw.get("tier_period") or None
    if period not in (None,) + TIER_PERIODS or (tier is None and period):
        reasons.append(f"{label}: tier_period {period!r} — ожидалось month или year у ступени")
        return None

    season = (raw.get("season_from") or None, raw.get("season_to") or None)
    if any(season) and not all(value and SEASON.match(str(value)) for value in season):
        reasons.append(f"{label}: сезон {season[0]!r}–{season[1]!r} не в формате MM-DD")
        return None

    return {"tier": tier, "above_m3": above, "up_to_m3": up_to,
            "tier_period": period if tier is not None else None,
            "season_from": season[0], "season_to": season[1], "rate": rate}


def check_plan(raw: dict, scale: float, tax: float, limits: dict, label: str,
               reasons: list) -> dict:
    """One offer: a supplier, a kind of contract or use, and every price printed for it.

    Expects `plan_code`, `name` and `supplier` already set by the caller — they come from config
    or from the page's own table, never from a model's wording. Returns the clean plan or None.
    """
    code = str(raw.get("plan_code") or "").strip()
    where = f"{label}, план {code}"
    if not code or not str(raw.get("supplier") or "").strip():
        reasons.append(f"{where}: у плана нет кода или поставщика")
        return None
    contract, usage, metered = raw.get("contract") or None, raw.get("usage") or None, raw.get("metered")
    if contract not in (None,) + CONTRACTS:
        reasons.append(f"{where}: contract {contract!r} — ожидалось {', '.join(CONTRACTS)} или null")
        return None
    if usage not in (None,) + USAGES:
        reasons.append(f"{where}: usage {usage!r} — ожидалось {', '.join(USAGES)} или null")
        return None
    if metered not in (True, False, None):
        reasons.append(f"{where}: metered {metered!r} — ожидалось true, false или null")
        return None

    rows = []
    for item in raw.get("rates") or []:
        row = check_rate(item, scale, limits, where, reasons) if isinstance(item, dict) else None
        if row is None:
            return None
        rows.append(row)
    if not rows:
        reasons.append(f"{where}: ни одной цены")
        return None
    keys = [tuple(row[k] for k in row if k != "rate") for row in rows]
    if len(set(keys)) != len(keys):
        reasons.append(f"{where}: одна и та же цена встречается дважды")
        return None

    charge = as_number(raw.get("monthly_charge"))
    if charge is not None and charge < 0:
        reasons.append(f"{where}: отрицательная абонентская плата {charge}")
        return None

    return {"plan_code": code, "name": str(raw.get("name") or code), "is_default": False,
            "supplier": str(raw["supplier"]).strip(), "contract": contract, "usage": usage,
            "metered": metered, "monthly_charge": round(charge * tax, 4) if charge else None,
            "rates": sorted(rows, key=lambda r: (r["season_from"] or "", r["tier"] or 0))}


def check_norms(raw, label: str, reasons: list):
    """Consumption norms for a household without a meter. Returns the clean list, an empty list
    when the source prints none, or None when what it printed cannot be trusted."""
    if not raw:
        return []
    if not isinstance(raw, list):
        reasons.append(f"{label}: нормы потребления не являются списком")
        return None
    norms = []
    for item in raw:
        item = item if isinstance(item, dict) else {}
        value = as_number(item.get("value"))
        season_only = item.get("heating_season_only")
        if item.get("usage") not in NORM_USAGES or item.get("basis") not in NORM_BASES \
                or value is None or value <= 0 or season_only not in (True, False):
            reasons.append(f"{label}: норма потребления {item!r} не разбирается")
            return None
        norms.append({"usage": item["usage"], "basis": item["basis"], "value": value,
                      "heating_season_only": season_only})
    if len({(n["usage"], n["basis"]) for n in norms}) != len(norms):
        reasons.append(f"{label}: одна и та же норма потребления встречается дважды")
        return None
    return norms


def _in_season(row: dict, today: date) -> bool:
    if not row["season_from"]:
        return True
    day = today.strftime("%m-%d")
    start, end = row["season_from"], row["season_to"]
    return start <= day <= end if start <= end else (day >= start or day <= end)


def plain_rate(plan: dict, today: date):
    """The price an ordinary household of the plan pays today: the first band, this season."""
    found = [row for row in plan["rates"] if _in_season(row, today)]
    return min(found, key=lambda row: row["tier"] or 0)["rate"] if found else None


def build_city(identity: dict, plans: list, default_code: str, distributor: str,
               distribution_rate, norms: list, norms_decree: str, effective_date: str,
               decree_info: str, previous: dict, limits: dict, label: str, today: date) -> dict:
    """The city as published. Raises Rejected.

    `identity` carries city_code, city_name. The previous record of the city guards against a
    misread: a price that jumps past the configured ratio is refused, and an unchanged tariff
    keeps the date and caption it was first published with — an aggregate page restamps every
    month, and the date should move when the price does.
    """
    if default_code not in [plan["plan_code"] for plan in plans]:
        raise Rejected([f"{label}: нет цены плана по умолчанию «{default_code}»"])
    for plan in plans:
        plan["is_default"] = plan["plan_code"] == default_code
    default = next(plan for plan in plans if plan["is_default"])
    rate = plain_rate(default, today)
    if rate is None:
        raise Rejected([f"{label}: у плана по умолчанию нет цены на сегодняшний сезон"])

    distribution = as_number(distribution_rate) or 0.0
    ceiling = as_number((limits.get(BLOCK) or {}).get("max_rate"))
    if distribution < 0 or (ceiling and distribution > ceiling):
        raise Rejected([f"{label}: тариф доставки {distribution} вне диапазона 0..{ceiling}"])

    was = as_number((previous or {}).get("rate"))
    ratio = as_number((limits.get(BLOCK) or {}).get("max_change_ratio") or limits.get("max_change_ratio"))
    if was and ratio and abs(rate - was) / was > ratio:
        raise Rejected([f"{label}: цена газа изменилась с {was} на {rate}, "
                        f"больше порога {round(ratio * 100)}%"])

    unchanged = was == rate and as_number(previous.get("distribution_rate")) == distribution \
        and previous.get("effective_date") and previous.get("supplier") == default["supplier"]
    return {
        "city_code": identity["city_code"],
        "city_name": identity["city_name"],
        "supplier": default["supplier"],
        "unit": UNIT,
        "rate": rate,
        "distributor": distributor or "",
        "distribution_rate": distribution,
        "effective_date": previous["effective_date"] if unchanged else effective_date,
        "decree_info": clean_decree(previous.get("decree_info") if unchanged else decree_info),
        "plans": plans,
        "norms": norms,
        "norms_decree": clean_decree(norms_decree) if norms else "",
    }


def registry_key(city: dict) -> str:
    """The name a gas city is registered under. Where delivery is billed apart, the network
    operator is what differs between cities — one national supplier sells gas in all of them."""
    return city.get("distributor") or city.get("supplier") or ""


def _period(raw: dict, source: dict, supplier: str, limits: dict, label: str, reasons: list):
    """One dated version of a model's reading, checked. Returns it or None."""
    start = as_date(raw.get("from"))
    end = as_date(raw.get("to")) if raw.get("to") else None
    if not start or (end and end < start):
        reasons.append(f"{label}: даты периода {raw.get('from')!r}–{raw.get('to')!r} не разбираются")
        return None
    unit = raw.get("price_per")
    if unit not in PRICE_UNITS:
        reasons.append(f"{label}: единица цены {unit!r} — ожидалось {', '.join(PRICE_UNITS)}")
        return None
    tax = 1 + (as_number(source.get("vat_percent")) or 0.0) / 100
    scale = tax / PRICE_UNITS[unit]

    configured = source.get("plans") or {}
    plans = []
    for item in raw.get("plans") or []:
        code = str((item or {}).get("plan") or "").strip()
        if code not in configured:
            reasons.append(f"{label}: план «{code}» не объявлен в конфиге")
            return None
        declared = configured[code] or {}
        plan = check_plan({**item, "plan_code": code, "name": declared.get("name") or code,
                           "supplier": declared.get("supplier") or supplier,
                           "contract": declared.get("contract"), "usage": declared.get("usage"),
                           "metered": declared.get("metered")},
                          scale, tax, limits, label, reasons)
        if plan is None:
            return None
        plans.append(plan)
    if len({plan["plan_code"] for plan in plans}) != len(plans):
        reasons.append(f"{label}: один план встречается дважды")
        return None
    order = list(configured)
    plans.sort(key=lambda plan: order.index(plan["plan_code"]))

    norms = check_norms(raw.get("norms"), label, reasons) if source.get("read_norms") else []
    if norms is None:
        return None
    period = {"from": start.strftime(DATE_FORMAT), "plans": plans, "norms": norms,
              "norms_decree": clean_decree(raw.get("norms_decree")),
              "decree_info": clean_decree(raw.get("decree_info"))}
    if source.get("separate_distribution"):
        rate = as_number(raw.get("distribution_rate"))
        if rate is None:
            reasons.append(f"{label}: не найден тариф на доставку газа")
            return None
        period["distributor"] = str(raw.get("distributor") or "").strip()
        period["distribution_rate"] = round(rate * scale, 5)
    if end:
        period["to"] = end.strftime(DATE_FORMAT)
    return period


def default_plan_of(source: dict) -> str:
    plans = source.get("plans") or {}
    marked = [code for code, plan in plans.items() if (plan or {}).get("default")]
    return marked[0] if marked else next(iter(plans), "")


def read_city(source: dict, identity: dict, supplier: str, currency: str, previous: dict,
              config: dict, extractor, label: str) -> tuple:
    """Fetches, extracts and validates one city's gas source.

    Returns (published city or None, reasons it was not refreshed, the model's raw answer).
    """
    timeout = int((config.get("settings", {}) or {}).get("timeout_seconds") or 30)
    urls = [u for u in (source.get("urls") or [source.get("url")]) if u]
    problems = []
    documents = fetch_all(urls, timeout, bool(source.get("read_images")),
                          source.get("read_documents") or False, problems)
    if not documents:
        return None, [f"{label}: источник не открылся ({'; '.join(problems) or ', '.join(urls)})"], None

    instruction = prompts.gas_prompt(
        identity["city_name"], supplier, currency, source.get("plans") or {},
        hint=source.get("hint", ""), distribution=bool(source.get("separate_distribution")),
        norms=bool(source.get("read_norms")))
    options = {key: source[key] for key in ("model", "json_mode", "extra_params") if key in source}
    extracted = extractor.extract([d.as_llm_part() for d in documents], instruction, options)
    if not isinstance(extracted, dict) or not isinstance(extracted.get("periods"), list) \
            or not extracted["periods"]:
        return None, [f"{label}: тариф не извлечён из источника"], extracted

    limits = config.get("validation", {}) or {}
    reasons, periods = [], []
    for index, raw in enumerate(extracted["periods"]):
        period = _period(raw if isinstance(raw, dict) else {}, source, supplier, limits,
                         f"{label}, период #{index + 1}", reasons)
        if period:
            periods.append(period)
    if reasons:
        return None, reasons, extracted
    if len({p["from"] for p in periods}) != len(periods):
        return None, [f"{label}: два периода начинаются в один день"], extracted

    today = date.today()
    resolved, stale = resolve_periods({"periods": periods}, today, label)
    if stale:
        logger.warning(stale)
    try:
        city = build_city(identity, resolved["plans"], default_plan_of(source),
                          resolved.get("distributor", ""), resolved.get("distribution_rate"),
                          resolved.get("norms") or [], resolved.get("norms_decree", ""),
                          resolved["effective_date"], resolved.get("decree_info", ""),
                          previous or {}, limits, label, today)
    except Rejected as rejection:
        return None, rejection.reasons, extracted
    return city, [], extracted
