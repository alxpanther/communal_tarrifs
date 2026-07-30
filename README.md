# Ukraine Utility Tariffs Automation Pipeline

Интеллектуальная система автоматического сбора, AI-сравнения, отправки отчетов в Telegram и публикации тарифов ЖКХ Украины для Android приложения.

## 🚀 Возможности
1. **Мульти-источниковый сбор:** Забор данных с референсных сайтов (все URLs конфигурируются в `config/sources.json`, никаких зашитых строк в коде).
2. **AI-валидация и веб-поиск (Gemini Search Grounding):** Скрипт через Gemini анализирует альтернативные источники и проверяет даты вступления в силу тарифов (постановления НКРЕКП / Кабмина).
3. **Автоматическое динамическое определение актуальной модели Gemini:** Скрипт перед запуском вызывает `client.models.list()`, отбирает самые свежие доступные модели семейства Flash (например, `gemini-2.5-flash`, `gemini-3.0-flash` и т.д.) и сортирует их по номеру версии, избавляя вас от необходимости переписывать код при выходе новых версий моделей Google.
4. **Сравнение расхождений:** Если найдены новые тарифы или дата вступления в силу на сторонних сайтах позже референсных, формируется сводная таблица с указанием URLs и высылается в **Telegram**.
5. **Единообразные источники и Ручное переопределение (Manual Override):** Все сущности (`electricity`, `water`, `water.cities.<city_code>`) используют единообразное имя поля `source_url`.
6. **Запуск в Docker:** Возможность локального запуска через `docker compose` в один клик.
7. **Бесплатный хостинг для 100k+ пользователей:** Автоматическая публикация на **Cloudflare Pages** (0$ затрат на трафик).

---

## 🔑 Как получить Gemini API Key

Для работы AI-сравнения и автоматического веб-поиска требуется бесплатный ключ Gemini API.

### Пошаговая инструкция:
1. Перейдите в **Google AI Studio**: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. Войдите под своим аккаунтом Google.
3. Нажмите синюю кнопку **"Create API key"** (или **"Get API key"**).
4. Выберите существенный Google Cloud проект или нажмите **"Create API key in new project"**.
5. Скопируйте сгенерированный ключ (строка вида `AIzaSy...`).
6. Вставьте ключ в ваш файл `.env`.

---

## 🛠️ Способы запуска

### Вариант 1. Запуск через Docker (Рекомендуемый)

Так как у вас уже создан файл `.env`, запустите сборку и генерацию в 1 команду:

```bash
docker compose up --build
```
> 💡 **Как это работает:** Результаты генерации (`assets/tariffs_default.json` и `tariffs.json`) благодаря Volume Mount мгновенно сохранятся прямо у вас на компьютере в папках проекта!

---

### Вариант 2. Локальный запуск на Python

```bash
# 1. Установите зависимости
pip install -r requirements.txt

# 2. Запустите скрипт
python src/tariffs_fetcher.py
```

---

## ⚙️ Управление источниками и моделями (`config/sources.json`)

```json
{
  "settings": {
    "auto_select_latest_model": true,
    "gemini_model": "gemini-2.5-flash",
    "timeout_seconds": 15
  },
  "reference_sources": {
    "electricity": "https://tariffa.com.ua/ru/tarif-na-elektroenergiy",
    "water": "https://index.minfin.com.ua/tariff/water/"
  },
  "manual_override": {
    "enabled": false,
    "electricity": {
      "source_url": "https://kmu.gov.ua/decree-632",
      "base_rate": 4.32,
      "effective_date": "2024-06-01",
      "decree_info": "Постанова КМУ № 632"
    },
    "water": {
      "source_url": "https://index.minfin.com.ua/tariff/water/",
      "cities": {
        "kyiv": {
          "source_url": "https://vodokanal.kiev.ua/tarifi/",
          "water_supply": 22.884,
          "sewage": 16.548,
          "total_rate": 39.432,
          "effective_date": "2022-01-01",
          "decree_info": "Постанова НКРЕКП № 2842"
        }
      }
    }
  }
}
```

---

## 📱 Интеграция с Android

1. Скопируйте файл `assets/tariffs_default.json` в папку `app/src/main/assets/tariffs_default.json` вашего Android проекта.
2. Раз в неделю в приложении выкачивайте актуальный JSON по вашему Cloudflare Pages URL: `https://your-app.pages.dev/tariffs.json`.
