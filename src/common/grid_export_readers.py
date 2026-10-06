"""Readers of the documents that set the price of electricity a household exports to the grid.

The price is read by code, not by a model: each regulator prints it in a fixed legal wording
that is re-issued unchanged with new numbers, so a reader keyed to that wording costs nothing
to run and cannot invent a number. Config names the reader of a country's source
(`grid_export.reader`); the reader returns what one page says, and `common/grid_export.py`
decides whether it may be published.

A reader returns a dict, or raises Rejected with the reasons in Russian:

    decree_info          the act the rates rest on, spelled the same way on every run
    valid_from           the day the rates took effect, YYYY-MM-DD
    income_tax_percent   tax withheld from the income, or None when the page does not say
    income_tax_info      what the percent is, as printed; empty when the page does not say
    rates                rows: station_type, max_capacity_kw, commissioned_from,
                         commissioned_to, rate (as printed), in_subunits, vat_included

The wording each reader relies on is in the constants next to it. When a regulator rewords
its text the reader rejects the page instead of guessing, and those constants are the one
thing to update.
"""

import re

from common.dates import RU_MONTHS_GENITIVE, UK_MONTHS_GENITIVE, WRITTEN_DATE, parse_written_date
from common.validation import DATE_FORMAT, Rejected, as_number

# A printed price: «1 848,52», «1848,52», «613,40», «1 000».
PRINTED_NUMBER = r"\d+(?: \d{3})*(?:,\d+)?"


def _flat(text: str) -> str:
    """Page text on one line: the same sentence is split over lines differently on every site."""
    return re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()


def _iso(value, months: dict, label: str, reasons: list) -> str:
    parsed = parse_written_date(value, months)
    if not parsed:
        reasons.append(f"{label}: дата «{value}» не разбирается")
        return ""
    return parsed.strftime(DATE_FORMAT)


# --- Ukraine: NKREKP resolution «Про встановлення «зелених» тарифів … приватних домогосподарств»

# The heading suppliers put above the table they reprint: «затверджених постановою НКРЕКП від
# 29.09.2026 № 1613» or «… від 29 вересня 2026 року № 1613». A page may keep every past edition,
# newest first or last, so each heading opens a section of its own.
NKREKP_HEADING = re.compile(
    rf"постанов\w* НКРЕКП від (?P<date>{WRITTEN_DATE})(?: року)? №\s*(?P<number>\d+)")
# The day the resolution takes effect: its own last clause, or the date right after the heading.
NKREKP_IN_FORCE = re.compile(rf"набирає чинності з (?P<date>{WRITTEN_DATE})")
NKREKP_AFTER_HEADING = re.compile(rf"^:?\s*з (?P<date>{WRITTEN_DATE})")
# One clause of the resolution: the kind of station and its capacity limit.
NKREKP_CAPTION = re.compile(
    r"вироблену з енергії (?P<source>.+?) (?:генеруючими|на комбінованих)"
    r".{0,200}?не перевищує (?P<kw>\d+(?:,\d+)?) кВт")
# One row: the period the station was put into operation, and its rate.
NKREKP_ROW = re.compile(
    rf"з (?P<start>{WRITTEN_DATE}) року по (?P<end>{WRITTEN_DATE}) року\s*[|–—-]?\s*"
    rf"(?P<rate>{PRINTED_NUMBER})")


def _nkrekp_station_type(source: str, rest: str) -> str:
    """The station type of one clause, from the energy it names and its placement."""
    if "вітру та сонця" in source:
        return "wind_solar"
    if "сонячного" in source:
        return "solar_roof" if "дах" in rest else "solar_ground"
    if "вітру" in source:
        return "wind"
    return ""


