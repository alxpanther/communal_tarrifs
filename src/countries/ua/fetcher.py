import os
import json
import logging
import re
import difflib
import html as html_module
from datetime import datetime
import requests
from dotenv import load_dotenv

from common.countries import load_country
from common.jsonio import build_root, empty_city_block, save_country_json
from common.overrides import apply_base_rate_to_zones, apply_manual_overrides
from common.paths import assets_output_path, docs_output_path, registry_path, sources_path
from common.telegram_notifier import TelegramNotifier

load_dotenv()

logger = logging.getLogger("TariffsFetcherUA")

COUNTRY_CODE = "UA"

CONFIG_PATH = sources_path(COUNTRY_CODE)
REGISTRY_PATH = registry_path(COUNTRY_CODE)
OUTPUT_PATH = assets_output_path(COUNTRY_CODE)
ROOT_OUTPUT_PATH = docs_output_path(COUNTRY_CODE)

# Sanity limits for a single water tariff component (UAH per m3, VAT included)
MAX_WATER_RATE = 500.0
# Allowed rounding error when checking water_supply + sewage == total_rate
RATE_SUM_TOLERANCE = 0.011
# Sanity limit for a hot water tariff (UAH per m3, VAT included)
MAX_HOT_WATER_RATE = 1000.0
# Sanity limits for heating: variable part (UAH per Gcal) and standing part (UAH per Gcal/hour)
MAX_HEAT_GCAL_RATE = 20000.0
MAX_HEAT_GCAL_HOUR_RATE = 1000000.0

# Registry sections. Water utilities and heat suppliers are different companies, so they get
# separate sections, while hot water and heating share one because it is the same companies.
WATER_REGISTRY_SECTION = "suppliers"
HEAT_REGISTRY_SECTION = "heat_suppliers"

class ConfigError(Exception):
    pass

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise ConfigError(f"Configuration file missing at {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    ref = config.get("reference_sources", {})
    if not ref.get("electricity") or not ref.get("water"):
        raise ConfigError("Missing required reference_sources in config/sources.json")

    # hot_water and heating stay optional: an older config without them keeps working,
    # the corresponding blocks are simply carried over from the previous JSON.
    for optional in ("hot_water", "heating", "hot_water_kyiv"):
        if not ref.get(optional):
            logger.warning(f"reference_sources.{optional} is not configured, block will not be refreshed")

    return config

def parse_date(date_str: str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            pass
    return None

def parse_rate(rate_val):
    if rate_val is None:
        return None
    try:
        if isinstance(rate_val, (int, float)):
            return float(rate_val)
        cleaned = re.sub(r"[^\d.,]", "", str(rate_val)).replace(",", ".")
        return float(cleaned) if cleaned else None
    except Exception:
        return None

def load_base_schema() -> dict:
    """
    Loads reference base schema prioritizing master file (tariffs_ua.json),
    falling back to existing output files or default fallback.
    """
    candidate_paths = [ROOT_OUTPUT_PATH, OUTPUT_PATH]
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and "electricity" in data and "water" in data:
                        cities = data.get("water", {}).get("cities", [])
                        if len(cities) > 0:
                            return data
            except Exception as e:
                logger.warning(f"Failed to parse base schema from {path}: {e}")

    return {
        "version": "1.0",
        "last_updated_at": datetime.now().isoformat(),
        "country": "UA",
        "currency": "UAH",
        "electricity": {
            "source_url": "https://tariffa.com.ua/ru/tarif-na-elektroenergiy",
            "base_rate": 4.32,
            "unit": "kWh",
            "effective_date": "2024-06-01",
            "update_date": datetime.now().strftime("%Y-%m-%d"),
            "decree_info": "Постанова Кабінету Міністрів України № 632 від 31 травня 2024 р.",
            "zones": {
                "two_zone": {
                    "description": "Двозонний тариф (День/Ніч)",
                    "day": {"hours": "07:00 - 23:00", "coefficient": 1.0, "rate": 4.32},
                    "night": {"hours": "23:00 - 07:00", "coefficient": 0.5, "rate": 2.16}
                },
                "three_zone": {
                    "description": "Тризонний тариф (Пік/Напівпік/Ніч)",
                    "peak": {"hours": "08:00 - 11:00, 20:00 - 22:00", "coefficient": 1.5, "rate": 6.48},
                    "half_peak": {"hours": "07:00 - 08:00, 11:00 - 20:00, 22:00 - 23:00", "coefficient": 1.0, "rate": 4.32},
                    "night": {"hours": "23:00 - 07:00", "coefficient": 0.4, "rate": 1.728}
                }
            }
        },
        "water": empty_city_block("https://index.minfin.com.ua/ua/tariff/water/"),
        "hot_water": empty_city_block("https://index.minfin.com.ua/ua/tariff/hotwater/"),
        "heating": empty_city_block("https://index.minfin.com.ua/ua/tariff/heating/")
    }

def resolve_latest_gemini_model(config: dict) -> str:
    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        logger.info(f"Using GEMINI_MODEL from environment: {env_model}")
        return env_model

    settings = config.get("settings", {})
    fallback_model = settings.get("gemini_model", "gemini-2.5-flash")
    auto_select = settings.get("auto_select_latest_model", True)

    api_key = os.getenv("GEMINI_API_KEY")
    if not auto_select or not api_key:
        return fallback_model

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        models_list = list(client.models.list())
        
        flash_models = []
        for m in models_list:
            m_name = getattr(m, "name", str(m))
            clean_name = m_name.replace("models/", "")
            if "flash" in clean_name.lower() and "gemini" in clean_name.lower() and "experimental" not in clean_name.lower():
                flash_models.append(clean_name)

        if not flash_models:
            return fallback_model

        def parse_version(name: str) -> float:
            match = re.search(r"gemini-(\d+(?:\.\d+)?)-flash", name, re.IGNORECASE)
            return float(match.group(1)) if match else 0.0

        flash_models.sort(key=parse_version, reverse=True)
        return flash_models[0]

    except Exception as e:
        logger.warning(f"Failed to dynamically list Gemini models ({e}). Falling back to config model: '{fallback_model}'")
        return fallback_model

def parse_json_from_llm(raw_text: str) -> dict:
    if not raw_text or not isinstance(raw_text, str):
        return {}

    cleaned = raw_text.strip()
    json_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if json_block_match:
        cleaned = json_block_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"Could not parse JSON from response text ({e}): {cleaned[:200]}")
        return {}

def fetch_html(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"Failed to fetch {url}, status code: {resp.status_code}")
        return ""
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""

def call_gemini_extract(text_content: str, prompt_instruction: str, model_name: str, notifier: TelegramNotifier) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. Skipping LLM extraction.")
        return {}

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model=model_name,
            contents=[text_content, prompt_instruction],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
        )
        
        if not response or not hasattr(response, "text") or response.text is None:
            logger.warning("Gemini API returned empty text response.")
            return {}

        return parse_json_from_llm(response.text)

    except Exception as e:
        err_msg = f"❌ <b>Ошибка вызова Gemini API (Модель: <code>{model_name}</code>):</b>\n<code>{str(e)}</code>"
        logger.error(err_msg)
        notifier.send_message(err_msg, parse_mode="HTML")
        return {}

