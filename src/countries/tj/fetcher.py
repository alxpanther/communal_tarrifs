"""Tajikistan (TJ).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/tj/sources.json. Only electricity is collected: the ministry of energy publishes the
government's tariff decision as a scan of its pages, so the source is the stable page and
`read_images` hands the scan to the vision model.

Water, hot water and heating for Dushanbe have no readable source yet — the utility's own
site serves an expired certificate with a weak key, and the city hall publishes only
housing-fund and waste tariffs. Those blocks keep their previous values and every run
reports them as not refreshed.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "TJ"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
