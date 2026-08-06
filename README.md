# Ukraine Utility Tariffs Automation Pipeline

Интеллектуальная система автоматического сбора, AI-сравнения, отправки отчетов в Telegram и публикации тарифов ЖКХ Украины для Android приложения.

## 🚀 Возможности
1. **Мульти-источниковый сбор:** Забор данных с референсных сайтов (все URLs конфигурируются в `config/sources.json`, никаких зашитых строк в коде).
2. **AI-валидация и веб-поиск (Gemini Search Grounding):** Скрипт через Gemini анализирует альтернативные источники и проверяет даты вступления в силу тарифов (постановления НКРЕКП / Кабмина).
3. **Автоматическое динамическое определение актуальной модели Gemini:** Скрипт перед запуском вызывает `client.models.list()`, отбирает самые свежие доступные модели семейства Flash (например, `gemini-2.5-flash`, `gemini-3.6-flash` и т.д.) и сортирует их по номеру версии, избавляя вас от необходимости переписывать код при выходе новых версий моделей Google.
4. **Сравнение расхождений:** Если найдены новые тарифы или дата вступления в силу на сторонних сайтах позже референсных, формируется сводная таблица с указанием URLs и высылается в **Telegram**.
5. **Единообразные источники и Ручное переопределение (Manual Override):** Все сущности (`electricity`, `water`, `water.cities.<city_code>`) используют единообразное имя поля `source_url`.
6. **Запуск и Деплой в Docker:** Сбор тарифов и деплой в Cloudflare R2 в 1 команду.
7. **Автоматический запуск 25-го числа каждого месяца:** Настроен крон в GitHub Actions.
8. **Двойной мульти-деплой (Cloudflare R2 + GitHub Pages):** Файл `tariffs_ua.json` мгновенно публицируется на Cloudflare R2 и GitHub Pages.
9. **Жёсткая валидация тарифов на воду:** Ответ модели сверяется с исходной таблицей — каждая тройка «водопостачання / водовідведення / разом» должна встречаться в источнике именно в таком порядке, количество строк обязано совпадать, одна и та же строка не может быть извлечена дважды. Если хоть что-то не сошлось, старые данные остаются нетронутыми, а в Telegram уходит перечень претензий.
10. **Текстовые поля берутся из источника, а не из ответа модели:** Тройка чисел служит ключом связи со строкой таблицы, после чего `supplier` и период действия подставляются из самого HTML. Модель регулярно «исправляет» непривычные украинские названия (`Словміськводоканал` → `Словмісьководоканал`), но в JSON попадает только написание с сайта.
11. **Стабильные `city_code` (`config/city_registry.json`):** Идентификаторы городов не зависят от ответа модели — они хранятся в постоянном реестре и после первого назначения никогда не меняются. Android-приложение хранит `city_code` как выбор пользователя, поэтому его «дрейф» между запусками недопустим.

---

## 🔒 Реестр городов (`config/city_registry.json`)

Файл сопоставляет название поставщика с сайта-источника постоянному `city_code` и `city_name`:

```json
{
  "suppliers": {
    "ПАТ АК \"Київводоканал\"": { "city_code": "kyiv", "city_name": "Київ" }
  }
}
```

Правила работы:

* Реестр **обязан быть в git** — GitHub Actions коммитит его вместе с файлами тарифов. Без этого CI начнёт с пустого реестра и выдаст другие коды.
* Уже назначенный `city_code` скрипт не перезаписывает никогда, что бы ни вернула модель.
* Новый поставщик на сайте → код генерируется транслитерацией по постанові КМУ № 55 від 27.01.2010 (чистая функция на Python, не LLM), дописывается в реестр и уходит уведомление в Telegram.
* Поставщик пропал с сайта → запись остаётся в реестре, но выпадает из JSON; в Telegram уходит предупреждение, потому что у пользователей с этим `city_code` выбор перестанет работать.
* Коды можно править вручную — но только осознанно и вместе с миграцией в Android-приложении.

---

## 🔑 Как получить Gemini API Key

Для работы AI-сравнения и автоматического веб-поиска требуется бесплатный ключ Gemini API.

