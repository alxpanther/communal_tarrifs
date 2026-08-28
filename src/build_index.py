"""Builds tariffs_index.json — the list of countries whose tariffs are published.

The app needs it for one thing: a country added after a release must appear in the address
form of a user who never updated the app. See docs/en/JSON_SPECIFICATION.md, section 6.

Each host carries its own copy of the index, because the file layout differs:

* GitHub Pages — everything flat at the web root:  tariffs_am.json
* Cloudflare R2 — one folder per country:          am/tariffs_am.json

The `path` of every entry is therefore rendered from that host's template, and the app
resolves it relative to the index it downloaded. Both templates live in
config/countries.json, nothing about a host is hardcoded here.
"""

import json
import logging
import os
import sys
from datetime import datetime

if __package__ is None and os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.countries import load_countries
from common.paths import REPO_ROOT, docs_output_path

logger = logging.getLogger("TariffsIndex")


class IndexError_(Exception):
    pass


def country_entry(country, path_template: str) -> dict:
    """One record of the index, or None when the country has nothing published yet."""
    published = docs_output_path(country.code)
    if not os.path.exists(published):
        logger.warning(f"{country.code}: {published} does not exist, leaving it out of the index")
        return None

    try:
        with open(published, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"{country.code}: cannot read {published} ({e}), leaving it out of the index")
        return None

    last_updated = data.get("last_updated_at")
    if not last_updated:
        logger.warning(f"{country.code}: published file has no last_updated_at, skipping")
        return None

    return {
        "country": country.code,
        "country_names": dict(country.country_names),
        "currency": country.currency,
        "last_updated_at": last_updated,
        "path": path_template.format(cc=country.lower),
        "enabled": country.enabled,
        "min_app_version": country.min_app_version
    }


def build(notifier=None) -> dict:
    """Writes every configured index file. Returns {host: written path}."""
    registry = load_countries()
    generated_at = datetime.now().isoformat()
    written = {}

    for host, settings in (registry.publication or {}).items():
        index_file = settings.get("index_file")
        path_template = settings.get("path_template")
        if not index_file or not path_template:
            logger.warning(f"publication.{host} has no index_file/path_template, skipped")
            continue

        entries = []
        for country in registry.countries:
            entry = country_entry(country, path_template)
            if entry:
                entries.append(entry)

        if not entries:
            # An empty index would tell the app that nothing is published at all.
            # Keeping the previous one is always better than publishing that.
            raise IndexError_(
                f"No published country file found — refusing to write an empty {index_file}"
            )

        payload = {
            "version": registry.index_version,
            "generated_at": generated_at,
            "countries": entries
        }

        target = os.path.join(REPO_ROOT, index_file)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        written[host] = target
        logger.info(f"{host}: wrote {index_file} with {len(entries)} countries "
                    f"({', '.join(e['country'] for e in entries)})")

    if not written:
        raise IndexError_("config/countries.json declares no publication targets")

    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        build()
    except Exception as e:
        logger.error(f"Index build failed: {e}", exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