def call_gemini_search(search_query: str, prompt_instruction: str, model_name: str, notifier: TelegramNotifier) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. Skipping search grounding.")
        return {}

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model=model_name,
            contents=[f"Запрос для поиска: {search_query}", prompt_instruction],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1
            ),
        )
        
        if not response or not hasattr(response, "text") or response.text is None:
            logger.warning("Gemini Search Grounding returned empty or None text.")
            return {}

        return parse_json_from_llm(response.text)

    except Exception as e:
        err_msg = f"❌ <b>Ошибка Gemini Search Grounding (Модель: <code>{model_name}</code>):</b>\n<code>{str(e)}</code>"
        logger.error(err_msg)
        notifier.send_message(err_msg, parse_mode="HTML")
        return {}

# Official Ukrainian-to-Latin transliteration (Cabinet of Ministers resolution No. 55 of 27.01.2010).
# Letters whose Latin form depends on position carry a (word_start, elsewhere) pair.
UK_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e",
    "є": ("ye", "ie"), "ж": "zh", "з": "z", "и": "y", "і": "i",
    "ї": ("yi", "i"), "й": ("y", "i"), "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ь": "", "ю": ("yu", "iu"), "я": ("ya", "ia"), "'": "", "’": "", "ʼ": "",
}

# Markers identifying a real water utility, used to pick the owner of a plain city code
# when several suppliers share the same city name.
WATERWORKS_MARKERS = ("водоканал", "вувкг", "водовід", "водопостач", "водоекотехпром", "вкг")

def translit_uk(text: str) -> str:
    """Transliterates Ukrainian text to Latin per resolution No. 55. Deterministic by design."""
    result = []
    for word in re.split(r"[^\w'’ʼ]+", text.lower(), flags=re.UNICODE):
        if not word:
            continue
        letters = []
        for pos, char in enumerate(word):
            # "зг" is the single documented digraph exception
            if char == "г" and pos > 0 and word[pos - 1] == "з":
                letters[-1] = "zg"
                letters.append("h")
                continue
            mapped = UK_TRANSLIT.get(char, char if char.isascii() and char.isalnum() else "")
            if isinstance(mapped, tuple):
                mapped = mapped[0] if pos == 0 else mapped[1]
            letters.append(mapped)
        joined = "".join(letters)
        if joined:
            result.append(joined)
    return "_".join(result)

def slugify(text: str, max_words: int = 3) -> str:
    """Builds a safe identifier from Ukrainian text, limited to the first few words."""
    slug = translit_uk(text)
    parts = [p for p in slug.split("_") if p][:max_words]
    return re.sub(r"[^a-z0-9_]", "", "_".join(parts))

def quoted_part(supplier: str) -> str:
    """
    Returns the quoted part of a supplier name, or the whole name when it has no quotes.
    Names with nested quotes, such as ТОВ "Фірма "Технова" (Чернігів), yield several
    fragments; the longest one is the distinctive part.
    """
    quoted = re.findall(r"[\"“”«»']([^\"“”«»']+)[\"“”«»']", supplier)
    return max(quoted, key=len) if quoted else supplier

def supplier_suffix(supplier: str) -> str:
    """Derives a disambiguating suffix from the quoted part of a supplier name."""
    return slugify(quoted_part(supplier))

def is_waterworks(supplier: str, city_name: str = "") -> bool:
    lowered = supplier.lower()
    return any(marker in lowered for marker in WATERWORKS_MARKERS)

def is_named_after_city(supplier: str, city_name: str) -> bool:
    """
    True when a heat supplier carries the city name in its own name, e.g.
    КП "КИЇВТЕПЛОЕНЕРГО" in Київ. Heat companies have no common naming marker the way
    water utilities do, so the city root is what identifies the main supplier of a city.
    The city name in brackets after the company name does not count, only the quoted part.
    """
    root = normalize_name(city_name)
    if len(root) < 4:
        return False
    return root[:6] in normalize_name(quoted_part(supplier))

def assign_city_code(city_name: str, supplier: str, taken: set, rivals: list,
                     is_plain_owner=is_waterworks) -> str:
    """
    Deterministic city_code: transliterated city name, disambiguated by supplier when
    several suppliers share one city. A plain code goes to the single main supplier of
    that city; otherwise every rival carries a suffix.
    """
    base = slugify(city_name) or slugify(supplier) or "city"

    owners = [s for s in rivals if is_plain_owner(s, city_name)]
    plain_owner = owners[0] if len(rivals) > 1 and len(owners) == 1 else (
        rivals[0] if len(rivals) == 1 else None
    )

    code = base if supplier == plain_owner else f"{base}_{supplier_suffix(supplier)}"
    code = code[:48].rstrip("_")

    # Guard against collisions with codes already handed out
    candidate, n = code, 2
    while candidate in taken:
        candidate = f"{code}_{n}"
        n += 1
    return candidate

