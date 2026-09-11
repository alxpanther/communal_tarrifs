"""Checks an extracted tariff before it is allowed anywhere near the published file.

The model that reads a source page is the weakest link in the pipeline: it can misread a
column, pick the tariff of the wrong year, invent a plausible number for a page that never
loaded, or quietly return a zero. None of that looks like an error — it looks like data.
So every extracted record is checked here, and a record that fails is dropped whole: the
city keeps whatever was published before and the failure is reported.

Every limit comes from `validation` in config/<cc>/sources.json. Nothing about a country,
a currency or a plausible price is written in this file.
"""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"

# Fields each block must end up with, beyond the identity fields every record shares.
BLOCK_FIELDS = {
    "water": ("water_supply", "sewage", "total_rate"),
    "hot_water": ("rate",),
    "heating": ("rate_gcal", "rate_gcal_hour"),
}

# Which extracted field each block's limit applies to.
BLOCK_LIMITS = {
    "water": {"water_supply": "max_rate", "sewage": "max_rate", "total_rate": "max_rate"},
    "hot_water": {"rate": "max_rate"},
    "heating": {"rate_gcal": "max_rate_gcal", "rate_gcal_hour": "max_rate_gcal_hour"},
}

# A standing charge is legitimately zero on a single-rate heat tariff; every other tariff
# reaching zero means the extraction failed, however confident the model sounded.
MAY_BE_ZERO = ("rate_gcal_hour",)


