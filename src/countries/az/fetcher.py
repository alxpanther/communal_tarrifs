"""Azerbaijan (AZ).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/az/sources.json. Electricity comes from the tariff tables of the energy regulator
(AERA), heating and hot water from Azeristiliktechizat, water from Azersu. Tariffs are set
centrally by the Tariff (Price) Council, so Baku is the only entry.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "AZ"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
