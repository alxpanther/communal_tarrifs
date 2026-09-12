"""Moldova (MD).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/md/sources.json. Electricity and heat come from ANRE's "tariffs in force" tables,
water from each utility's own page, because ANRE's consolidated water table prints the
figures without the date or the decision they rest on.

Household utilities are exempt from VAT in Moldova, so the "fără TVA" figures the regulator
publishes are what a household actually pays.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "MD"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
