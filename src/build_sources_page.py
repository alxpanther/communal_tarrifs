"""Builds sources.html — a public page that lists every source the tariffs are read from.

Google Play requires an app that shows information of state bodies to name the sources of that
information, and its reviewers open the addresses the store listing gives. The two publication
hosts are among those addresses, so each of them must answer with a readable page rather than a
404. This page is that answer: the disclaimer, then every source address of every published
country, city and service, read from config/<cc>/sources.json — the same addresses the pipelines
fetch, so the list cannot drift from what is actually collected.

    python src/build_sources_page.py <output_dir>

Writes <output_dir>/sources.html, an identical <output_dir>/index.html, so the bare folder
address opens the page too (GitHub Pages serves it by itself, tarrifs.foleks.com through a rewrite
rule), and <output_dir>/sources.css. The styles live in a file of their own: the security policy of
foleks.com (`style-src 'self'`) drops a <style> written inside the page.
"""

import html
import json
import logging
import os
import sys

if __package__ is None and os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.countries import load_countries
from common.paths import docs_output_path, sources_path

logger = logging.getLogger("SourcesPage")

# Branches of sources.json that hold no tariff source: model endpoints, limits, notes for the
# model, alternative supplier spellings, and pages of cities no longer collected.
SKIPPED_KEYS = {"settings", "validation", "manual_override", "retired_cities", "retired_pages",
                "hint", "supplier_aka"}

SERVICES = {
    "electricity": "Electricity",
    "water": "Cold water and sewage",
    "hot_water": "Hot water",
    "heating": "Heating",
    "gas": "Gas",
    "grid_export": "Electricity sold to the grid",
}

# The page language is English (the reviewers'), country names are the ones config carries.
NAME_LANGUAGE = "ru"


def service_of(path: list) -> str:
    """The service a config branch belongs to: `hot_water_kyiv` counts as hot water."""
    for key in path:
        for service in SERVICES:
            if key == service or key.startswith(service + "_"):
                return service
    return ""


def collect_sources(config: dict) -> list:
    """Every (city, service, supplier, url) of one country, in config order, without repeats."""
    rows, seen = [], set()

    def walk(node, path, city, supplier):
        if isinstance(node, dict):
            city = node.get("city_name", city)
            supplier = node.get("supplier", supplier)
            for key, value in node.items():
                if key not in SKIPPED_KEYS:
                    walk(value, path + [key], city, supplier)
        elif isinstance(node, list):
            for item in node:
                walk(item, path, city, supplier)
        elif isinstance(node, str) and node.startswith(("http://", "https://")):
            row = (city or "", service_of(path), supplier or "", node)
            if row not in seen:
                seen.add(row)
                rows.append(row)

    walk(config, [], None, None)
    return rows


def last_updated(code: str) -> str:
    with open(docs_output_path(code), "r", encoding="utf-8") as f:
        return str(json.load(f).get("last_updated_at", ""))[:10]


STYLES = """body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px; color: #1d1d1f; background: #fff; line-height: 1.45; }
table { border-collapse: collapse; width: 100%; margin-bottom: 28px; font-size: 14px; }
th, td { border-bottom: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }
td:last-child { word-break: break-all; }
.notice { background: #fff4e5; border-left: 4px solid #f0a020; padding: 10px 14px; }
.meta { color: #666; margin-top: -8px; }
"""


def country_section(country) -> str:
    with open(sources_path(country.code), "r", encoding="utf-8") as f:
        rows = collect_sources(json.load(f))
    name = country.country_names.get(NAME_LANGUAGE) or next(iter(country.country_names.values()))
    lines = [
        f'<h2 id="{country.lower}">{html.escape(name)} ({country.code})</h2>',
        f"<p class=\"meta\">Published file updated: {html.escape(last_updated(country.code))}</p>",
        "<table><thead><tr><th>City</th><th>Service</th><th>Supplier</th><th>Source</th></tr></thead><tbody>",
    ]
    for city, service, supplier, url in rows:
        link = html.escape(url, quote=True)
        lines.append(
            f"<tr><td>{html.escape(city) or 'Whole country'}</td>"
            f"<td>{html.escape(SERVICES.get(service, service))}</td>"
            f"<td>{html.escape(supplier)}</td>"
            f'<td><a href="{link}" rel="noopener nofollow" target="_blank">{link}</a></td></tr>'
        )
    lines.append("</tbody></table>")
    return "\n".join(lines)


def render(countries: list) -> str:
    contents = " · ".join(
        f'<a href="#{c.lower}">{html.escape(c.country_names.get(NAME_LANGUAGE, c.code))}</a>'
        for c in countries
    )
    sections = "\n".join(country_section(c) for c in countries)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KomMeter tariff sources</title>
<link rel="stylesheet" href="sources.css">
</head>
<body>
<h1>KomMeter: sources of the tariffs</h1>
<p class="notice">KomMeter is an unofficial app. It does not represent and is not affiliated with any
government body, regulator or utility provider. Tariffs are collected automatically from the public
pages listed below — regulators, utility providers and reference websites — and are for reference
only: check them against your bill.</p>
<p>The app downloads tariffs from this publication only. Each file is compiled from the sources
listed for its country.</p>
<p>{contents}</p>
{sections}
</body>
</html>
"""


def published_countries() -> list:
    """The countries the index lists: not retired, with a published file."""
    return [c for c in load_countries().countries
            if not c.retired and os.path.exists(docs_output_path(c.code))]


def build(output_dir: str) -> list:
    page = render(published_countries())
    os.makedirs(output_dir, exist_ok=True)
    written = []
    for name, content in (("sources.html", page), ("index.html", page), ("sources.css", STYLES)):
        target = os.path.join(output_dir, name)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(target)
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    for target in build(sys.argv[1]):
        logger.info(f"Written {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
