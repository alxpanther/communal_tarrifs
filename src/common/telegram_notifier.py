import os
import logging
import requests

# No basicConfig here: a library module must not take over the entry point's logging setup.
logger = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured():
            logger.warning("Telegram Bot Token or Chat ID not configured. Skipping notification.")
            print("\n--- TELEGRAM MESSAGE START ---")
            print(text)
            print("--- TELEGRAM MESSAGE END ---\n")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                logger.info("Telegram notification sent successfully.")
                return True
            else:
                logger.error(f"Failed to send Telegram message: {res.status_code} - {res.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending message to Telegram: {e}")
            return False

    def send_discrepancy_report(self, discrepancies: list, summary_info: dict) -> bool:
        """
        Sends a structured report of tariff discrepancies found across sources.
        """
        html = "<b>⚠️ Обнаружены расхождения в тарифах ЖКХ (Украина)!</b>\n\n"
        html += f"<b>Дата проверки:</b> {summary_info.get('check_date', 'N/A')}\n"
        html += f"<b>Категории с расхождениями:</b> {', '.join(summary_info.get('categories', []))}\n\n"
        html += "<b>📋 Сводная таблица источников:</b>\n\n"

        for item in discrepancies:
            category = item.get("category", "Неизвестно").upper()
            ref_rate = item.get("ref_rate", "N/A")
            ref_date = item.get("ref_effective_date", "N/A")
            ref_url = item.get("ref_url", "")

            found_rate = item.get("found_rate", "N/A")
            found_date = item.get("found_effective_date", "N/A")
            found_url = item.get("found_url", "")
            decree = item.get("found_decree", "Не указано")

            html += f"<b>🔹 Категория: {category}</b>\n"
            html += f"• <b>Референсный источник:</b> {ref_url}\n"
            html += f"  - Тариф: <code>{ref_rate} UAH</code>\n"
            html += f"  - Дата вступления в силу: <code>{ref_date}</code>\n"
            html += f"• <b>Найденный источник:</b> {found_url}\n"
            html += f"  - Тариф: <code>{found_rate} UAH</code>\n"
            html += f"  - Дата вступления в силу: <code>{found_date}</code>\n"
            html += f"  - Постановление: <i>{decree}</i>\n\n"

        html += "⚙️ <b>Действие:</b>\n"
        html += "Если найденный источник более достоверный, добавьте URL в <code>config/sources.json</code> в секцию <code>manual_override</code> и перезапустите скрипт."

        return self.send_message(html, parse_mode="HTML")
