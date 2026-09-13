"""Belarus (BY).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/by/sources.json. Water tariffs are set by each oblast executive committee and read
from the city's own водоканал. Heat and electricity tariffs for households are set by the
Council of Ministers for the whole republic and read from the national energy association,
Belenergo, which attaches them to its page as PDFs.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "BY"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
