"""Kyrgyzstan (KG).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/kg/sources.json. Electricity comes from the orders of the Department for Regulation
of the Fuel and Energy Complex, attached to its page as PDFs; heating and hot water from
Bishkekteploset, which pastes its tariff table into the page as an image; water from the
Bishkek city council's list of resolutions, which links each resolution as a page of its own.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "KG"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
