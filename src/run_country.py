"""Entry point of the generator: runs one country, several, or all of them.

    python src/run_country.py            # every enabled country, then the index
    python src/run_country.py ua         # only Ukraine, then the index
    python src/run_country.py am az      # Armenia and Azerbaijan
    python src/run_country.py all --no-index

Countries run one after another in a fixed order. A country that fails is reported to
Telegram and the run continues with the next one — one broken source must not stop the
others from being republished. The index is rebuilt at the end from whatever is actually
published on disk, so a failed country simply keeps its previous entry.

Exit code is non-zero when any country or the index build failed, which is what makes the
CI job go red.
"""

import argparse
import importlib
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

import build_index
from common.countries import load_countries
from common.telegram_notifier import TelegramNotifier

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunCountry")


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Generate utility tariff files per country.")
    parser.add_argument("countries", nargs="*", default=[],
                        help="country codes to run, or 'all' (default: every enabled country)")
    parser.add_argument("--no-index", action="store_true",
                        help="do not rebuild tariffs_index.json afterwards")
    return parser.parse_args(argv)


def select_countries(registry, requested: list) -> list:
    if not requested or [c.lower() for c in requested] == ["all"]:
        return [c for c in registry.countries if c.enabled]
    return [registry.get(code) for code in requested]


def run_pipeline(country, notifier: TelegramNotifier):
    module = importlib.import_module(f"countries.{country.pipeline}.fetcher")
    return module.main(notifier)


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    notifier = TelegramNotifier()

    try:
        registry = load_countries()
        selected = select_countries(registry, args.countries)
    except Exception as e:
        message = f"💥 <b>Фатальная ошибка конфигурации стран:</b>\n<code>{e}</code>"
        logger.critical(message)
        notifier.send_message(message, parse_mode="HTML")
        return 1

    logger.info(f"Countries to run: {', '.join(c.code for c in selected)}")
    failed = []

    for country in selected:
        try:
            run_pipeline(country, notifier)
        except Exception as e:
            failed.append(country.code)
            logger.error(f"{country.code} pipeline failed: {e}", exc_info=True)
            notifier.send_message(
                f"💥 <b>Сбой генерации тарифов {country.code}:</b>\n<code>{e}</code>\n"
                f"Ранее опубликованный файл оставлен без изменений.",
                parse_mode="HTML"
            )

    if not args.no_index:
        try:
            build_index.build(notifier)
        except Exception as e:
            failed.append("index")
            logger.error(f"Index build failed: {e}", exc_info=True)
            notifier.send_message(
                f"💥 <b>Не удалось собрать tariffs_index.json:</b>\n<code>{e}</code>",
                parse_mode="HTML"
            )

    if failed:
        logger.error(f"Finished with failures: {', '.join(failed)}")
        return 1

    logger.info("Finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
