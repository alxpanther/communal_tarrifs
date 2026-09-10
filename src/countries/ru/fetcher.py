"""Russia (RU).

Tariffs are regulated city by city, so there is no single table to scrape: every city
declares its own sources in config/ru/sources.json and the shared pipeline in
common/ai_pipeline.py reads them one by one. This module only names the country.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "RU"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