def _nkrekp_section(text: str, label: str, reasons: list) -> dict:
    """The rates of one edition of the resolution, from the text below its heading."""
    in_force = NKREKP_IN_FORCE.search(text) or NKREKP_AFTER_HEADING.search(text)
    if not in_force:
        reasons.append(f"{label}: не напечатана дата вступления постановления в силу")
        return {}
    valid_from = _iso(in_force.group("date"), UK_MONTHS_GENITIVE, label, reasons)

    if "коп/кВт" in text:
        in_subunits = True
    elif "грн/кВт" in text:
        in_subunits = False
    else:
        reasons.append(f"{label}: не сказано, в копейках или гривнах ставки")
        return {}
    if "без ПДВ" in text:
        vat_included = False
    elif "з ПДВ" in text:
        vat_included = True
    else:
        reasons.append(f"{label}: не сказано, с НДС ли ставки")
        return {}

    captions = list(NKREKP_CAPTION.finditer(text))
    rows = list(NKREKP_ROW.finditer(text))
    if rows and (not captions or rows[0].start() < captions[0].start()):
        reasons.append(f"{label}: строка тарифа без заголовка с типом станции")
        return {}

    rates = []
    for index, caption in enumerate(captions):
        end = captions[index + 1].start() if index + 1 < len(captions) else len(text)
        own = [row for row in rows if caption.end() <= row.start() < end]
        # What the clause says after the capacity limit, up to its first row: «за умови їх
        # розташування на дахах» is what tells a roof station from a ground one.
        rest = text[caption.end():own[0].start() if own else end]
        station = _nkrekp_station_type(caption.group("source"), rest)
        if not station:
            reasons.append(f"{label}: незнакомый тип станции «{caption.group('source')}»")
            continue
        if not own:
            reasons.append(f"{label}: у пункта «{caption.group('source')}» нет ни одной ставки")
            continue
        for row in own:
            rates.append({
                "station_type": station,
                "max_capacity_kw": as_number(caption.group("kw")),
                "commissioned_from": _iso(row.group("start"), UK_MONTHS_GENITIVE, label, reasons),
                "commissioned_to": _iso(row.group("end"), UK_MONTHS_GENITIVE, label, reasons),
                "rate": as_number(row.group("rate")),
                "in_subunits": in_subunits,
                "vat_included": vat_included,
            })
    return {"valid_from": valid_from, "rates": rates}


def read_nkrekp_green_tariff(text: str, label: str) -> dict:
    """The household «green» tariff as a supplier reprints the NKREKP resolution.

    Universal service suppliers print it as a table under «затверджених постановою НКРЕКП від …»
    or as the clauses of the resolution word for word. Where a page keeps past editions too,
    the one with the latest date is read; which end of the page is the newest differs from
    site to site, so no position is trusted.
    """
    flat = _flat(text)
    headings = list(NKREKP_HEADING.finditer(flat))
    if not headings:
        raise Rejected([f"{label}: на странице нет постановления НКРЕКП о «зелёных» тарифах"])

    reasons = []
    editions = []
    for index, heading in enumerate(headings):
        signed = parse_written_date(heading.group("date"), UK_MONTHS_GENITIVE)
        if not signed:
            reasons.append(f"{label}: дата постановления «{heading.group('date')}» не разбирается")
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(flat)
        editions.append((signed, heading, flat[heading.end():end]))
    if not editions:
        raise Rejected(reasons)

    signed, heading, section = max(editions, key=lambda edition: edition[0])
    reading = _nkrekp_section(section, label, reasons)
    if reasons:
        raise Rejected(reasons)
    reading["decree_info"] = (f"Постанова НКРЕКП від {signed.strftime('%d.%m.%Y')} "
                              f"№ {heading.group('number')}")
    # No supplier page prints the tax on the household's income, so it is left to the user.
    reading["income_tax_percent"] = None
    reading["income_tax_info"] = ""
    return reading


# --- Uzbekistan: presidential resolution ПП-57, programme «Солнечный дом», on lex.uz

# The act as lex.uz names it: «Постановление Президента Республики Узбекистан, от 16.02.2023 г.
# № ПП-57».
LEX_UZ_ACT = re.compile(
    r"(?P<kind>Постановление Президента Республики Узбекистан), от (?P<date>\d{2}\.\d{2}\.\d{4}) г\. "
    r"№ (?P<number>ПП-\d+)")
