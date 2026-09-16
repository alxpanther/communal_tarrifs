# Структура проекта

> **Язык:** русский — зеркало для чтения человеком.
> Каноническая версия: [../en/PROJECT_STRUCTURE.md](../en/PROJECT_STRUCTURE.md), именно её читают AI-агенты.
> Оба файла обязаны совпадать по смыслу; см. [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

Этот репозиторий — **генератор данных**, а не приложение. Он собирает официальные тарифы ЖКХ,
валидирует их и публикует по одному JSON-файлу на страну плюс индекс опубликованных стран — всё это
читает Android-приложение. Кода приложения здесь нет.

Страны живут рядом друг с другом: у каждой своя папка конфигурации, свой модуль пайплайна и свой
выходной файл, а всё, что не зависит от страны, они делят между собой.

---

## 1. Карта каталогов

```
kommeter_scripts/
├── AGENTS.md                     # Точка входа для AI-агентов (тонкая ссылка на CLAUDE.md)
├── CLAUDE.md                     # Точка входа для AI-агентов: что прочитать перед первым действием
├── README.md                     # Руководство для человека (рус.): установка, запуск, manual_override
├── requirements.txt              # Python-зависимости пайплайна
├── Dockerfile                    # Образ, запускающий src/run_country.py
├── Dockerfile.wrangler           # Образ, выкладывающий JSON-файлы в Cloudflare R2
├── docker-compose.yml            # Два сервиса: tariffs-fetcher, tariffs-deploy
├── wrangler.toml                 # Проект Cloudflare: бакет R2 + ./docs как статика
├── .env                          # Секреты, в git не попадает (см. раздел 4)
│
├── .agents/rules/main_rules.md   # Постоянные правила для любого AI-агента в этом репозитории
│
├── .github/workflows/
│   ├── fetch_tariffs.yml         # Ежемесячный cron: прогнать все страны, коммит, деплой R2 + Pages
│   └── collect_cities.yml        # Вручную: названные города одной страны, пробный прогон или публикация
│
├── config/                       # Входная конфигурация — единственное, что правится руками
│   ├── countries.json            # Реестр стран: коды, названия, валюта, раскладка публикации
│   ├── ua/
│   │   ├── sources.json          # URL источников, настройки модели, manual_override
│   │   └── city_registry.json    # Постоянный реестр «поставщик → city_code» (коды не переписываем)
│   ├── am/{sources.json, city_registry.json}
│   ├── az/{sources.json, city_registry.json}
│   ├── md/{sources.json, city_registry.json}
│   ├── uz/{sources.json, city_registry.json}
│   ├── kz/{sources.json, city_registry.json}
│   ├── by/{sources.json, city_registry.json}
│   ├── ge/{sources.json, city_registry.json}
│   ├── kg/{sources.json, city_registry.json}
│   ├── tj/{sources.json, city_registry.json}
│   ├── tm/city_registry.json   # выведенная страна: сохранён только реестр городов
│   └── ru/{sources.json, city_registry.json}
│
├── src/                          # Код пайплайнов
│   ├── run_country.py            # Точка входа: одна страна, несколько или все, затем индекс
│   ├── run_city.py               # Один город или одна услуга; по умолчанию без записи
│   ├── check_sources.py          # Проверка, открываются ли источники; без модели
│   ├── build_index.py            # Собирает tariffs_index.json для каждой цели публикации
│   ├── common/                   # Общий код, не зависящий от страны
│   │   ├── paths.py              # Все пути, выведенные из кода страны
│   │   ├── countries.py          # Чтение config/countries.json
│   │   ├── jsonio.py             # Предыдущий файл, корневой объект, запись обоих выходных файлов
│   │   ├── ai_pipeline.py        # Пайплайн сбора по городам
│   │   ├── fetching.py           # Загрузка источника (HTML, PDF, скан)
│   │   ├── llm/                  # Модель извлечения: общий интерфейс, модуль на провайдера
│   │   ├── pdf.py                # PDF для провайдера, который его не читает
│   │   ├── prompts.py            # О чём спрашивают модель
│   │   ├── gas.py                # Газ: предложения, доставка, нормы и их проверки
│   │   ├── validation.py         # Можно ли публиковать извлечённое
│   │   ├── overrides.py          # Семантика manual_override, одинаковая для всех стран
│   │   ├── registry.py           # Реестр city_code: чтение, сверка, добавление
│   │   └── telegram_notifier.py  # Отправка алертов и отчётов о расхождениях в Telegram
│   └── countries/
│       ├── ua/fetcher.py         # Украина: сбор → разбор → валидация → сохранение
│       ├── am/fetcher.py         # Армения: по городам, через common/ai_pipeline.py
│       ├── az/fetcher.py         # Азербайджан: по городам, через common/ai_pipeline.py
│       ├── md/fetcher.py         # Молдова: по городам, через common/ai_pipeline.py
│       ├── uz/fetcher.py         # Узбекистан: по городам, через common/ai_pipeline.py
│       ├── kz/fetcher.py         # Казахстан: по городам, через common/ai_pipeline.py
│       ├── by/fetcher.py         # Беларусь: по городам, через common/ai_pipeline.py
│       ├── ge/fetcher.py         # Грузия: по городам, через common/ai_pipeline.py
│       ├── kg/fetcher.py         # Кыргызстан: по городам, через common/ai_pipeline.py
│       ├── tj/fetcher.py         # Таджикистан: по городам, через common/ai_pipeline.py
│       └── ru/fetcher.py         # Россия: по городам, через common/ai_pipeline.py
│
├── assets/                       # Генерируется. Оффлайн-файлы, вшиваемые в Android-приложение
│   ├── tariffs_ua_default.json
│   ├── tariffs_am_default.json
│   ├── tariffs_az_default.json
│   ├── tariffs_md_default.json
│   ├── tariffs_uz_default.json
│   ├── tariffs_kz_default.json
│   ├── tariffs_by_default.json
│   ├── tariffs_ge_default.json
│   ├── tariffs_kg_default.json
│   ├── tariffs_tj_default.json
│   └── tariffs_ru_default.json
│
├── dist/cloudflare/
│   └── tariffs_index.json        # Генерируется. Копия индекса для R2 (со своими значениями `path`)
│
└── docs/                         # Документация + опубликованные данные (эта папка — веб-корень)
    ├── tariffs_ua.json           # Генерируется. Раздаётся GitHub Pages и дублируется в R2
    ├── tariffs_am.json           # Генерируется
    ├── tariffs_az.json           # Генерируется
    ├── tariffs_md.json           # Генерируется
    ├── tariffs_uz.json           # Генерируется
    ├── tariffs_kz.json           # Генерируется
    ├── tariffs_by.json           # Генерируется
    ├── tariffs_ge.json           # Генерируется
    ├── tariffs_kg.json           # Генерируется
    ├── tariffs_tj.json           # Генерируется
    ├── tariffs_ru.json           # Генерируется
    ├── tariffs_index.json        # Генерируется. Копия индекса стран для GitHub Pages
    ├── README.md                 # Индекс документации
    ├── en/                       # Английская документация — каноническая, её читают AI-агенты
    │   ├── PROJECT_STRUCTURE.md  # Этот файл
    │   ├── ARCHITECTURE.md       # Как работают пайплайны, по шагам
    │   ├── JSON_SPECIFICATION.md # Контракт выхода: все поля, Kotlin-DTO, формулы, индекс стран
    │   ├── ADDING_A_COUNTRY.md   # Как добавить пайплайн тарифов для ещё одной страны
    │   ├── DOCUMENTATION_RULES.md# Как поддерживать документацию и структуру
    │   └── ANDROID_MIGRATION.md  # Задание для Android-стороны (горячая вода + отопление)
    └── ru/                       # Русское зеркало, те же файлы, для владельца проекта
```

---

## 2. За что отвечает каждая часть

### `config/` — единственный вход, правимый руками

| Файл | Кто владеет | Правила |
|---|---|---|
| `countries.json` | Владелец | Реестр публикуемых стран: код, `country_names`, валюта, `enabled`, `min_app_version`, модуль пайплайна и раскладка публикации каждого хоста. Из него собираются обе копии `tariffs_index.json`, из него же каждый пайплайн берёт корневые поля. Страны, которой здесь нет, не существует для публикации. |
| `<cc>/sources.json` | Владелец | Все URL, к которым обращается пайплайн этой страны. **Ни один URL не зашивается в Python.** Здесь же `settings` (выбор модели, таймаут HTTP), `validation` (пределы), `electricity` (источник электроэнергии и его группы потребителей, `plans`, — названия и подсказки, без тарифов) и `manual_override` (значения, навязанные поверх того, что собрал пайплайн). |
| `<cc>/city_registry.json` | Пайплайн + владелец | Соответствие имени поставщика — ровно так, как оно напечатано на сайте-источнике — постоянному `city_code`. Новые поставщики дописываются автоматически; **существующий `city_code` никогда не переписывается**, потому что Android-приложение хранит его как выбор пользователя. Секция `suppliers` — водоканалы, секция `heat_suppliers` — теплоснабжающие предприятия (общая для горячей воды и отопления), секция `electricity_suppliers` — города с собственным тарифом на электроэнергию, секция `gas_suppliers` — газ, по оператору сети там, где доставка оплачивается отдельно. |

### `src/` — пайплайны

| Файл | Ответственность |
|---|---|
| `run_country.py` | Единственная точка входа. Решает, какие страны запускать, запускает их по очереди, изолирует сбой в пределах одной страны и в конце пересобирает индекс. |
| `build_index.py` | Собирает `tariffs_index.json` по одному разу на каждую цель публикации, читая реестр стран и те файлы тарифов, которые реально есть на диске. |
| `common/paths.py` | Единственное место, знающее раскладку файлов репозитория. Пайплайн никогда не собирает путь сам. |
| `common/countries.py` | Загрузка и проверка `config/countries.json`. |
| `common/jsonio.py` | Чтение предыдущего опубликованного файла, сборка корневого объекта (включая `country_names`), запись обоих выходных файлов и отказ писать файл с пустым блоком электроэнергии. |
| `common/ai_pipeline.py` | Сбор по городам: загрузка, извлечение, валидация, слияние, сохранение. Используется всеми странами, где города регулируются отдельно. |
| `common/fetching.py` | Загрузка одного источника и подготовка его для модели: HTML сплющивается в текст с сохранением таблиц, PDF и сканы передаются байтами. |
| `common/llm/` | Модель извлечения за единым интерфейсом; по модулю на провайдера, выбор — `settings.llm`. |
| `common/pdf.py` | Текстовый слой или картинки страниц PDF — для провайдера, который PDF не читает. |
| `common/prompts.py` | О чём спрашивают модель — по шаблону на каждый блок тарифов. |
| `common/electricity.py` | Электроэнергия страны или города: все тарифы для населения, которые печатает источник, публикуются как `plans`, а `base_rate` и `zones` берутся из группы по умолчанию. |
| `common/gas.py` | Газ города: все предложения источника как `plans`, доставка, нормы потребления без счётчика; проверки, через которые проходит газ любой страны. |
| `common/validation.py` | Можно ли публиковать извлечённый тариф. Отбраковывает город целиком, а не публикует сомнительное поле. |
| `common/overrides.py` | Семантика `manual_override`, общая для всех стран, чтобы она не разошлась. |
| `common/registry.py` | Постоянный реестр `city_code`: чтение, навязывание зарегистрированных кодов данным, добавление новых поставщиков, уведомление. |
| `common/telegram_notifier.py` | Единственное место, разговаривающее с Telegram. Деградирует мягко: без токена печатает сообщение в stdout и возвращает `False`, поэтому пайплайн никогда не падает из-за уведомлений. |
| `countries/<cc>/fetcher.py` | Пайплайн одной страны с единственной функцией `main(notifier)`. Украина собирает и валидирует; все остальные страны только называют себя и передают работу общему пайплайну сбора по городам. |

### Генерируемые файлы — руками не править

`docs/tariffs_<cc>.json` и `assets/tariffs_<cc>_default.json` побайтово одинаковы и
**перезаписываются при каждом запуске**, как и обе копии `tariffs_index.json`. Любая ручная правка
молча теряется на следующем запуске. Чтобы зафиксировать значение, используйте `manual_override` в
`config/<cc>/sources.json` (см. раздел README «Ручное переопределение тарифов»).

### `docs/` — документация *и* веб-корень

У этой папки двойная роль: в ней лежит документация, и она же публикуется GitHub Pages и объявлена
каталогом статики Cloudflare в `wrangler.toml`. Следствия:

* `docs/tariffs_<cc>.json` и `docs/tariffs_index.json` обязаны лежать в корне `docs/`, плоско. От
  этого зависят опубликованные адреса, и выпущенные сборки Android идут именно по ним. Копии по
  папкам стран, которые Pages тоже раздаёт (`<cc>/tariffs_<cc>.json`), добавляет workflow при
  публикации, в репозиторий они не коммитятся.
* Markdown-файлы внутри `docs/` тоже публикуются. Само по себе это безвредно, но не кладите сюда
  секреты и черновики.

### `dist/` — то, что публикуется не через Pages

Здесь лежит только копия индекса для Cloudflare: на R2 файлы разложены по папкам стран, поэтому в
индексе нужны другие значения `path`. Сами файлы стран выкладываются на R2 прямо из `docs/` — на
обоих хостах они одинаковы.

---

## 3. Поток данных между частями

```
config/countries.json ──────────────┬─> src/run_country.py ─> src/countries/<cc>/fetcher.py ─┬─> docs/tariffs_<cc>.json ──> GitHub Pages
config/<cc>/sources.json ───────────┤                                    │                   │                        └──> Cloudflare R2
config/<cc>/city_registry.json ─────┘                                    │                   └─> assets/tariffs_<cc>_default.json ──> сборка Android
        ▲                                                                │
        └── новые поставщики ────────────────────────────────────────────┤
                                                                         └─> src/common/telegram_notifier.py ──> Telegram (алерты, расхождения)

docs/tariffs_<cc>.json ──> src/build_index.py ──┬─> docs/tariffs_index.json           ──> GitHub Pages
                                                └─> dist/cloudflare/tariffs_index.json ──> Cloudflare R2
```

Опубликованные адреса:

| Что | Cloudflare R2 | GitHub Pages |
|---|---|---|
| Файл страны | `https://tarrifs.foleks.com/<cc>/tariffs_<cc>.json` | `https://alxpanther.github.io/communal_tarrifs/tariffs_<cc>.json` и `…/communal_tarrifs/<cc>/tariffs_<cc>.json` |
| Индекс стран | `https://tarrifs.foleks.com/tariffs_index.json` | `https://alxpanther.github.io/communal_tarrifs/tariffs_index.json` |

---

## 4. Переменные окружения

Локально читаются из `.env` (через `python-dotenv`), в CI — из секретов GitHub Actions.

| Переменная | Обязательна | Для чего |
|---|---|---|
| `GEMINI_API_KEY` | для Украины | Вызовы извлечения и Search Grounding |
| `GEMINI_MODEL` | нет | Жёстко фиксирует модель; перекрывает `settings` в `config/ua/sources.json` |
| `TELEGRAM_BOT_TOKEN` | нет | Уведомления; без него сообщения идут в stdout |
| `TELEGRAM_CHAT_ID` | нет | То же |
| `CLOUDFLARE_API_TOKEN` | только деплой | `wrangler r2 object put` |
| `CLOUDFLARE_ACCOUNT_ID` | только деплой | То же |

`.env` не попадает в git и не должен туда попасть.

---

## 5. Куда класть новое

| Что вы добавляете | Куда это класть |
|---|---|
| URL источника, имя модели, таймаут | `config/<cc>/sources.json` — никогда в Python |
| Принудительное значение тарифа | `config/<cc>/sources.json` → `manual_override` |
| Название страны, валюту, путь публикации | `config/countries.json` — никогда в Python |
| Новый пайплайн страны | См. [ADDING_A_COUNTRY.md](ADDING_A_COUNTRY.md): запись в `config/countries.json`, папка `config/<cc>/`, файл `src/countries/<cc>/fetcher.py` |
| Логику, нужную двум странам | `src/common/` — но не копию во втором fetcher'е |
| Новую страницу документации | `docs/en/` **и** `docs/ru/`, плюс строка в `docs/README.md` — см. [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md) |
| Одноразовый скрипт или отладочный дамп | Папка `tmp/` в корне репозитория, удаляется по завершении. Ничему временному не место в `src/`, `docs/` и корне репозитория |
| Изменение схемы выходного JSON | Ничего, пока владелец не согласился. Схема — контракт с Android-приложением; см. [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md), раздел «Замороженные контракты» |
