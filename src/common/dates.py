"""Dates written out in words, the way decrees and supplier pages print them.

Ukrainian and Russian legal texts spell a date with the month in the genitive case —
«з 01 жовтня 2026 року», «с 1 апреля 2023 года». Every reader of such a text needs the same
two tables, so they live here once.
"""

import re
from datetime import date

# Ukrainian month names in the genitive case.
UK_MONTHS_GENITIVE = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}

# Russian month names in the genitive case.
RU_MONTHS_GENITIVE = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# A date as printed: «01 жовтня 2026», «1 апреля 2023» or «29.09.2026».
WRITTEN_DATE = r"\d{1,2}\s+[^\W\d_]+\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{4}"

_IN_WORDS = re.compile(r"^(\d{1,2})\s+([^\W\d_]+)\s+(\d{4})$")
_IN_DIGITS = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def parse_written_date(text: str, months: dict):
    """A date matched by WRITTEN_DATE, or None when it does not name a real day."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    words = _IN_WORDS.match(value)
    digits = _IN_DIGITS.match(value)
    if words:
        day, month, year = int(words.group(1)), months.get(words.group(2).lower()), int(words.group(3))
    elif digits:
        day, month, year = (int(group) for group in digits.groups())
    else:
        return None
    try:
        return date(year, month, day) if month else None
    except ValueError:
        return None