def normalize_name(text: str) -> str:
    """Normalizes a supplier name so lookups survive quote and spacing differences."""
    return re.sub(r"[^a-zа-яёіїєґ0-9]", "", str(text).lower())

REGISTRY_COMMENT = (
    "Постоянный реестр city_code. Ключ — название поставщика с сайта-источника. "
    "Однажды назначенный city_code менять нельзя: Android-приложение хранит его "
    "как выбор пользователя. Новые поставщики дописываются автоматически. "
    "Секция suppliers — водоканалы, heat_suppliers — поставщики тепла (горячая вода и отопление)."
)

def load_registry_file() -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return {}
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read city registry: {e}")
        return {}

def load_registry(section: str = WATER_REGISTRY_SECTION) -> dict:
    """Loads one section of the persistent supplier -> city_code registry.
    Codes stored here are never rewritten."""
    return load_registry_file().get(section, {})

def save_registry(suppliers: dict, section: str = WATER_REGISTRY_SECTION):
    """Rewrites one section, carrying the other section over untouched."""
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    stored = load_registry_file()
    payload = {
        "_comment": REGISTRY_COMMENT,
        WATER_REGISTRY_SECTION: stored.get(WATER_REGISTRY_SECTION, {}),
        HEAT_REGISTRY_SECTION: stored.get(HEAT_REGISTRY_SECTION, {})
    }
    payload[section] = dict(sorted(suppliers.items()))
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def resolve_city_identity(cities: list, notifier: TelegramNotifier,
                          section: str = WATER_REGISTRY_SECTION,
                          is_plain_owner=is_waterworks, label: str = "воды") -> list:
    """
    Replaces model-provided identifiers with registry-backed ones so city_code and
    city_name stay byte-identical across runs. Returns the cities with final identity.
    """
    registry = load_registry(section)
    lookup = {normalize_name(name): entry for name, entry in registry.items()}
    taken = {entry["city_code"] for entry in registry.values()}

    # Suppliers sharing a city name compete for the plain code
    rivals_by_city = {}
    for city in cities:
        rivals_by_city.setdefault(slugify(city["city_name"]), []).append(city["supplier"])

    added = []
    for city in cities:
        known = lookup.get(normalize_name(city["supplier"]))
        if known:
            city["city_code"] = known["city_code"]
            city["city_name"] = known["city_name"]
            continue

        code = assign_city_code(
            city["city_name"], city["supplier"], taken,
            rivals_by_city.get(slugify(city["city_name"]), [city["supplier"]]),
            is_plain_owner
        )
        taken.add(code)
        city["city_code"] = code
        registry[city["supplier"]] = {"city_code": code, "city_name": city["city_name"]}
        lookup[normalize_name(city["supplier"])] = registry[city["supplier"]]
        added.append(f"{city['supplier']} → {code}")

    present = {normalize_name(c["supplier"]) for c in cities}
    disappeared = [
        f"{name} ({entry['city_code']})"
        for name, entry in registry.items()
        if normalize_name(name) not in present
    ]

    if added:
        save_registry(registry, section)
        logger.info(f"Registered {len(added)} new suppliers in '{section}'")
        notifier.send_message(
            f"🆕 <b>В тарифах {label} появились новые поставщики</b>\n"
            "Им назначены новые <code>city_code</code>, приложение о них ещё не знает:\n"
            + "\n".join(f"• <code>{a}</code>" for a in added),
            parse_mode="HTML"
        )

    if disappeared:
        logger.warning(f"{len(disappeared)} known suppliers are missing from the '{section}' source")
        notifier.send_message(
            f"⚠️ <b>Поставщики {label} пропали с сайта-источника</b>\n"
            "Их города исчезнут из JSON, у пользователей с этими <code>city_code</code> "
            "выбор перестанет работать:\n"
            + "\n".join(f"• <code>{d}</code>" for d in disappeared),
            parse_mode="HTML"
        )

    return cities

WATER_PROMPT = """
Ты извлекаешь данные из HTML-таблицы тарифов на воду с сайта index.minfin.com.ua.

Извлеки КАЖДУЮ строку таблицы, относящуюся к предприятию-поставщику. Строки-подзаголовки
с названием области (например "Вінницька обл.") — это не поставщики, они лишь задают
область для следующих за ними строк.

Правила извлечения:
1. Переписывай числа ТОЧНО так, как они указаны в таблице. Десятичный разделитель "," замени на ".".
   Ничего не округляй, не пересчитывай и не подгоняй под сумму.
2. Прочерк "-" вместо тарифа означает, что услуга не предоставляется — используй 0.0.
3. "supplier" — название предприятия так, как оно написано в таблице.
4. "city_name" — название населённого пункта на украинском. Определяй его по названию
   предприятия или по столбцу области. Если предприятие обслуживает не город, а область
   или ведомственную сеть, укажи область (например "Дніпропетровська обл.").
5. НЕ добавляй строки, которых нет в таблице. НЕ пропускай ни одной строки поставщика.

Верни СТРОГО JSON без текста до и после:
{
  "cities": [
    {
      "city_name": "Київ",
      "supplier": "ПАТ АК \\"Київводоканал\\"",
      "water_supply": 16.164,
      "sewage": 14.220,
      "total_rate": 30.384
    }
  ]
}
"""

def extract_water_table_html(html: str) -> str:
    """Returns the first <table> block of the page, which holds the tariff rows."""
    match = re.search(r"<table.*?</table>", html, flags=re.S | re.I)
    return match.group(0) if match else ""

def table_row_cells(row_html: str) -> list:
    """Strips tags from one <tr> and returns its cell texts."""
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.S | re.I)
    return [html_module.unescape(re.sub(r"<[^>]+>", "", c)).replace("­", "").strip() for c in cells]

def count_supplier_rows(table_html: str) -> int:
    """Counts rows that carry tariff values, used to verify LLM extraction completeness."""
    count = 0
    for row in re.findall(r"<tr.*?</tr>", table_html, flags=re.S | re.I):
        cells = table_row_cells(row)
        if len(cells) >= 4 and re.fullmatch(r"[\d,\s ]+|-", cells[1]):
            count += 1
    return count

