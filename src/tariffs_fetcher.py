import os
import json
import logging
import re
from datetime import datetime
import requests
from dotenv import load_dotenv

from telegram_notifier import TelegramNotifier

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TariffsFetcher")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "sources.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "tariffs_ua_default.json")
ROOT_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "tariffs_ua.json")
ORIG_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "tariffs_ua.json")

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
    candidate_paths = [ORIG_OUTPUT_PATH, OUTPUT_PATH, ROOT_OUTPUT_PATH]
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
        "water": {
            "source_url": "https://index.minfin.com.ua/tariff/water/",
            "update_date": datetime.now().strftime("%Y-%m-%d"),
            "cities": []
        }
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
            
            zones = elec_data.get("zones", {})
            if "two_zone" in zones and isinstance(zones["two_zone"], dict):
                tz = zones["two_zone"]
                if "day" in tz and isinstance(tz["day"], dict) and "coefficient" in tz["day"]:
                    tz["day"]["rate"] = round(base_rate * float(tz["day"]["coefficient"]), 4)
                if "night" in tz and isinstance(tz["night"], dict) and "coefficient" in tz["night"]:
                    tz["night"]["rate"] = round(base_rate * float(tz["night"]["coefficient"]), 4)

            if "three_zone" in zones and isinstance(zones["three_zone"], dict):
                thz = zones["three_zone"]
                if "peak" in thz and isinstance(thz["peak"], dict) and "coefficient" in thz["peak"]:
                    thz["peak"]["rate"] = round(base_rate * float(thz["peak"]["coefficient"]), 4)
                if "half_peak" in thz and isinstance(thz["half_peak"], dict) and "coefficient" in thz["half_peak"]:
                    thz["half_peak"]["rate"] = round(base_rate * float(thz["half_peak"]["coefficient"]), 4)
                if "night" in thz and isinstance(thz["night"], dict) and "coefficient" in thz["night"]:
                    thz["night"]["rate"] = round(base_rate * float(thz["night"]["coefficient"]), 4)
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
    water_data["update_date"] = datetime.now().strftime("%Y-%m-%d")

    return {"electricity": elec_data, "water": water_data}

def search_alternative_tariffs(model_name: str, notifier: TelegramNotifier) -> dict:
    logger.info("Performing Search Grounding for alternative tariff updates...")
    prompt = """
    Найди самые последние официальные тарифы на электроэнергию и холодную воду/водоотведение в Украине для населения.
    КРИТИЧЕСКИ ВАЖНО:
    1. Указывай тарифы С УЧЕТОМ НДС (ПДВ = 20%). Не бери тарифы без НДС!
    2. По электроэнергии дата вступления в силу Постановления КМУ №632 — 2024-06-01 (1 июня 2024 года).
    3. Указывай только числовые значения для тарифов (например 4.32 вместо "4.32 UAH").

    Верни результаты СТРОГО в формате JSON (без текстов до или после JSON):
    {
      "electricity": {
        "found_url": "https://index.minfin.com.ua/tariff/electric/",
        "base_rate": 4.32,
        "effective_date": "2024-06-01",
        "decree_info": "Постанова КМУ № 632 від 31.05.2024"
      },
      "water": {
        "found_url": "https://index.minfin.com.ua/tariff/water/",
        "kyiv_total_rate": 39.432,
        "effective_date": "2022-01-01",
        "decree_info": "Постанова НКРЕКП № 2842"
      }
    }
    """
    search_data = call_gemini_search("актуальні тарифы на електроенергію та воду для населения Украина 2026", prompt, model_name, notifier)
    return search_data

