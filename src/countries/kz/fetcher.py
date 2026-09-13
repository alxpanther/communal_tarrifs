"""Kazakhstan (KZ).

Tariffs are collected by the shared per-city pipeline; the sources live in
config/kz/sources.json. Every tariff is approved by the regional department of the Committee for
the Regulation of Natural Monopolies and published by the supplier itself, so each city reads
its own water utility and heat company. Electricity is Astana's supplier, Astana-REC.
"""

import logging

from common.ai_pipeline import run as run_ai_pipeline
from common.countries import load_country

logger = logging.getLogger(__name__)

COUNTRY_CODE = "KZ"


def main(notifier=None) -> dict:
    country = load_country(COUNTRY_CODE)
    logger.info(f"Starting {country.code} tariff pipeline...")
    result = run_ai_pipeline(country, notifier)
    logger.info(f"{country.code} tariff update completed successfully.")
    return result