def source_rows(table_html: str) -> dict:
    """
    Maps each (water_supply, sewage, total_rate) triple of the source table to the supplier
    and period printed on that row. The triple is the join key: it rejects hallucinated
    digits and swapped columns, while supplier and period are taken from the source itself,
    so the model rewording a name cannot reach the output.
    """
    rows = {}
    for row_html in re.findall(r"<tr.*?</tr>", table_html, flags=re.S | re.I):
        cells = table_row_cells(row_html)
        if len(cells) < 4 or not re.fullmatch(r"[\d,\s ]+|-", cells[1]):
            continue

        triple = tuple(parse_rate(c) if c != "-" else 0.0 for c in cells[1:4])
        if any(v is None for v in triple):
            continue

        rows.setdefault(triple, []).append({"supplier": cells[0], "period": cells[-1]})
    return rows

def pick_source_row(candidates: list, model_supplier: str) -> dict:
    """Picks the source row matching the model's supplier when one triple has several rows."""
    if len(candidates) == 1:
        return candidates[0]
    target = normalize_name(model_supplier)
    return max(
        candidates,
        key=lambda row: difflib.SequenceMatcher(None, target, normalize_name(row["supplier"])).ratio()
    )

def parse_period(period: str) -> tuple:
    """Parses a period string like 'з 01.01.2022' into (effective_date, decree_info)."""
    dates = re.findall(r"\d{2}\.\d{2}\.\d{4}", period or "")
    if not dates:
        return None, None

    start = parse_date(dates[0])
    if not start:
        return None, None

    effective_date = start.strftime("%Y-%m-%d")
    decree_info = f"Тариф НКРЕКП, чинний з {dates[0]}"
    if len(dates) > 1:
        decree_info += f" по {dates[1]}"
    return effective_date, decree_info

def validate_water_cities(raw_cities, expected_rows: int, table_rows: dict) -> tuple:
    """Validates LLM output against the source table rows. Returns (cities, errors)."""
    errors = []

    if not isinstance(raw_cities, list) or not raw_cities:
        return [], ["Модель не вернула список городов"]

    if expected_rows and len(raw_cities) != expected_rows:
        errors.append(f"Извлечено {len(raw_cities)} строк вместо {expected_rows} в таблице источника")

    cities = []
    matched_triples = set()

    for idx, item in enumerate(raw_cities):
        if not isinstance(item, dict):
            errors.append(f"Запись #{idx + 1}: не является объектом")
            continue

        name = str(item.get("city_name", "")).strip()
        model_supplier = str(item.get("supplier", "")).strip()
        label = model_supplier or name or f"#{idx + 1}"

        if not name:
            errors.append(f"{label}: пустой city_name")
            continue

        water_supply = parse_rate(item.get("water_supply"))
        sewage = parse_rate(item.get("sewage"))
        total_rate = parse_rate(item.get("total_rate"))

        if water_supply is None or sewage is None or total_rate is None:
            errors.append(f"{label}: нечисловые значения тарифов")
            continue
        if not all(0.0 <= v <= MAX_WATER_RATE for v in (water_supply, sewage, total_rate)):
            errors.append(f"{label}: тариф вне допустимого диапазона 0..{MAX_WATER_RATE}")
            continue
        if abs(water_supply + sewage - total_rate) > RATE_SUM_TOLERANCE:
            errors.append(f"{label}: {water_supply} + {sewage} != {total_rate}")
            continue

        triple = (water_supply, sewage, total_rate)
        if triple not in table_rows:
            errors.append(
                f"{label}: строка {water_supply} / {sewage} / {total_rate} "
                "отсутствует в исходной таблице в таком порядке"
            )
            continue
        if triple in matched_triples:
            errors.append(f"{label}: строка {water_supply} / {sewage} / {total_rate} извлечена дважды")
            continue

        # Supplier and period always come from the source, never from the model,
        # so a reworded name cannot change city_code or reach the output.
        source_row = pick_source_row(table_rows[triple], model_supplier)
        effective_date, decree_info = parse_period(source_row["period"])
        if not effective_date:
            errors.append(f"{label}: не удалось разобрать период '{source_row['period']}'")
            continue

        if normalize_name(model_supplier) != normalize_name(source_row["supplier"]):
            logger.info(
                f"Supplier name corrected from source: '{model_supplier}' -> '{source_row['supplier']}'"
            )

        matched_triples.add(triple)
        cities.append({
            # city_code is assigned later from the persistent registry, never by the model
            "city_code": "",
            "city_name": name,
            "supplier": source_row["supplier"],
            "water_supply": water_supply,
            "sewage": sewage,
            "total_rate": total_rate,
            "unit": "m3",
            "effective_date": effective_date,
            "decree_info": decree_info
        })

    return cities, errors

def extract_water_tariffs(water_html: str, model_name: str, notifier: TelegramNotifier) -> list:
    """
    Extracts the water tariff table via LLM and validates the result against the source.
    Returns None when extraction cannot be trusted, so the caller keeps the previous data.
    """
    table_html = extract_water_table_html(water_html)
    if not table_html:
        logger.error("Water tariff table not found in the fetched page")
        notifier.send_message(
            "⚠️ <b>Тарифы на воду не обновлены:</b>\nтаблица не найдена на странице источника.",
            parse_mode="HTML"
        )
        return None

    expected_rows = count_supplier_rows(table_html)
    logger.info(f"Water table found: {len(table_html)} chars, {expected_rows} supplier rows expected")

    extracted = call_gemini_extract(table_html, WATER_PROMPT, model_name, notifier)
    cities, errors = validate_water_cities(extracted.get("cities"), expected_rows, source_rows(table_html))

    if errors:
        for err in errors:
            logger.warning(f"Water validation: {err}")
        details = "\n".join(f"• {e}" for e in errors[:15])
        if len(errors) > 15:
            details += f"\n… и ещё {len(errors) - 15}"
        notifier.send_message(
            f"⚠️ <b>Тарифы на воду не обновлены — не пройдена валидация ({len(errors)}):</b>\n<code>{details}</code>",
            parse_mode="HTML"
        )
        return None

    cities = resolve_city_identity(cities, notifier)
    logger.info(f"Water tariffs extracted and validated for {len(cities)} suppliers")
    return cities

