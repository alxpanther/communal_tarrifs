"""Moldova (MD).

Runs on the shared manual pipeline: tariffs are declared in config/md/sources.json
under manual_override, and this module delegates to common/manual_pipeline.py.
"""

import logging

from common.countries import load_country
from common.manual_pipeline import run as run_manual_pipeline

logger = logging.getLogger(__name__)

COUNTRY_CODE = "MD"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_manual_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
