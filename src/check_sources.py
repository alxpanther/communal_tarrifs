"""Checks that sources can be read — from the machine it runs on. Calls no model, costs nothing.

    python src/check_sources.py ru                   # every URL in config/ru/sources.json
    python src/check_sources.py --url URL [URL ...]  # candidates, before they go into config

What matters is where it runs. Several Russian sites answer one machine and time out for a GitHub
runner — the Yekaterinburg водоканал and gov.spb.ru opened from a developer's machine and not
from GitHub — so a source is proven only once the "Check Sources" workflow has passed it.

A line per URL: whether it answered, its type and size, how many price-like numbers it carries,
and a warning when it reads like a "page not found". A page with no prices is a menu or an
article, not a tariff. Exit code is non-zero when anything failed.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.fetching import probe
from common.paths import sources_path

# Long enough for a slow regulator site, short enough that a dead one does not stall the check.
TIMEOUT_SECONDS = 30


def urls_of_country(code: str) -> dict:
    """url -> the places in config that use it."""
    with open(sources_path(code), encoding="utf-8") as f:
        config = json.load(f)
    used = {}
    for city_code, city in (config.get("cities") or {}).items():
        for block, source in (city.get("sources") or {}).items():
            urls = source.get("urls") or [] if isinstance(source, dict) else [source]
            for url in urls:
                used.setdefault(url, []).append(f"{city_code}.{block}")
    power = (config.get("electricity") or {}).get("source") or {}
    for url in (power.get("urls") or []) if isinstance(power, dict) else [power]:
        used.setdefault(url, []).append("electricity")
    return used


def describe(result: dict) -> str:
    if "error" in result:
        return f"FAIL  {result['error']}"
    if not result["ok"]:
        return f"FAIL  HTTP {result['status']}"
    line = f"OK    {result['kind']}, {result['chars']} chars, {result['prices']} prices"
    if result["looks_like_404"]:
        line += "  ⚠ looks like a 'page not found'"
    elif result["prices"] == 0:
        line += "  ⚠ no prices on the page"
    return line


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check that tariff sources can be read.")
    parser.add_argument("countries", nargs="*", default=[], help="country codes, e.g. ru")
    parser.add_argument("--url", nargs="+", default=[], help="candidate URLs to check")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not args.countries and not args.url:
        parser.error("name a country or pass --url")

    targets = {}
    for code in args.countries:
        for url, places in urls_of_country(code.lower()).items():
            targets.setdefault(url, []).extend(places)
    for url in args.url:
        targets.setdefault(url, []).append("candidate")

    failed = 0
    for url, places in targets.items():
        verdict = describe(probe(url, TIMEOUT_SECONDS))
        failed += verdict.startswith("FAIL")
        print(f"{verdict}\n      {url}\n      used by: {', '.join(places)}")
    print(f"\n{len(targets) - failed} of {len(targets)} sources answered.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