# Ukrainian month names in the genitive case, as printed in minfin table captions.
UK_MONTHS_GENITIVE = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}

# Heat tariff kinds as printed in the source, mapped to the values published in the JSON.
HEAT_TARIFF_TYPES = {"одноставковий": "one_rate", "двоставковий": "two_rate"}

def parse_caption_date(page_html: str) -> tuple:
    """
    Reads the '(на 1 лютого 2021 року)' stamp from a minfin table caption. Unlike the water
    table, the hot water and heating tables carry no per-row period, so this caption is the
    only date the source publishes. Returns (effective_date, decree_info) or (None, None).
    """
    text = html_module.unescape(re.sub(r"<[^>]+>", " ", page_html))
    match = re.search(r"\(на\s+(\d{1,2})\s+([а-яіїєґ']+)\s+(\d{4})\s+року\)", text, flags=re.I)
    if not match:
        return None, None

    month = UK_MONTHS_GENITIVE.get(match.group(2).lower())
    if not month:
        return None, None

    day, year = int(match.group(1)), int(match.group(3))
    return f"{year}-{month:02d}-{day:02d}", f"Тариф НКРЕКП, чинний станом на {day:02d}.{month:02d}.{year}"

def hot_water_rows(table_html: str) -> list:
    """
    Parses the two-column minfin hot water table (supplier, UAH per m3). Rows holding a
    single cell are region captions and carry no tariff.
    """
    rows = []
    for row_html in re.findall(r"<tr.*?</tr>", table_html, flags=re.S | re.I):
        cells = table_row_cells(row_html)
        if len(cells) != 2 or not re.fullmatch(r"[\d,\s ]+", cells[1]):
            continue

        rate = parse_rate(cells[1])
        if rate is not None:
            rows.append({"supplier": cells[0], "rate": rate})
    return rows

def heating_rows(table_html: str) -> list:
    """
    Parses the minfin heating table. A one-rate supplier occupies a single row, while a
    two-rate one spans three: the supplier row plus the 'умовно-змінна' and 'умовно-постійна'
    continuation rows that carry the two halves of the tariff.
    """
    rows = []
    current = None

    for row_html in re.findall(r"<tr.*?</tr>", table_html, flags=re.S | re.I):
        cells = table_row_cells(row_html)

        if len(cells) >= 4 and cells[1] in HEAT_TARIFF_TYPES:
            current = {
                "supplier": cells[0],
                "tariff_type": HEAT_TARIFF_TYPES[cells[1]],
                "rate_gcal": parse_rate(cells[2]) or 0.0,
                "rate_gcal_hour": parse_rate(cells[3]) or 0.0
            }
            rows.append(current)
        elif current and len(cells) == 3:
            value = next((v for v in (parse_rate(cells[1]), parse_rate(cells[2])) if v is not None), None)
            if value is None:
                continue
            if cells[0].startswith("умовно-змінна"):
                current["rate_gcal"] = value
            elif cells[0].startswith("умовно-постійна"):
                current["rate_gcal_hour"] = value
        elif len(cells) <= 1:
            # A region caption ends the block of the supplier parsed so far
            current = None

    return rows

def validate_hot_water_rows(rows: list, effective_date: str, decree_info: str) -> tuple:
    """Validates parsed hot water rows. Returns (cities, errors)."""
    if not rows:
        return [], ["Таблица горячей воды не содержит ни одной строки с тарифом"]

    cities, errors = [], []
    for row in rows:
        label = row["supplier"] or "запись без названия"
        if not 0.0 < row["rate"] <= MAX_HOT_WATER_RATE:
            errors.append(f"{label}: тариф {row['rate']} вне допустимого диапазона 0..{MAX_HOT_WATER_RATE}")
            continue

        cities.append({
            # city_code and city_name are filled later from the persistent registry
            "city_code": "",
            "city_name": "",
            "supplier": row["supplier"],
            "rate": row["rate"],
            "unit": "m3",
            "effective_date": effective_date,
            "decree_info": decree_info
        })
    return cities, errors

def validate_heating_rows(rows: list, effective_date: str, decree_info: str) -> tuple:
    """Validates parsed heating rows. Returns (cities, errors)."""
    if not rows:
        return [], ["Таблица отопления не содержит ни одной строки с тарифом"]

    cities, errors = [], []
    for row in rows:
        label = row["supplier"] or "запись без названия"
        gcal, gcal_hour = row["rate_gcal"], row["rate_gcal_hour"]

        if not 0.0 < gcal <= MAX_HEAT_GCAL_RATE:
            errors.append(f"{label}: тариф {gcal} грн/Гкал вне диапазона 0..{MAX_HEAT_GCAL_RATE}")
            continue
        if not 0.0 <= gcal_hour <= MAX_HEAT_GCAL_HOUR_RATE:
            errors.append(f"{label}: абонплата {gcal_hour} грн/Гкал·год вне диапазона 0..{MAX_HEAT_GCAL_HOUR_RATE}")
            continue
        if row["tariff_type"] == "two_rate" and gcal_hour <= 0.0:
            errors.append(f"{label}: двухставковый тариф без умовно-постійної частини")
            continue
        if row["tariff_type"] == "one_rate" and gcal_hour > 0.0:
            errors.append(f"{label}: одноставковый тариф с непустой умовно-постійною частиною {gcal_hour}")
            continue

        cities.append({
            "city_code": "",
            "city_name": "",
            "supplier": row["supplier"],
            "tariff_type": row["tariff_type"],
            "rate_gcal": gcal,
            "rate_gcal_hour": gcal_hour,
            "unit": "Gcal",
            "effective_date": effective_date,
            "decree_info": decree_info
        })
    return cities, errors

def reject_block(kind: str, errors: list, notifier: TelegramNotifier):
    """Reports why a whole block was discarded, so the previous values stay published."""
    for err in errors:
        logger.warning(f"{kind} validation: {err}")
    details = "\n".join(f"• {e}" for e in errors[:15])
    if len(errors) > 15:
        details += f"\n… и ещё {len(errors) - 15}"
    notifier.send_message(
        f"⚠️ <b>Тарифы «{kind}» не обновлены — не пройдена валидация ({len(errors)}):</b>\n<code>{details}</code>",
        parse_mode="HTML"
    )

