"""The price a household is paid for electricity it exports to the grid (`grid_export`).

One country-wide block, the same way `electricity` is: Ukraine's «green» tariff is set by NKREKP
for the whole country, Uzbekistan's «Солнечный дом» subsidy by a presidential resolution. Both
pipelines call collect() — the Ukrainian fetcher and the per-city pipeline alike — so the checks
and the published shape cannot drift apart between countries.

Config (`grid_export` in config/<cc>/sources.json) names the pages, the reader of their wording
and the settlement scheme; it holds no rate. Every page is read by code
(`common/grid_export_readers.py`), never by a model. When config lists several pages, each is
read on its own: the newest act wins, and two pages printing the same act with different numbers
reject the run — a free cross-check of the reader.

A failure keeps the published block and says why; a country with no `grid_export` in config
gets the empty block.
"""

import logging
from datetime import date

from common.electricity import SUBUNITS_PER_UNIT
from common.fetching import fetch
from common.grid_export_readers import READERS
from common.jsonio import GRID_EXPORT, empty_grid_export_block
from common.validation import DATE_FORMAT, Rejected, as_number

logger = logging.getLogger(__name__)

# Kinds of station a rate row may name. `solar` is a solar station of any placement — a rule that
# does not split them; `solar_roof` is a rule only for stations on roofs and facades.
STATION_TYPES = ("solar", "solar_roof", "wind", "wind_solar")

# How the exported energy is settled. "monthly_surplus": the month's export minus import, a
# positive difference paid at the rate.
SCHEMES = ("monthly_surplus",)

# Fields of a published rate row, in the order they are written.
ROW_FIELDS = ("station_type", "max_capacity_kw", "commissioned_from", "commissioned_to", "rate",
              "vat_included", "valid_from", "valid_to")


def _row_key(row: dict) -> tuple:
    """What identifies one rate across runs: the same station bought at the same time."""
    return row["station_type"], row["max_capacity_kw"], row["commissioned_from"]


def _published_rows(reading: dict) -> list:
    """Rows in the published shape: the rate in whole currency units, the validity of the act."""
    rows = []
    for raw in reading["rates"]:
        rate = as_number(raw.get("rate"))
        if rate is not None and raw.get("in_subunits"):
            rate = rate / SUBUNITS_PER_UNIT
        rows.append({
            "station_type": raw.get("station_type") or "",
            "max_capacity_kw": as_number(raw.get("max_capacity_kw")),
            "commissioned_from": raw.get("commissioned_from") or "",
            "commissioned_to": raw.get("commissioned_to") or "",
            "rate": round(rate, 4) if rate is not None else None,
            "vat_included": bool(raw.get("vat_included")),
            # An act sets its rates until the next act replaces it, and none prints that day.
            "valid_from": reading["valid_from"],
            "valid_to": "",
        })
    return rows


def _overlap(first: dict, second: dict) -> bool:
    """Whether two commissioning periods share a day; an empty bound is open-ended."""
    starts_before_end = not second["commissioned_to"] or \
        first["commissioned_from"] <= second["commissioned_to"]
    ends_after_start = not first["commissioned_to"] or \
        first["commissioned_to"] >= second["commissioned_from"]
    return starts_before_end and ends_after_start


def validate(rows: list, limits: dict, label: str) -> list:
    """Reasons the rows may not be published; empty when they may."""
    if not rows:
        return [f"{label}: ни одной ставки"]
    reasons = []
    ceiling = as_number(limits.get("max_rate"))
    for row in rows:
        where = f"{label}, {row['station_type'] or '?'} {row['commissioned_from'] or '—'}"
        if row["station_type"] not in STATION_TYPES:
            reasons.append(f"{where}: тип станции «{row['station_type']}» не из {', '.join(STATION_TYPES)}")
        if not row["max_capacity_kw"] or row["max_capacity_kw"] <= 0:
            reasons.append(f"{where}: предел мощности {row['max_capacity_kw']!r} не положительное число")
        if row["rate"] is None or row["rate"] <= 0:
            reasons.append(f"{where}: ставка {row['rate']!r} не положительное число")
        elif ceiling and row["rate"] > ceiling:
            reasons.append(f"{where}: ставка {row['rate']} выше предела {ceiling}")
        if row["commissioned_from"] and row["commissioned_to"] and \
                row["commissioned_from"] > row["commissioned_to"]:
            reasons.append(f"{where}: период ввода {row['commissioned_from']}–{row['commissioned_to']} "
                           f"не имеет смысла")
    for index, row in enumerate(rows):
        for other in rows[index + 1:]:
            same_kind = (row["station_type"], row["max_capacity_kw"]) == \
                (other["station_type"], other["max_capacity_kw"])
            if same_kind and _overlap(row, other):
                reasons.append(f"{label}: у {row['station_type']} до {row['max_capacity_kw']} кВт "
                               f"пересекаются периоды ввода с {row['commissioned_from'] or '—'} "
                               f"и с {other['commissioned_from'] or '—'}")
    return reasons


