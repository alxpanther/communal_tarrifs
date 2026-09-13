"""Uzbekistan (UZ).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/uz/sources.json. Water tariffs of every region come from the JSON the national water company
Uzsuvtaminot serves its tariff page from; electricity from the tariff calculator of Regional
Electric Networks; Tashkent's heating from Veolia Energy Tashkent's news feed.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "UZ"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
