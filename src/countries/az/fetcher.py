"""Azerbaijan (AZ).

Tariffs are set centrally by the Tariff (Price) Council and published on tariff.gov.az as
prose and PDF decisions, with no table a parser can rely on. So the country runs on the
shared manual pipeline: every number lives in config/az/sources.json under manual_override,
and this module only names the country.

Unlike Armenia, Azerbaijan does have centralised hot water and heating (Azeristiliktechizat),
so all four blocks are filled.

When a scrapable source appears, add the scraping stage here, before the shared pipeline.
"""

import logging

from common.countries import load_country
from common.manual_pipeline import run as run_manual_pipeline

logger = logging.getLogger(__name__)

COUNTRY_CODE = "AZ"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_manual_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