class Rejected(Exception):
    """One city's extraction cannot be trusted. Carries the reasons, in Russian."""

    def __init__(self, reasons: list):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def as_number(value):
    """Parses a rate the way a page prints it: '2 899,98', '2899.98 руб.', 2899.98."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).strip().replace("\xa0", "").replace(" ", "")
    cleaned = cleaned.replace(",", ".")
    kept = "".join(ch for ch in cleaned if ch.isdigit() or ch in ".-")
    if kept.count(".") > 1:
        head, _, tail = kept.rpartition(".")
        kept = head.replace(".", "") + "." + tail
    try:
        return float(kept)
    except ValueError:
        return None


def as_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), DATE_FORMAT).date()
    except ValueError:
        return None


def clean_decree(text) -> str:
    """A decree reference spelled the same way on every run.

    The model varies spacing, letter case and quote escaping from one run to the next — one run
    returned the quotes already escaped, which would have shown backslashes in the app. Every
    variant is a caption that changes for no reason and a commit that carries no news.
    """
    cleaned = str(text or "").replace('\\"', '"').replace("\\", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"(\S)-\s+(\d)", r"\1-\2", cleaned)
    return cleaned[:1].upper() + cleaned[1:]


def normalize_supplier(name: str) -> str:
    """Supplier names differ between a decree and a web page in quotes, case and form."""
    return "".join(ch.lower() for ch in str(name or "") if ch.isalnum())


def strip_qualifier(name: str) -> str:
    """Drops the parenthesised part of a company name.

    Config qualifies a name by city to keep it unique inside a country — ПАО "Т Плюс"
    supplies heat in more than one of them — while a decree qualifies the same company by
    where it is registered. Neither qualifier says anything about which company it is.
    """
    return re.sub(r"\([^)]*\)", " ", str(name or ""))


# Legal forms, spelled out and abbreviated, as they open a company name. They carry no
# information about which company it is: a decree writes the form out in full where a web
# page abbreviates it, and comparing the names without stripping it finds no match at all.
LEGAL_FORMS = (
    "публичноеакционерноеобщество", "акционерноеобщество",
    "обществосограниченнойответственностью",
    "муниципальноеунитарноепредприятие", "государственноеунитарноепредприятие",
    "муниципальноеказенноепредприятие", "муниципальноепредприятие",
    "коммунальнеpідприємство", "комунальнепідприємство",
    "пао", "оао", "зао", "ао", "ооо", "муп", "гуп", "мкп", "мп", "кп",
)


def strip_legal_form(normalized: str) -> str:
    """Removes the legal form from the front of an already normalized name."""
    for form in sorted(LEGAL_FORMS, key=len, reverse=True):
        if normalized.startswith(form) and len(normalized) > len(form):
            return normalized[len(form):]
    return normalized


def same_supplier(expected: str, found: str) -> bool:
    """Whether the source names the company config expects.

    A company writes itself short on its own site — «МУП «Водоканал»» — and long in a
    decree — «МУП "Водоканал г. Екатеринбурга"». One name containing the other is the same
    company; two unrelated names share no such prefix, which is what has to be caught.
    """
    left = strip_legal_form(normalize_supplier(strip_qualifier(expected)))
    right = strip_legal_form(normalize_supplier(strip_qualifier(found)))
    if not left or not right:
        return True
    return left in right or right in left


def fold_hot_water(period: dict, reasons: list, label: str):
    """Turns a two-component hot water tariff into one price per m3.

    Russia and several of its neighbours price hot water as a carrier component (per m3)
    plus an energy component (per Gcal), which only becomes a price per m3 once multiplied
    by the regional norm for heating one m3. The arithmetic is done here rather than by the
    model: a number the code computed can be checked, a number the model computed cannot.

    The published schema carries a single `rate`, so the components stay in the record for
    the decree caption and for the day the app learns to bill them properly.
    """
    water = as_number(period.get("component_water"))
    energy = as_number(period.get("component_energy"))
    norm = as_number(period.get("heat_norm"))
    if water is None or energy is None or norm is None:
        return None

    if not 0 < norm < 1:
        reasons.append(f"{label}: норматив подогрева {norm} Гкал/м³ вне разумного диапазона")
        return None

    folded = round(water + energy * norm, 2)
    stated = as_number(period.get("rate"))
    if stated is not None and abs(stated - folded) > max(0.05, folded * 0.01):
        reasons.append(f"{label}: заявленный тариф {stated} не сходится с расчётным {folded}")
        return None
    return folded


def _check_period(block: str, period: dict, limits: dict, label: str, reasons: list) -> dict:
    """Validates one dated version of a tariff. Returns the clean period or None."""
    start = as_date(period.get("from"))
    if not start:
        reasons.append(f"{label}: период без разбираемой даты начала ('from')")
        return None
    end = as_date(period.get("to")) if period.get("to") else None
    if end and end < start:
        reasons.append(f"{label}: период заканчивается {end} раньше начала {start}")
        return None

    starts = limits.get("period_starts")
    if starts and start.strftime("%m-%d") not in starts:
        # Regulators start tariff periods on a handful of fixed days. Any other start is a misread
        # date — the model once turned "по 30.09.2026" into a period "from 1 September".
        reasons.append(f"{label}: период начинается {start}, а тарифы здесь с такой даты не "
                       f"начинаются (допустимо: {', '.join(starts)})")
        return None

    clean = {"from": start.strftime(DATE_FORMAT)}
    if end:
        clean["to"] = end.strftime(DATE_FORMAT)

    values = dict(period)
    if block == "hot_water":
        folded = fold_hot_water(period, reasons, label)
        if folded is not None:
            values["rate"] = folded
        for key in ("component_water", "component_energy", "heat_norm"):
            if as_number(period.get(key)) is not None:
                clean[key] = as_number(period.get(key))

    if block == "water":
        # The total is arithmetic, so the code does it. Asking the model to add two numbers
        # invites it to "correct" a sum that does not add up, which is exactly the mistake
        # worth catching. When the source does print a total, it is checked below instead.
        supply = as_number(values.get("water_supply"))
        sewage = as_number(values.get("sewage"))
        if as_number(values.get("total_rate")) is None and supply is not None and sewage is not None:
            values["total_rate"] = round(supply + sewage, 4)

    if block == "heating" and values.get("rate_gcal_hour_in_thousands") is True:
        # The schema carries the standing charge in currency units; decrees print it in thousands.
        # The model only reports which, so the multiplication stays checkable.
        standing = as_number(values.get("rate_gcal_hour"))
        if standing is not None:
            values["rate_gcal_hour"] = round(standing * 1000, 2)

    block_limits = limits.get(block, {}) or {}
    for field in BLOCK_FIELDS[block]:
        number = as_number(values.get(field))
        if number is None:
            if field == "rate_gcal_hour":
                number = 0.0
            else:
                reasons.append(f"{label}: поле {field} отсутствует или не число")
                return None
        if number < 0:
            reasons.append(f"{label}: отрицательный тариф {field}={number}")
            return None
        if number == 0 and field not in MAY_BE_ZERO:
            reasons.append(f"{label}: нулевой тариф {field}")
            return None
        ceiling = as_number(block_limits.get(BLOCK_LIMITS[block][field]))
        if ceiling and number > ceiling:
            reasons.append(f"{label}: {field}={number} выше допустимого предела {ceiling}")
            return None
        clean[field] = round(number, 4)

    if block == "water":
        tolerance = as_number(limits.get("sum_tolerance")) or 0.0
        total = clean["water_supply"] + clean["sewage"]
        if abs(total - clean["total_rate"]) > tolerance:
            reasons.append(
                f"{label}: {clean['water_supply']} + {clean['sewage']} = {round(total, 2)}, "
                f"а в total_rate {clean['total_rate']}"
            )
            return None

    if block == "heating":
        kind = str(period.get("tariff_type") or "").strip()
        clean["tariff_type"] = kind if kind in ("one_rate", "two_rate") else "one_rate"

    decree = str(period.get("decree_info") or "").strip()
    if not decree:
        reasons.append(f"{label}: не указано основание тарифа (decree_info)")
        return None
    clean["decree_info"] = clean_decree(decree)
    return clean


def _check_against_previous(block: str, periods: list, previous: dict, limits: dict,
                            label: str, reasons: list):
    """Guards against a confident but wrong extraction by comparing with what was published.

    A regulated tariff moves by percents a year. A jump by a multiple means the model read
    another column, another year or another city — the one failure mode that passes every
    other check, because the number itself is perfectly plausible.
    """
    ratio = as_number(limits.get("max_change_ratio"))
    if not ratio or not previous:
        return

    field = BLOCK_FIELDS[block][-1] if block == "water" else BLOCK_FIELDS[block][0]
    was = as_number(previous.get("total_rate" if block == "water" else field))
    if not was:
        return

    # The period in force today is the one comparable with what is published today.
    today = datetime.now().date()
    current = [p for p in periods if as_date(p["from"]) <= today]
    now = as_number((current[-1] if current else periods[0]).get(
        "total_rate" if block == "water" else field))
    if not now:
        return

    change = abs(now - was) / was
    if change > ratio:
        reasons.append(
            f"{label}: тариф изменился с {was} на {now} — на {round(change * 100)}%, "
            f"порог {round(ratio * 100)}%"
        )


def _check_same_period(block: str, periods: list, previous: dict, limits: dict,
                       label: str, reasons: list):
    """An already published period must come back with the same number.

    A regulator does not reprice a period it has already set. A different number for the
    same dates means the model read another column — the tariff without VAT, another year,
    another consumer group — and nothing else gives that away: the wrong number is still a
    real tariff from a real document, and usually within a few percent of the right one.
    So the tolerance here is a rounding margin, not an allowance for indexation.
    """
    tolerance = as_number(limits.get("same_period_tolerance"))
    if tolerance is None or not previous:
        return
    since = previous.get("effective_date")
    field = "total_rate" if block == "water" else BLOCK_FIELDS[block][0]
    was = as_number(previous.get(field))
    if not since or not was:
        return
    for period in periods:
        if period["from"] != since:
            continue
        now = as_number(period.get(field))
        if now and abs(now - was) / was > tolerance:
            reasons.append(
                f"{label}: период с {since} уже опубликован со значением {was}, а извлечено "
                f"{now} — вероятно, прочитана не та колонка или не та строка"
            )
        return


def validate_city(block: str, code: str, identity: dict, extracted: dict,
                  previous: dict, limits: dict) -> dict:
    """Checks one city's extraction. Returns a record with periods, or raises Rejected.

    `identity` is what config declares about the city — its name and, optionally, the
    supplier we expect to find. `previous` is the city as published last time, used only
    to catch an implausible jump.
    """
    reasons = []
    label = identity.get("label") or identity.get("city_name") or code

    if not isinstance(extracted, dict):
        raise Rejected([f"{label}: модель не вернула объект"])

    raw_periods = extracted.get("periods")
    if not isinstance(raw_periods, list) or not raw_periods:
        raise Rejected([f"{label}: модель не вернула ни одного периода действия тарифа"])

    expected = identity.get("supplier")
    # An abbreviation cannot be matched against its expansion — «АО "ЕТК"» against
    # «Екатеринбургская теплосетевая компания» — so config may list how the source spells
    # the same company. The canonical name still goes into the file and the registry.
    accepted = [expected] + list(identity.get("aliases") or [])
    found = extracted.get("supplier")
    if expected and found and not any(same_supplier(name, found) for name in accepted if name):
        reasons.append(f"{label}: источник называет поставщика «{found}», ожидался «{expected}»")

    periods = []
    for index, raw in enumerate(raw_periods):
        if not isinstance(raw, dict):
            reasons.append(f"{label}: период #{index + 1} не является объектом")
            continue
        clean = _check_period(block, raw, limits, f"{label}, период #{index + 1}", reasons)
        if clean:
            periods.append(clean)

    if not periods:
        reasons.append(f"{label}: не осталось ни одного пригодного периода")
        raise Rejected(reasons)

    periods.sort(key=lambda p: p["from"])
    starts = [p["from"] for p in periods]
    if len(set(starts)) != len(starts):
        reasons.append(f"{label}: два периода начинаются в один день")

    # A source that lists only future periods has no tariff in force today. Publishing its
    # first period now would put an October tariff in front of a user in September.
    today = datetime.now().date()
    if not any(as_date(p["from"]) <= today for p in periods):
        reasons.append(f"{label}: в источнике только будущие периоды, первый с {periods[0]['from']} — "
                       f"действующего на сегодня тарифа нет")

    _check_against_previous(block, periods, previous or {}, limits, label, reasons)
    _check_same_period(block, periods, previous or {}, limits, label, reasons)

    if reasons:
        raise Rejected(reasons)

    record = {"city_name": identity["city_name"], "periods": periods}
    if expected:
        record["supplier"] = expected
    elif found:
        record["supplier"] = str(found).strip()
    else:
        raise Rejected([f"{label}: не удалось определить поставщика"])
    return record