def extract_table_cities(page_html: str, kind: str, parse_rows, validate_rows,
                         notifier: TelegramNotifier) -> list:
    """
    Shared pipeline for the hot water and heating tables: locate the table, parse it
    deterministically and validate. Returns None when the result cannot be trusted, so the
    caller keeps the previously published data.
    """
    table_html = extract_water_table_html(page_html)
    if not table_html:
        logger.error(f"{kind} tariff table not found in the fetched page")
        notifier.send_message(
            f"⚠️ <b>Тарифы «{kind}» не обновлены:</b>\nтаблица не найдена на странице источника.",
            parse_mode="HTML"
        )
        return None

    effective_date, decree_info = parse_caption_date(page_html)
    if not effective_date:
        logger.error(f"{kind}: could not read the date stamp from the table caption")
        notifier.send_message(
            f"⚠️ <b>Тарифы «{kind}» не обновлены:</b>\nне удалось прочитать дату в заголовке таблицы.",
            parse_mode="HTML"
        )
        return None

    cities, errors = validate_rows(parse_rows(table_html), effective_date, decree_info)
    if errors:
        reject_block(kind, errors, notifier)
        return None

    logger.info(f"{kind}: {len(cities)} suppliers parsed, source dated {effective_date}")
    return cities

def extract_kyiv_hot_water(source: dict, timeout: int, notifier: TelegramNotifier) -> dict:
    """
    Reads the Kyiv hot water tariff of КП "КИЇВТЕПЛОЕНЕРГО". Its tariff is set by the city
    administration rather than by НКРЕКП, so the company is absent from the national table
    and needs this dedicated page. The page lists several service variants, and the rate the
    population actually pays is the wartime one, identical across all of them.
    """
    if not isinstance(source, dict) or not source.get("url"):
        return None

    page_html = fetch_html(source["url"], timeout=timeout)
    if not page_html:
        return None

    values = []
    for row_html in re.findall(r"<tr.*?</tr>", extract_water_table_html(page_html), flags=re.S | re.I):
        cells = table_row_cells(row_html)
        if len(cells) < 2:
            continue
        # The label is bulleted with a dash and a non-breaking space
        label = re.sub(r"^[\s –—-]+", "", cells[0]).lower()
        if not label.startswith("тариф протягом дії"):
            continue

        rate = parse_rate(cells[1])
        if rate is not None:
            values.append(rate)

    if not values:
        logger.warning("Kyiv hot water page carries no wartime tariff rows")
        notifier.send_message(
            "⚠️ <b>Горячая вода по Киеву не обновлена:</b>\n"
            "на странице КТЕ не найдено строк с тарифом на период военного положения.",
            parse_mode="HTML"
        )
        return None

    if len(set(values)) > 1:
        logger.warning(f"Kyiv hot water page lists differing wartime tariffs: {sorted(set(values))}")
        notifier.send_message(
            "⚠️ <b>Горячая вода по Киеву:</b> на странице несколько разных тарифов "
            f"на период военного положения — <code>{sorted(set(values))}</code>. Взят первый.",
            parse_mode="HTML"
        )

    return {
        "city_code": "",
        "city_name": source.get("city_name", ""),
        "supplier": source.get("supplier", ""),
        "rate": values[0],
        "unit": "m3",
        "effective_date": source.get("effective_date", ""),
        "decree_info": source.get("decree_info", "")
    }

CITY_NAME_PROMPT = """
Ты определяешь населённый пункт по названию украинского теплоснабжающего предприятия.

Для каждого поставщика из полученного списка укажи название населённого пункта на украинском
языке. Если предприятие обслуживает не город, а область или ведомственную сеть, укажи область
(например "Дніпропетровська обл."). Переписывай название поставщика в ответе дословно.
Не добавляй и не пропускай поставщиков — верни ровно столько записей, сколько получил.

Верни СТРОГО JSON без текста до и после:
{
  "cities": [
    {"supplier": "ЛМКП \\"Львівтеплоенерго\\"", "city_name": "Львів"}
  ]
}
"""

def resolve_city_names(cities: list, section: str, model_name: str,
                       notifier: TelegramNotifier) -> list:
    """
    Fills city_name from the persistent registry and asks the model only about suppliers it
    has never seen, so a steady run costs no LLM call at all. Suppliers that stay unnamed are
    dropped instead of voiding the whole block.
    """
    known = {
        normalize_name(name): entry["city_name"]
        for name, entry in load_registry(section).items()
    }
    for city in cities:
        if not city.get("city_name"):
            city["city_name"] = known.get(normalize_name(city["supplier"]), "")

    unknown = [c for c in cities if not c["city_name"]]
    if unknown:
        logger.info(f"Asking the model for the city names of {len(unknown)} new suppliers")
        answer = call_gemini_extract(
            "\n".join(c["supplier"] for c in unknown), CITY_NAME_PROMPT, model_name, notifier
        )
        named = {
            normalize_name(item.get("supplier")): str(item.get("city_name", "")).strip()
            for item in answer.get("cities", []) if isinstance(item, dict)
        }
        for city in unknown:
            city["city_name"] = named.get(normalize_name(city["supplier"]), "")

    dropped = [c["supplier"] for c in cities if not c["city_name"]]
    if dropped:
        logger.warning(f"{len(dropped)} suppliers dropped: their city could not be determined")
        notifier.send_message(
            "⚠️ <b>Не удалось определить город для поставщиков тепла</b>\n"
            "Они не попадут в JSON:\n" + "\n".join(f"• {d}" for d in dropped),
            parse_mode="HTML"
        )

    return [c for c in cities if c["city_name"]]

