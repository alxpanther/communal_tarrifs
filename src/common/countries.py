"""The country registry, config/countries.json.

One list of every country the generator publishes. Pipelines read their own metadata from
here (country code, display names, currency), and the index builder reads all of it.
Nothing about a country is hardcoded in Python.
"""

import json
import os

from common.paths import COUNTRIES_PATH


class CountryConfigError(Exception):
    pass


class Country:
    """One entry of config/countries.json."""

    def __init__(self, raw: dict):
        code = str(raw.get("code", "")).strip().upper()
        if len(code) != 2:
            raise CountryConfigError(f"Invalid country code in countries.json: {raw.get('code')!r}")

        names = raw.get("country_names") or {}
        if not isinstance(names, dict) or not names:
            raise CountryConfigError(f"Country {code} has no country_names")

        currency = str(raw.get("currency", "")).strip().upper()
        if not currency:
            raise CountryConfigError(f"Country {code} has no currency")

        self.code = code
        self.lower = code.lower()
        self.country_names = {str(k): str(v) for k, v in names.items()}
        self.currency = currency
        # Python module under src/countries/ that generates this country's file.
        self.pipeline = str(raw.get("pipeline") or self.lower)
        self.enabled = bool(raw.get("enabled", True))
        self.min_app_version = str(raw.get("min_app_version") or "")

    def __repr__(self):
        return f"<Country {self.code}>"


class CountryRegistry:
    def __init__(self, raw: dict):
        self.index_version = str(raw.get("index_version") or "1.0")
        self.publication = raw.get("publication") or {}
        self.countries = [Country(entry) for entry in raw.get("countries") or []]
        if not self.countries:
            raise CountryConfigError("countries.json lists no countries")

        seen = set()
        for country in self.countries:
            if country.code in seen:
                raise CountryConfigError(f"Duplicate country code {country.code} in countries.json")
            seen.add(country.code)

    def get(self, code: str) -> Country:
        wanted = str(code).strip().upper()
        for country in self.countries:
            if country.code == wanted:
                return country
        raise CountryConfigError(f"Country {wanted} is not listed in countries.json")

    def codes(self) -> list:
        return [country.code for country in self.countries]


def load_countries() -> CountryRegistry:
    if not os.path.exists(COUNTRIES_PATH):
        raise CountryConfigError(f"Country registry missing at {COUNTRIES_PATH}")
    with open(COUNTRIES_PATH, "r", encoding="utf-8") as f:
        return CountryRegistry(json.load(f))


def load_country(code: str) -> Country:
    return load_countries().get(code)