def compare_and_validate(ref_data: dict, search_data: dict) -> list:
    discrepancies = []
    
    # Check Electricity
    ref_elec = ref_data.get("electricity", {})
    search_elec = search_data.get("electricity", {}) if search_data else {}
    
    if search_elec:
        ref_rate = parse_rate(ref_elec.get("base_rate"))
        found_rate = parse_rate(search_elec.get("base_rate"))
        ref_date_str = ref_elec.get("effective_date")
        found_date_str = search_elec.get("effective_date")

        ref_dt = parse_date(ref_date_str)
        found_dt = parse_date(found_date_str)

        if found_dt and found_dt.month == 5 and found_dt.day in (30, 31):
            found_dt = datetime(found_dt.year, 6, 1)
            found_date_str = "2024-06-01"

        rate_increased = bool(found_rate is not None and ref_rate is not None and (found_rate - ref_rate) > 0.05)
        date_significantly_newer = bool(ref_dt and found_dt and (found_dt - ref_dt).days > 3)

        if rate_increased or date_significantly_newer:
            logger.info(f"Electricity discrepancy detected: ref_rate={ref_rate}, found_rate={found_rate}, ref_date={ref_date_str}, found_date={found_date_str}")
            discrepancies.append({
                "category": "Электроэнергия",
                "ref_rate": ref_rate,
                "ref_effective_date": ref_date_str,
                "ref_url": ref_elec.get("source_url"),
                "found_rate": found_rate,
                "found_effective_date": found_date_str,
                "found_url": search_elec.get("found_url"),
                "found_decree": search_elec.get("decree_info")
            })

    # Check Water
    ref_water = ref_data.get("water", {})
    search_water = search_data.get("water", {}) if search_data else {}
    if search_water:
        ref_kyiv = next((c for c in ref_water.get("cities", []) if c.get("city_code") == "kyiv"), {})
        ref_rate = parse_rate(ref_kyiv.get("total_rate"))
        found_rate = parse_rate(search_water.get("kyiv_total_rate"))
        ref_date_str = ref_kyiv.get("effective_date")
        found_date_str = search_water.get("effective_date")

        ref_dt = parse_date(ref_date_str)
        found_dt = parse_date(found_date_str)

        rate_increased = bool(found_rate is not None and ref_rate is not None and (found_rate - ref_rate) > 0.05)
        date_significantly_newer = bool(ref_dt and found_dt and (found_dt - ref_dt).days > 3)

        if rate_increased or date_significantly_newer:
            logger.info(f"Water discrepancy detected: ref_rate={ref_rate}, found_rate={found_rate}, ref_date={ref_date_str}, found_date={found_date_str}")
            discrepancies.append({
                "category": "Водоснабжение (Киев)",
                "ref_rate": ref_rate,
                "ref_effective_date": ref_date_str,
                "ref_url": ref_water.get("source_url"),
                "found_rate": found_rate,
                "found_effective_date": found_date_str,
                "found_url": search_water.get("found_url"),
                "found_decree": search_water.get("decree_info")
            })

    return discrepancies

def build_final_json(ref_data: dict) -> dict:
    return {
        "version": "1.0",
        "last_updated_at": datetime.now().isoformat(),
        "country": "UA",
        "currency": "UAH",
        "electricity": ref_data.get("electricity", {}),
        "water": ref_data.get("water", {})
    }

def save_json(data: dict):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    with open(ROOT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Tariffs JSON saved successfully to {OUTPUT_PATH} and {ROOT_OUTPUT_PATH}")

def main():
    notifier = TelegramNotifier()
    try:
        config = load_config()
    except Exception as e:
        err_msg = f"💥 <b>Фатальная ошибка конфигурации тарифов:</b>\n<code>{str(e)}</code>"
        logger.critical(err_msg)
        notifier.send_message(err_msg, parse_mode="HTML")
        return

    model_name = resolve_latest_gemini_model(config)
    logger.info(f"Resolved Gemini model for execution: '{model_name}'")

    manual = config.get("manual_override", {})

    if manual.get("enabled"):
        logger.info("MANUAL OVERRIDE IS ENABLED. Merging manual overrides...")
        ref_data = extract_reference_tariffs(config, model_name, notifier)
        
        # Override Electricity
        elec_override = manual.get("electricity", {})
        if elec_override.get("source_url"):
            ref_data["electricity"]["source_url"] = elec_override["source_url"]
        if elec_override.get("base_rate") is not None:
            ref_data["electricity"]["base_rate"] = elec_override["base_rate"]
        if elec_override.get("effective_date"):
            ref_data["electricity"]["effective_date"] = elec_override["effective_date"]
        if elec_override.get("decree_info"):
            ref_data["electricity"]["decree_info"] = elec_override["decree_info"]

        # Override Water
        water_override = manual.get("water", {})
        if water_override.get("source_url"):
            ref_data["water"]["source_url"] = water_override["source_url"]

        # Override Water Cities
        water_cities_override = water_override.get("cities", {})
        if water_cities_override:
            for city in ref_data.get("water", {}).get("cities", []):
                code = city.get("city_code")
                if code in water_cities_override:
                    fields = water_cities_override[code]
                    for k, v in fields.items():
                        if v is not None:
                            city[k] = v
        
        final_json = build_final_json(ref_data)
        save_json(final_json)
        return

    ref_data = extract_reference_tariffs(config, model_name, notifier)
    search_data = search_alternative_tariffs(model_name, notifier)
    discrepancies = compare_and_validate(ref_data, search_data)

    if discrepancies:
        logger.warning(f"Found {len(discrepancies)} tariff discrepancies across sources!")
        summary = {
            "check_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "categories": [d["category"] for d in discrepancies]
        }
        notifier.send_discrepancy_report(discrepancies, summary)
    else:
        logger.info("No discrepancies found. Reference data matches or is up to date.")
        final_json = build_final_json(ref_data)
        save_json(final_json)

if __name__ == "__main__":
    main()
