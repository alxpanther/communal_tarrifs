"""Armenia (AM).

The regulator (PSRC) publishes its decisions as prose, and the two suppliers that matter —
Electric Networks of Armenia and Veolia Jur — have no machine-readable tariff page. So the
country runs on the shared manual pipeline: every number lives in config/am/sources.json
under manual_override, and this module only names the country.

Armenia has no district heating or centralised hot water for households, so those two
blocks stay empty by design.

When a scrapable source appears, add the scraping stage here, before the shared pipeline.
"""

import logging

from common.countries import load_country
from common.manual_pipeline import run as run_manual_pipeline

logger = logging.getLogger(__name__)

COUNTRY_CODE = "AM"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_manual_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