def resolve_heat_identity(hot_cities: list, heating_cities: list, model_name: str,
                          notifier: TelegramNotifier) -> tuple:
    """
    Assigns city_code to the hot water and heating lists in one pass over their union. The
    same company appears in both tables, so resolving them separately would report every
    heating-only supplier as gone from the hot water source and vice versa.
    """
    combined = (hot_cities or []) + (heating_cities or [])
    if not combined:
        return hot_cities, heating_cities

    # One entry per company: a duplicated supplier would compete with itself for the plain
    # city code and end up needlessly suffixed.
    unique = {}
    for city in combined:
        unique.setdefault(normalize_name(city["supplier"]), dict(city))

    resolved = resolve_city_identity(
        resolve_city_names(list(unique.values()), HEAT_REGISTRY_SECTION, model_name, notifier),
        notifier, section=HEAT_REGISTRY_SECTION,
        is_plain_owner=is_named_after_city, label="тепла"
    )
    identity = {normalize_name(c["supplier"]): c for c in resolved}

    def apply(cities):
        if cities is None:
            return None
        applied = []
        for city in cities:
            found = identity.get(normalize_name(city["supplier"]))
            if not found:
                continue
            city["city_code"] = found["city_code"]
            city["city_name"] = found["city_name"]
            applied.append(city)
        return applied

    return apply(hot_cities), apply(heating_cities)

def extract_heat_blocks(base_data: dict, ref_sources: dict, timeout: int,
                        model_name: str, notifier: TelegramNotifier) -> dict:
    """Builds the hot_water and heating blocks, keeping previous values on any failure."""
    hot_url = ref_sources.get("hot_water")
    heating_url = ref_sources.get("heating")

    hot_data = base_data.get("hot_water") or empty_city_block(hot_url)
    heat_data = base_data.get("heating") or empty_city_block(heating_url)
    hot_cities = heating_cities = None

    if hot_url:
        hot_data["source_url"] = hot_url
        logger.info(f"Fetching hot water reference from {hot_url}...")
        hot_cities = extract_table_cities(
            fetch_html(hot_url, timeout=timeout), "Горячая вода",
            hot_water_rows, validate_hot_water_rows, notifier
        )
        kyiv = extract_kyiv_hot_water(ref_sources.get("hot_water_kyiv"), timeout, notifier)
        if hot_cities is not None and kyiv:
            hot_cities.append(kyiv)

    if heating_url:
        heat_data["source_url"] = heating_url
        logger.info(f"Fetching heating reference from {heating_url}...")
        heating_cities = extract_table_cities(
            fetch_html(heating_url, timeout=timeout), "Отопление",
            heating_rows, validate_heating_rows, notifier
        )

    hot_cities, heating_cities = resolve_heat_identity(hot_cities, heating_cities, model_name, notifier)

    today = datetime.now().strftime("%Y-%m-%d")
    for url, cities, block, kind in (
        (hot_url, hot_cities, hot_data, "hot water"),
        (heating_url, heating_cities, heat_data, "heating")
    ):
        if cities:
            block["cities"] = cities
            block["update_date"] = today
        elif url:
            logger.warning(f"Keeping previous {kind} cities: extraction failed or was rejected")

    return {"hot_water": hot_data, "heating": heat_data}

def extract_reference_tariffs(config: dict, model_name: str, notifier: TelegramNotifier) -> dict:
    base_data = load_base_schema()
    ref_sources = config["reference_sources"]
    electricity_url = ref_sources["electricity"]
    water_url = ref_sources["water"]
    timeout = config.get("settings", {}).get("timeout_seconds", 15)

    logger.info(f"Fetching electricity reference from {electricity_url}...")
    elec_html = fetch_html(electricity_url, timeout=timeout)
    
    logger.info(f"Fetching water reference from {water_url}...")
    water_html = fetch_html(water_url, timeout=timeout)

    elec_prompt = """
    Извлеки из текста HTML информацию о тарифах на электроэнергию в Украине для населения.
    Верни JSON с ключами:
    {
      "base_rate": 4.32,
      "effective_date": "2024-06-01",
      "decree_info": "Постанова КМУ № 632 від 31.05.2024"
    }
    """
    elec_extracted = call_gemini_extract(elec_html[:15000], elec_prompt, model_name, notifier) if elec_html else {}
    
    elec_data = base_data.get("electricity", {})
    elec_data["source_url"] = electricity_url
    elec_data["update_date"] = datetime.now().strftime("%Y-%m-%d")

    if elec_extracted.get("base_rate") is not None:
        try:
            base_rate = float(elec_extracted["base_rate"])
            elec_data["base_rate"] = base_rate
            apply_base_rate_to_zones(elec_data, base_rate)
        except Exception as e:
            logger.warning(f"Error updating zone rates from base_rate: {e}")

    if elec_extracted.get("effective_date"):
        dt = parse_date(elec_extracted["effective_date"])
        if dt and dt.month == 5 and (dt.day == 31 or dt.day == 30):
            elec_data["effective_date"] = "2024-06-01"
        else:
            elec_data["effective_date"] = str(elec_extracted["effective_date"])

    if elec_extracted.get("decree_info"):
        elec_data["decree_info"] = str(elec_extracted["decree_info"])

    water_data = base_data.get("water", {})
    water_data["source_url"] = water_url

    water_cities = extract_water_tariffs(water_html, model_name, notifier) if water_html else None
    if water_cities:
        water_data["cities"] = water_cities
        water_data["update_date"] = datetime.now().strftime("%Y-%m-%d")
    else:
        logger.warning("Keeping previous water cities: extraction failed or was rejected by validation")

    heat_blocks = extract_heat_blocks(base_data, ref_sources, timeout, model_name, notifier)

    return {"electricity": elec_data, "water": water_data, **heat_blocks}