### Пошаговая инструкция:
1. Перейдите в **Google AI Studio**: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. Войдите под своим аккаунтом Google.
3. Нажмите синюю кнопку **"Create API key"** (или **"Get API key"**).
4. Выберите существующий Google Cloud проект или нажмите **"Create API key in new project"**.
5. Скопируйте сгенерированный ключ (строка вида `AIzaSy...`).
6. Вставьте ключ в ваш файл `.env`.

---

## ☁️ Деплой в Cloudflare (CF) через Docker

Для деплоя файла `docs/tariffs_ua.json` в ваш Cloudflare R2 бакет `kommeter` используйте сервисы Docker Compose:

### 1. Генерация тарифов + автоматический деплой в Cloudflare R2:
```bash
docker compose up --build
```

### 2. Запуск ТОЛЬКО деплоя файла в Cloudflare R2:
```bash
docker compose run --rm tariffs-deploy
```

> 💡 **Справка:** В файле `.env` должны быть указаны секреты:
> ```env
> CLOUDFLARE_API_TOKEN=your_token_here
> CLOUDFLARE_ACCOUNT_ID=your_account_id_here
> ```

---

## 🌐 Настройка GitHub Pages для Android приложения

Чтобы GitHub Actions мог выкладывать `tariffs_ua.json` на GitHub Pages, сделайте единоразовую настройку в репозитории:

1. Откройте ваш репозиторий на GitHub.
2. Перейдите в **Settings** $\rightarrow$ **Pages** (в левом меню).
3. В разделе **Build and deployment** $\rightarrow$ **Source** выберите: **`GitHub Actions`**.

---

## 🛠️ Способы запуска

### Вариант 1. Запуск через Docker (Рекомендуемый)

```bash
# Генерация файла тарифов
docker compose run --rm tariffs-fetcher

# Деплой в Cloudflare R2
docker compose run --rm tariffs-deploy
```

---

### Вариант 2. Локальный запуск на Python

```bash
# 1. Установите зависимости
pip install -r requirements.txt

# 2. Запустите скрипт
python src/tariffs_fetcher.py
```

---

### Вариант 3. Автоматический запуск через GitHub Actions

В файле `.github/workflows/fetch_tariffs.yml` настроено расписание:
- **Крон:** `0 0 25 * *` (каждое **25-е число месяца в 00:00 UTC**).
- **Мульти-деплой:** Скрипт публикует файл сразу и на **Cloudflare R2** (`kommeter/ua/tariffs_ua.json`), и на **GitHub Pages**.
- Можно запустить вручную во вкладке **Actions $\rightarrow$ Fetch and Update Tariffs $\rightarrow$ Run workflow**.

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
    "water": "https://index.minfin.com.ua/ua/tariff/water/"
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
      "source_url": "https://index.minfin.com.ua/ua/tariff/water/",
      "cities": {
        "kyiv": {
          "water_supply": 16.164,
          "sewage": 14.22,
          "total_rate": 30.384,
          "effective_date": "2022-01-01",
          "decree_info": "Тариф НКРЕКП, чинний з 01.01.2022"
        }
      }
    }
  }
}
```

---

## 📱 Интеграция с Android и Спецификация JSON

Полное руководство по интеграции, детальное описание всех полей JSON, готовые **Kotlin Data Classes** и формулы расчетов для учета счетчиков находятся в отдельном документе:
👉 **[Документация и Спецификация JSON тарифов (docs/JSON_SPECIFICATION.md)](docs/JSON_SPECIFICATION.md)**

### Краткая сводка по интеграции:
1. **Локальный кэш (Offline Fallback):** Положите стартовый `assets/tariffs_ua_default.json` в локальные `assets` Android-приложения на случай отсутствия интернета.
2. **Удаленное обновление (Remote Sync):** При наличии интернета выкачивайте обновленный файл по любому из доступных URL:
   * **Cloudflare / R2 CDN:** `https://tarrifs.foleks.com/ua/tariffs_ua.json`
   * **GitHub Pages:** `https://alxpanther.github.io/communal_tarrifs/tariffs_ua.json`
3. **Парсинг и Модели:** Для быстрого создания моделей данных в Android используйте Kotlin DTO из [docs/JSON_SPECIFICATION.md](docs/JSON_SPECIFICATION.md#3-готовые-kotlin-data-classes-kotlinxserialization).