def _check_against_previous(rows: list, previous: dict, limits: dict, label: str) -> list:
    """A rate that jumped beyond `max_change_ratio` was read from the wrong row or column."""
    ratio = as_number(limits.get("max_change_ratio"))
    if not ratio:
        return []
    was = {_row_key(row): as_number(row.get("rate")) for row in (previous or {}).get("rates", [])}
    reasons = []
    for row in rows:
        old = was.get(_row_key(row))
        if old and abs(row["rate"] - old) / old > ratio:
            reasons.append(f"{label}: ставка {row['station_type']} {row['commissioned_from'] or '—'} "
                           f"изменилась с {old} на {row['rate']}, больше порога {round(ratio * 100)}%")
    return reasons


def _limits_of(config: dict) -> dict:
    """The block's own limits, with the country's change ratio when the block sets none."""
    validation = config.get("validation") or {}
    limits = dict(validation.get(GRID_EXPORT) or {})
    limits.setdefault("max_change_ratio", validation.get("max_change_ratio"))
    return limits


def _read_sources(section: dict, timeout: int, label: str) -> tuple:
    """(url, reading) of every page that could be read, and why the others could not."""
    reader = READERS.get(section.get("reader"))
    if not reader:
        return [], [f"{label}: неизвестный reader «{section.get('reader')}», "
                    f"ожидался один из {', '.join(READERS)}"]
    readings, reasons = [], []
    for url in section.get("urls") or []:
        problems = []
        document = fetch(url, timeout, problems)
        if not document.text:
            reasons.append(f"{label}: источник не открылся ({'; '.join(problems) or url})")
            continue
        try:
            readings.append((url, reader(document.text, f"{label} {url}")))
        except Rejected as rejection:
            reasons.extend(rejection.reasons)
    return readings, reasons


def collect(config: dict, previous: dict, label: str, today: date = None) -> tuple:
    """Reads the block from its sources. Returns (block to publish, refreshed, reasons).

    `refreshed` is True when the sources were read and passed every check; otherwise the
    previous block is returned unchanged and `reasons` says why.
    """
    section = config.get(GRID_EXPORT)
    if not section:
        return empty_grid_export_block(), False, []
    previous = previous or empty_grid_export_block()
    today = today or date.today()

    scheme = section.get("scheme")
    if scheme not in SCHEMES:
        return previous, False, [f"{label}: scheme «{scheme}» не из {', '.join(SCHEMES)}"]

    timeout = int((config.get("settings") or {}).get("timeout_seconds") or 30)
    readings, reasons = _read_sources(section, timeout, label)
    if not readings:
        return previous, False, reasons or [f"{label}: в конфиге нет ни одного источника"]

    newest = max(reading["valid_from"] for _, reading in readings)
    current = [(url, reading) for url, reading in readings if reading["valid_from"] == newest]
    url, reading = current[0]
    rows = _published_rows(reading)
    for other_url, other in current[1:]:
        if _published_rows(other) != rows or other["decree_info"] != reading["decree_info"]:
            return previous, False, [f"{label}: {url} и {other_url} печатают один документ "
                                     f"с разными ставками"]

    limits = _limits_of(config)
    rejected = validate(rows, limits, label) or _check_against_previous(rows, previous, limits, label)
    if rejected:
        return previous, False, rejected
    # A source that stayed behind is no failure: the newer page has been read.
    for reason in reasons:
        logger.warning(f"{label}: {reason}")

    tax = reading["income_tax_percent"]
    return {
        "source_url": url,
        "update_date": today.strftime(DATE_FORMAT),
        "scheme": scheme,
        "unit": "kWh",
        "decree_info": reading["decree_info"],
        "income_tax_percent": float(tax) if tax is not None else 0.0,
        "income_tax_info": reading["income_tax_info"] if tax is not None else "",
        "rates": [{field: row[field] for field in ROW_FIELDS} for row in rows],
    }, True, []


def same_block(before: dict, after: dict) -> bool:
    """Whether a refreshed block says what was published, apart from the day it was checked."""
    def strip(block):
        return {key: value for key, value in (block or {}).items() if key != "update_date"}
    return strip(before) == strip(after)