LEX_UZ_PROGRAMME = "«Солнечный дом»"
# A numbered item of the act: « 15. Начиная с …». The programme is one item.
LEX_UZ_ITEM = re.compile(r"(?:^| )\d{1,2}\. (?=[А-ЯЁ])")
LEX_UZ_START = re.compile(rf"[Нн]ачиная с (?P<date>{WRITTEN_DATE}) года")
LEX_UZ_CAPACITY = re.compile(r"мощность до (?P<kw>\d+(?:,\d+)?) кВт")
LEX_UZ_RATE = re.compile(rf"киловатт/час .{{0,300}}? по (?P<rate>{PRINTED_NUMBER}) сум")
LEX_UZ_TAX_FREE = re.compile(r"[^;:.]*не включаются в состав совокупного дохода[^;:.]*")
# What lex.uz prints between the paragraphs of every act: its own buttons and the classifier
# codes of the paragraph. Not part of the text.
LEX_UZ_NOISE = re.compile(
    r"Предложения по документу Прослушать аудио Получить ссылку из элемента документа|\[ ОКОЗ:[^\]]*\]")


def read_lex_uz_solar_house(text: str, label: str) -> dict:
    """The «Солнечный дом» subsidy per kWh a household passes to the grid, from the consolidated
    text of the resolution that set it up. lex.uz keeps the text of an act current with every
    amendment at the same address, so a new rate written into the act arrives on its own."""
    flat = _flat(LEX_UZ_NOISE.sub(" ", _flat(text)))
    act = LEX_UZ_ACT.search(flat)
    position = flat.find(LEX_UZ_PROGRAMME)
    if not act or position < 0:
        raise Rejected([f"{label}: на странице нет постановления о программе {LEX_UZ_PROGRAMME}"])

    starts = [item.start() for item in LEX_UZ_ITEM.finditer(flat, 0, position)]
    following = LEX_UZ_ITEM.search(flat, position)
    item = flat[starts[-1] if starts else position:following.start() if following else len(flat)]

    reasons = []
    start = LEX_UZ_START.search(item)
    capacity = LEX_UZ_CAPACITY.search(item)
    rate = LEX_UZ_RATE.search(item)
    if not start:
        reasons.append(f"{label}: не напечатана дата начала программы")
    if not capacity:
        reasons.append(f"{label}: не напечатан предел мощности станции")
    if not rate:
        reasons.append(f"{label}: не напечатана сумма за кВт·ч")
    if "солнечных панел" not in item:
        reasons.append(f"{label}: программа больше не говорит о солнечных панелях")
    if reasons:
        raise Rejected(reasons)
    valid_from = _iso(start.group("date"), RU_MONTHS_GENITIVE, label, reasons)
    if reasons:
        raise Rejected(reasons)

    tax_free = LEX_UZ_TAX_FREE.search(item)
    tax_info = _flat(tax_free.group(0)) if tax_free else ""
    return {
        "decree_info": f"{act.group('kind')} от {act.group('date')} № {act.group('number')}",
        "valid_from": valid_from,
        "income_tax_percent": 0.0 if tax_info else None,
        "income_tax_info": tax_info[:1].upper() + tax_info[1:],
        # The programme pays for the surplus of any station within the limit, whenever it was
        # built, so the row has no commissioning period. A subsidy is not a sale: no VAT.
        "rates": [{
            "station_type": "solar",
            "max_capacity_kw": as_number(capacity.group("kw")),
            "commissioned_from": "",
            "commissioned_to": "",
            "rate": as_number(rate.group("rate")),
            "in_subunits": False,
            "vat_included": False,
        }],
    }


# Config value of `grid_export.reader` -> the function reading that kind of document.
READERS = {
    "nkrekp_green_tariff": read_nkrekp_green_tariff,
    "lex_uz_solar_house": read_lex_uz_solar_house,
}
