"""Runs one city — or a few, or one service — without touching the rest of the country.

Built to keep testing cheap. Every city is a paid model call, and re-collecting a whole
country to check a fix in one city is how a month's credits disappear in a day.

    python src/run_city.py ru yekaterinburg                    # every service of one city
    python src/run_city.py ru yekaterinburg --block water      # one service
    python src/run_city.py ru moscow saint_petersburg --block heating
    python src/run_city.py ru --block electricity              # the country-wide tariff
    python src/run_city.py ru kazan --block electricity        # a city's own electricity tariff
    python src/run_city.py ru yekaterinburg --write            # publish just this city
    python src/run_city.py am --block electricity --llm-from ru   # test on Russia's provider

A dry run, the default, fetches, extracts and validates, then prints what would be published
and every reason something would not. It writes no file, sends nothing to Telegram and leaves
the city registry alone. --write publishes the selected cities into the country file — every
other city keeps its published value — and rebuilds the country index.

A city has to be named: the tool refuses to collect a whole country, which is a job for
src/run_country.py and for the maintainer's agreement. The one exception is the electricity
block, which belongs to the country rather than to a city.
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

import build_index
from common import ai_pipeline, llm
from common.countries import load_countries
from common.jsonio import ELECTRICITY_CITIES, load_previous
from common.overrides import CITY_BLOCKS
from common.telegram_notifier import TelegramNotifier

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunCity")

ELECTRICITY = "electricity"


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Collect tariffs for part of a country.")
    parser.add_argument("country", help="country code, e.g. ru")
    parser.add_argument("cities", nargs="*", default=[], help="city codes from config/<cc>/sources.json")
    parser.add_argument("--block", choices=list(CITY_BLOCKS) + [ELECTRICITY],
                        help="one service only (default: every service of the named cities)")
    parser.add_argument("--write", action="store_true",
                        help="publish the result instead of only printing it")
    parser.add_argument("--accept-period-changes", action="store_true",
                        help="accept a new number for an already published period — only after "
                             "checking by hand that the regulator really corrected it")
    parser.add_argument("--llm-from", metavar="COUNTRY",
                        help="read with settings.llm of another country's config — to debug a "
                             "source on a cheaper provider than the one the country runs on")
    return parser.parse_args(argv)


def check_selection(args, config: dict) -> str:
    """Returns why the selection cannot run, or an empty string when it can."""
    known = config.get("cities") or {}
    unknown = [code for code in args.cities if code not in known]
    if unknown:
        return (f"неизвестные города: {', '.join(unknown)}\n"
                f"есть в конфиге: {', '.join(known)}")
    if not args.cities and args.block != ELECTRICITY:
        return ("назовите хотя бы один город: сбор всей страны — это src/run_country.py "
                "и только с согласия владельца проекта")
    return ""


# Enough of a rejected answer to see which column or row the model took.
RAW_PREVIEW_CHARS = 1500


def print_electricity(label: str, power: dict):
    print(f"  ✅ {label}base_rate {power.get('base_rate')} с {power.get('effective_date')} "
          f"| {power.get('decree_info')}")
    for meter, zones in (power.get("zones") or {}).items():
        rates = ", ".join(f"{name} {zone.get('rate')}" for name, zone in zones.items()
                          if isinstance(zone, dict))
        print(f"       {meter}: {rates}")
    for plan in power.get("plans") or []:
        extras = [f"ступени: {plan['tier_basis']}" if plan.get("tier_basis") else "",
                  "на человека" if plan.get("tiers_per_resident") else "",
                  f"абонплата {plan['monthly_charge']}" if plan.get("monthly_charge") else ""]
        print(f"       [{plan['plan_code']}{' *' if plan.get('is_default') else ''}] "
              f"{plan['name']} {' '.join(e for e in extras if e)}")
        for row in plan["rates"]:
            band = f" ступень {row['tier']}" if row["tier"] else ""
            if row["above_kwh"] is not None or row["up_to_kwh"] is not None:
                band += f" {row['above_kwh'] or 0}–{row['up_to_kwh'] or '∞'} кВт·ч"
            season = f" {row['season_from']}..{row['season_to']}" if row["season_from"] else ""
            hours = f" ({row['hours']})" if row["hours"] else ""
            print(f"         {row['meter']}/{row['zone']}{hours}{band}{season}: {row['rate']}")


def print_dry_run(args, data: dict, refreshed: dict, failures: dict, results: dict):
    blocks = [args.block] if args.block else list(CITY_BLOCKS) + [ELECTRICITY]
    for block in blocks:
        print(f"\n=== {block} ===")
        if block == ELECTRICITY:
            if refreshed.get(ELECTRICITY):
                print_electricity("", data[ELECTRICITY])
            result = results.get(ELECTRICITY_CITIES)
            by_code = {c.get("city_code"): c for c in data[ELECTRICITY_CITIES].get("cities", [])}
            for code in args.cities:
                if result and code in result.records:
                    print_electricity(f"{code}: ", by_code[code])
                elif result and result.raw.get(code):
                    answer = json.dumps(result.raw[code], ensure_ascii=False)
                    print(f"  ❔ {code}: ответ модели — {answer[:RAW_PREVIEW_CHARS]}")
            for reason in failures.get(ELECTRICITY_CITIES, []):
                print(f"  ❌ {reason}")
        else:
            by_code = {c.get("city_code"): c for c in data[block].get("cities", [])}
            result = results.get(block)
            for code in args.cities:
                record = result.records.get(code) if result else None
                if not record:
                    if result and code in result.raw:
                        answer = json.dumps(result.raw[code], ensure_ascii=False)
                        print(f"  ❔ {code}: ответ модели — {answer[:RAW_PREVIEW_CHARS]}")
                    continue
                published = {k: v for k, v in by_code.get(code, {}).items()
                             if k not in ("city_code", "city_name", "unit")}
                print(f"  ✅ {code}: {json.dumps(published, ensure_ascii=False)}")
                for period in record["periods"]:
                    values = {k: v for k, v in period.items()
                              if k not in ("from", "to", "decree_info")}
                    print(f"       {period['from']} .. {period.get('to') or '—'}  "
                          f"{json.dumps(values, ensure_ascii=False)}")
        for reason in failures.get(block, []):
            print(f"  ❌ {reason}")


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    country = load_countries().get(args.country)
    config = ai_pipeline.load_config(country)

    problem = check_selection(args, config)
    if problem:
        print(f"Отказ: {problem}", file=sys.stderr)
        return 2

    blocks = [args.block] if args.block else None
    cities = args.cities or None
    if args.llm_from:
        donor = ai_pipeline.load_config(load_countries().get(args.llm_from))
        config.setdefault("settings", {})["llm"] = donor["settings"]["llm"]
    if args.accept_period_changes:
        config.setdefault("validation", {})["same_period_tolerance"] = None

    if args.write:
        if args.accept_period_changes:
            logger.warning("same-period check is off for this run (--accept-period-changes)")
        notifier = TelegramNotifier()
        ai_pipeline.run(country, notifier, cities=cities, blocks=blocks, config=config)
        build_index.build(notifier)
        return 0

    # A dry run reports to the terminal only: no notifier, so a failed call is not
    # announced in the maintainer's Telegram as if something had been published.
    extractor = llm.from_config(config)
    logger.info(f"{country.code}: dry run with {extractor.name}")
    previous = load_previous(country) or {}
    data, refreshed, failures, results = ai_pipeline.collect(
        country, config, previous, extractor, cities, blocks)

    print_dry_run(args, data, refreshed, failures, results)
    print(f"\n{extractor.usage_line()}")
    print("Ничего не записано. Чтобы опубликовать эти города, добавьте --write.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
