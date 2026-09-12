"""Georgia (GE).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/ge/sources.json. Both of them are the regulator's own pages: GNERC publishes end
user electricity tariffs per supplier and the water tariffs of Georgian Water and Power,
which serves Tbilisi.

Georgian households have no district heating or centralised hot water, so those two blocks
stay empty by design.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "GE"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