def search_alternative_tariffs(model_name: str, notifier: TelegramNotifier) -> dict:
    logger.info("Performing Search Grounding for alternative tariff updates...")
    prompt = """
    Найди самые последние официальные тарифы для населения Украины: электроэнергия, холодная
    вода/водоотведение, горячая вода и централизованное отопление.
    КРИТИЧЕСКИ ВАЖНО:
    1. Указывай тарифы С УЧЕТОМ НДС (ПДВ = 20%). Не бери тарифы без НДС!
    2. По электроэнергии дата вступления в силу Постановления КМУ №632 — 2024-06-01 (1 июня 2024 года).
    3. Указывай только числовые значения для тарифов (например 4.32 вместо "4.32 UAH").
    4. По горячей воде и отоплению нужен тариф, который РЕАЛЬНО ПЛАТИТ НАСЕЛЕНИЕ на период
       военного положения, а не економічно обґрунтований тариф.
    5. По Киеву бери тарифы КП "КИЇВТЕПЛОЕНЕРГО" — это основной поставщик тепла города.

    Верни результаты СТРОГО в формате JSON (без текстов до или после JSON):
    {
      "electricity": {
        "found_url": "https://index.minfin.com.ua/tariff/electric/",
        "base_rate": 4.32,
        "effective_date": "2024-06-01",
        "decree_info": "Постанова КМУ № 632 від 31.05.2024"
      },
      "water": {
        "found_url": "https://index.minfin.com.ua/ua/tariff/water/",
        "kyiv_total_rate": 30.384,
        "effective_date": "2022-01-01",
        "decree_info": "Постанова НКРЕКП № 2842"
      },
      "hot_water": {
        "found_url": "https://index.minfin.com.ua/ua/tariff/kiev/hotwater/",
        "kyiv_rate": 97.89,
        "effective_date": "2022-10-01",
        "decree_info": "Розпорядження КМВА № 673 від 30.09.2022"
      },
      "heating": {
        "found_url": "https://kte.kmda.gov.ua/tarufu/",
        "kyiv_rate_gcal": 1654.41,
        "effective_date": "2022-10-01",
        "decree_info": "Розпорядження КМВА № 673 від 30.09.2022"
      }
    }
    """
    search_data = call_gemini_search(
        "актуальні тарифи для населення Україна 2026: електроенергія, вода, гаряча вода, опалення",
        prompt, model_name, notifier
    )
    return search_data

def rate_discrepancy(category: str, ref_rate, ref_date_str, ref_url,
                     found: dict, rate_key: str) -> dict:
    """
    Compares one reference value against what the search found. Returns a discrepancy
    record, or None when the two agree closely enough to say nothing.
    """
    found_rate = parse_rate(found.get(rate_key))
    found_date_str = found.get("effective_date")
    ref_dt, found_dt = parse_date(ref_date_str), parse_date(found_date_str)

    rate_changed = bool(found_rate is not None and ref_rate is not None and abs(found_rate - ref_rate) > 0.05)
    date_significantly_newer = bool(ref_dt and found_dt and (found_dt - ref_dt).days > 3)

    if not (rate_changed or date_significantly_newer):
        return None

    logger.info(
        f"{category} discrepancy detected: ref_rate={ref_rate}, found_rate={found_rate}, "
        f"ref_date={ref_date_str}, found_date={found_date_str}"
    )
    return {
        "category": category,
        "ref_rate": ref_rate,
        "ref_effective_date": ref_date_str,
        "ref_url": ref_url,
        "found_rate": found_rate,
        "found_effective_date": found_date_str,
        "found_url": found.get("found_url"),
        "found_decree": found.get("decree_info")
    }

# Per-city blocks cross-checked against the search, keyed by the city the search is asked about.
CITY_BLOCK_CHECKS = (
    ("water", "Водоснабжение (Киев)", "total_rate", "kyiv_total_rate"),
    ("hot_water", "Горячая вода (Киев)", "rate", "kyiv_rate"),
    ("heating", "Отопление (Киев)", "rate_gcal", "kyiv_rate_gcal"),
)

def compare_and_validate(ref_data: dict, search_data: dict) -> list:
    discrepancies = []
    search_data = search_data or {}

    ref_elec = ref_data.get("electricity", {})
    search_elec = dict(search_data.get("electricity") or {})
    if search_elec:
        # Decree No.632 is dated 31.05.2024 but takes effect on 01.06.2024, and sources quote
        # either date, so the found date is normalised before it is compared.
        found_dt = parse_date(search_elec.get("effective_date"))
        if found_dt and found_dt.month == 5 and found_dt.day in (30, 31):
            search_elec["effective_date"] = "2024-06-01"

        found = rate_discrepancy(
            "Электроэнергия", parse_rate(ref_elec.get("base_rate")),
            ref_elec.get("effective_date"), ref_elec.get("source_url"),
            search_elec, "base_rate"
        )
        if found:
            discrepancies.append(found)

    for block, category, ref_key, search_key in CITY_BLOCK_CHECKS:
        search_block = search_data.get(block) or {}
        if not search_block:
            continue

        ref_block = ref_data.get(block, {})
        ref_kyiv = next((c for c in ref_block.get("cities", []) if c.get("city_code") == "kyiv"), {})
        found = rate_discrepancy(
            category, parse_rate(ref_kyiv.get(ref_key)),
            ref_kyiv.get("effective_date"), ref_block.get("source_url"),
            search_block, search_key
        )
        if found:
            discrepancies.append(found)

    return discrepancies

def main(notifier: TelegramNotifier = None) -> dict:
    """Runs the whole Ukrainian pipeline and writes both output files."""
    country = load_country(COUNTRY_CODE)
    notifier = notifier or TelegramNotifier()
    config = load_config()

    model_name = resolve_latest_gemini_model(config)
    logger.info(f"Resolved Gemini model for execution: '{model_name}'")

    ref_data = extract_reference_tariffs(config, model_name, notifier)
    ref_data = apply_manual_overrides(ref_data, config, notifier)

    search_data = search_alternative_tariffs(model_name, notifier)
    discrepancies = compare_and_validate(ref_data, search_data)

    # Reference data is always persisted; discrepancies only trigger a notification,
    # so an alternative source disagreeing never blocks the update.
    final_json = build_root(country, ref_data)
    save_country_json(country, final_json)

    if discrepancies:
        logger.warning(f"Found {len(discrepancies)} tariff discrepancies across sources!")
        summary = {
            "check_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "categories": [d["category"] for d in discrepancies]
        }
        notifier.send_discrepancy_report(discrepancies, summary)
    else:
        logger.info("No discrepancies found. Reference data matches or is up to date.")

    return final_json
