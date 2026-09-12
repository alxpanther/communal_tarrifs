"""Armenia (AM).

Tariffs are collected city by city by the shared per-city pipeline; the sources live in
config/am/sources.json. Electricity comes from the tariff table of Electric Networks of
Armenia, water from Veolia Jur — one tariff for the whole country, so every city in the
registry reads the same pages.

Armenia has no district heating or centralised hot water for households, so those two
blocks stay empty by design.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "AM"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
