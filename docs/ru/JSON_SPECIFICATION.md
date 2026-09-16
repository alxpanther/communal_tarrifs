# Спецификация JSON формата тарифов ЖКХ (`tariffs_<код страны>.json`)

> **Язык:** русский — зеркало для чтения человеком.
> Каноническая версия: [../en/JSON_SPECIFICATION.md](../en/JSON_SPECIFICATION.md), именно её читают AI-агенты.
> Оба файла обязаны совпадать по смыслу; см. [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).


Данный документ содержит полную техническую спецификацию формата файла тарифов, детальное описание каждого поля, готовые Kotlin data-классы и бизнес-логику расчетов коммунальных услуг для использования в Android-приложении (учет счетчиков).

Файл — **один на страну**: `tariffs_ua.json`, `tariffs_am.json`, `tariffs_az.json`. Формат у всех один, страну называет поле `country`. Список стран, которые действительно опубликованы, лежит в отдельном файле — он описан в разделе 6 (`tariffs_index.json`).

---

## 📋 1. Общая структура JSON

Файл `tariffs_ua.json` состоит из семи основных блоков:
1. **Метаданные (Root)** — общая информация о файле, валюте, версии и времени обновления.
2. **`electricity`** — тариф на электроэнергию для всей страны: базовый тариф, счётчики на 1/2/3 зоны и все тарифы для населения, которые печатает источник (`plans`).
3. **`electricity_cities`** — тарифы на электроэнергию городов, у которых тариф отличается от общего по стране, в том же виде, по городам.
4. **`water`** — тарифы на централизованное водоснабжение и водоотведение по городам.
5. **`hot_water`** — тарифы на централизованное горячее водоснабжение (за м³).
6. **`heating`** — тарифы на централизованное отопление (за Гкал).
7. **`gas`** — природный газ по городам: цена газа, цена его доставки, все предложения, которые печатает источник, и нормы потребления для дома без счётчика.

> ⚠️ **Совместимость.** Блоки `hot_water` и `heating` были добавлены позже `electricity` и `water`; `electricity_cities`, `electricity.plans` и компоненты горячей воды добавлены в сентябре 2026 года, а новый корневой блок `gas` — в конце того же месяца. Ни одно существующее поле не переименовано, не удалено и не поменяло тип, поэтому старый код продолжает читать файл как раньше. Единственное требование — парсер должен игнорировать неизвестные ключи: `Json { ignoreUnknownKeys = true }` для `kotlinx.serialization` (Moshi и Gson делают это по умолчанию).

### Разное покрытие городов

Списки городов в трёх блоках **не совпадают** и совпадать не обязаны:

| Блок | Кто устанавливает тариф | Городов сейчас |
|---|---|---|
| `water` | НКРЕКП для всех водоканалов | ~50 |
| `hot_water` | НКРЕКП + местные власти | ~18 |
| `heating` | НКРЕКП + местные власти | ~28 |
| `gas` | поставщики (цена газа) и НКРЕКП (доставка) | ~33 |

Источник публикует только тарифы, установленные НКРЕКП, поэтому предприятия с «городским» тарифом попадают в JSON лишь если заведены отдельно (как КП «Київтеплоенерго»). Приложение обязано корректно переживать ситуацию «для выбранного города нет данных по отоплению».

### `source_url` может быть пустым

Поле пришло из тех времён, когда целый блок держала одна сводная страница, а у страны, которая
собирается по городам, такой страницы обычно нет: Молдова читает сайт каждого водоканала отдельно.
Поэтому оно заполняется только тогда, когда все города блока читаются с одной и той же страницы, а
иначе там пустая строка. Приложение обязано считать его справочным и никогда не полагаться на то,
что оно заполнено: пустое значение означает «источников несколько», а не «данных нет».

**`city_code` совпадает между блоками только там, где в городе один поставщик.** Для Києва, Львова, Вінниці, Харкова и большинства других это так (`kyiv`, `lviv`, `vinnytsia`, `kharkiv`). Но в Дніпрі, Миколаєві, Черкасах и Чернігові несколько теплопостачальних підприємств, и «чистого» кода там нет ни у кого — только `dnipro_teploenerho`, `dnipro_komenerhoservis` и т. п. Для связывания услуг между собой ориентируйтесь на `city_name`, а `city_code` используйте как стабильный ключ выбора внутри конкретного блока.

---

## 🔍 2. Описание полей (Field Description)

### 2.1. Корневой объект (Root Object)

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `version` | `String` | Версия схемы формата JSON. | `"1.0"` |
| `last_updated_at` | `String` | Штамп даты и времени последнего обновления файла в формате ISO 8601 (UTC). | `"2026-08-02T18:04:37.758583"` |
| `country` | `String` | Код страны по стандарту ISO 3166-1 alpha-2, верхний регистр. | `"UA"` |
| `country_names` | `Object` | Название страны для интерфейса: ключ — код языка приложения, значение — название на этом языке. Поле обязательное: по нему приложение показывает страну в списке при выборе адреса. Если ключа для текущего языка нет — берётся `ru`, если нет и его — показывается код из `country`. | `{ "ru": "Армения", "uk": "Вірменія" }` |
| `currency` | `String` | Код валюты тарифов по стандарту ISO 4217. | `"UAH"` |
| `electricity` | `Object` | Блок тарифов на электроэнергию (см. раздел 2.2). | `{ ... }` |
| `electricity_cities` | `Object` | Тарифы на электроэнергию отдельных городов (см. раздел 2.2a). Есть всегда; `cities` пуст, если везде действует общий тариф страны. | `{ ... }` |
| `water` | `Object` | Блок тарифов на водоснабжение и водоотведение (см. раздел 2.3). | `{ ... }` |
| `hot_water` | `Object` | Блок тарифов на горячую воду (см. раздел 2.4). | `{ ... }` |
| `heating` | `Object` | Блок тарифов на отопление (см. раздел 2.5). | `{ ... }` |

---

### 2.2. Блок `electricity` (Электроэнергия)

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `source_url` | `String` | URL-ссылка на веб-источник с официальными тарифами. | `"https://tariffa.com.ua/..."` |
| `base_rate` | `Double` | Базовый (одноставочный) тариф за 1 кВт⋅ч в UAH. | `4.32` |
| `unit` | `String` | Единица измерения потребления. | `"kWh"` |
| `effective_date` | `String` | Дата вступления тарифа в силу в формате `YYYY-MM-DD`. | `"2024-06-01"` |
| `update_date` | `String` | Дата последней проверки/актуализации тарифа (`YYYY-MM-DD`). | `"2026-08-02"` |
| `decree_info` | `String` | Название/номер нормативно-правового акта (постановление Кабмина/НКРЕКП). | `"постановлением КМУ № 632..."` |
| `zones` | `Object` | Объект с ценами для многозонных счетчиков. | `{ ... }` |
| `plans` | `Array<Object>` | Все тарифы для населения, которые печатает источник, как напечатано (раздел 2.2, `electricity.plans[]`). | `[ ... ]` |

#### Блок `electricity.zones`
* **`two_zone`** (`Object`): Двухзонный тариф (День / Ночь).
  * `description` (`String`): Описание ("Двухзонный тариф (День/Ночь)").
  * `day` (`Object`): Дневная зона.
    * `hours` (`String`): Интервал времени, как его печатает источник (например, `"07:00 - 23:00"`); пустая строка, если не напечатан.
    * `coefficient` (`Double`): `rate / base_rate`, округлённое до четырёх знаков. Справочное поле.
    * `rate` (`Double`): Цена 1 кВт⋅ч (например, `4.32`).
  * `night` (`Object`): Ночная зона, те же поля (`"23:00 - 07:00"`, `0.5`, `2.16`).

* **`three_zone`** (`Object`): Трехзонный тариф (Пик / Полупик / Ночь).
  * `description` (`String`): Описание ("Трехзонный тариф (Пик/Полупик/Ночь)").
  * `peak` (`Object`): Пиковая зона (`hours`: `"08:00 - 11:00, 20:00 - 22:00"`, `coefficient`: `1.5`, `rate`: `6.48`).
  * `half_peak` (`Object`): Полупиковая зона (`hours`: `"07:00 - 08:00, 11:00 - 20:00, 22:00 - 23:00"`, `coefficient`: `1.0`, `rate`: `4.32`).
  * `night` (`Object`): Ночная зона (`hours`: `"23:00 - 07:00"`, `coefficient`: `0.4`, `rate`: `1.73`).

> `base_rate` и `zones` повторяют цены группы по умолчанию (`is_default: true` в `plans`), первой ступени потребления, в сезоне дня, когда собран файл. Они нужны приложению, которое не читает `plans`. Если источник не печатает однотарифную цену — Армения печатает только день и ночь, — `base_rate` равен дневной цене. Для вида счётчика, который источник не тарифицирует вовсе, во всех зонах стоит `base_rate`, `coefficient` `1.0`, пустые `hours` и описание, оканчивающееся на «(не применяется, ставка одна)». Ни одна цена не вычисляется из коэффициента.

#### `electricity.plans[]`

Один элемент на группу потребителей, которую источник тарифицирует отдельно: квартира с газовой плитой, квартира с электроплитой, сельское население, малообеспеченная семья, электроотопление. Какие группы читать, задаёт конфиг; группы, которую источник в этот раз не напечатал, в файле нет.

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `plan_code` | `String` | Постоянный латинский ключ группы внутри страны. | `"standard"`, `"electric_stove"`, `"rural"` |
| `name` | `String` | Название группы по-русски для интерфейса. | `"Квартиры с электроплитами"` |
| `is_default` | `Boolean` | Группа, из которой взяты `base_rate` и `zones`. Ровно одна на блок. | `true` |
| `tier_basis` | `String?` | Как применяются ступени потребления: `"part"` — каждая часть месячного потребления оплачивается по цене своей ступени; `"whole"` — всё потребление месяца по цене ступени, в которую оно попало; `null` — ступеней нет или источник об этом не говорит. | `"part"` |
| `tiers_per_resident` | `Boolean?` | `true`, если границы ступеней установлены на одного проживающего, `false` — на квартиру, `null` — ступеней нет или источник не говорит. | `true` |
| `monthly_charge` | `Double?` | Фиксированная плата в месяц, не зависящая от потребления; `null`, если её нет. | `1.0` |
| `rates` | `Array<Object>` | Один элемент на каждую напечатанную цену. | `[ ... ]` |

Элемент `rates[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `meter` | `String` | `"single"`, `"two_zone"` или `"three_zone"`. | `"two_zone"` |
| `zone` | `String` | `"all"` для `single`; `"day"`/`"night"` для `two_zone`; `"peak"`/`"half_peak"`/`"night"` для `three_zone`. | `"night"` |
| `hours` | `String` | Часы зоны, как напечатаны; пусто, если не напечатаны. | `"23:00 - 07:00"` |
| `tier` | `Int?` | Номер ступени потребления, с 1; `null`, если цена не зависит от потребления. | `2` |
| `above_kwh` | `Double?` | Ступень действует для месячного потребления свыше этого числа; `null` — с нуля или не напечатано. | `200` |
| `up_to_kwh` | `Double?` | Ступень действует до этого числа включительно; `null` — без верхней границы или не напечатано. | `400` |
| `season_from` | `String?` | `MM-DD`: первый день сезона, повторяющегося каждый год; `null` — весь год. | `"10-01"` |
| `season_to` | `String?` | `MM-DD`: последний день сезона включительно. Сезон может переходить через Новый год. | `"04-30"` |
| `rate` | `Double` | Цена 1 кВт⋅ч с НДС. | `36.48` |

У ступени может быть `tier` без границ: Алматы печатает цену каждого уровня, но не его пределы. Тогда по файлу нельзя вычислить, в какой ступени семья, и приложению придётся спросить пользователя или считать по первой ступени.

### 2.2a. Блок `electricity_cities`

Если тариф города отличается от общего по стране — в России тарифы устанавливает каждый регион, — город перечислен здесь. Для города, которого в этом блоке нет, действует общий блок `electricity`.

| Поле | Тип | Описание |
|---|---|---|
| `source_url` | `String` | Единственная страница, с которой читаются все города, или пустая строка. |
| `update_date` | `String` | Дата последнего обновления блока, `YYYY-MM-DD`. |
| `cities` | `Array<Object>` | Один элемент на город. |

Элемент `electricity_cities.cities[]`: `city_code`, `city_name`, `supplier` и `unit`, как в `water.cities[]`, плюс `base_rate`, `effective_date`, `decree_info`, `zones` и `plans` ровно как в разделе 2.2. `city_code` — код города в стране, тот же, что в блоке воды, если у города один водоканал.

---

### 2.3. Блок `water` (Водоснабжение и Водоотведение)

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `source_url` | `String` | Ссылка на сводный веб-источник тарифов по водоканалам. Пустая строка, если блок собирается из разных страниц по городам, — см. примечание ниже. | `"https://index.minfin.com.ua/..."` |
| `update_date` | `String` | Дата проверки/обновления раздела (`YYYY-MM-DD`). | `"2026-08-02"` |
| `cities` | `Array<Object>` | Массив объектов тарифов водоканалов по населенным пунктам. | `[...]` |

#### Элемент массива `water.cities[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `city_code` | `String` | Уникальный латинский идентификатор города (slug, Primary Key для приложения). Стабилен между обновлениями: значения хранятся в постоянном реестре `config/ua/city_registry.json` и после первого назначения не меняются. | `"kyiv"`, `"lviv"` |
| `city_name` | `String` | Название города/региона на украинском языке для отображения в UI. | `"Київ"`, `"Львів"` |
| `supplier` | `String` | Наименование предприятия-поставщика (водоканала). | `"ПАТ АК \"Київводоканал\""` |
| `water_supply` | `Double` | Тариф за 1 м³ централизованного водоснабжения (холодная вода) в UAH. `0.0`, если поставщик не оказывает услугу. | `16.164` |
| `sewage` | `Double` | Тариф за 1 м³ водоотведения (канализация) в UAH. `0.0`, если поставщик не оказывает услугу. | `14.22` |
| `total_rate` | `Double` | Суммарный тариф (водоснабжение + водоотведение) за 1 м³ в UAH. | `30.384` |
| `unit` | `String` | Единица измерения объема воды. | `"m3"` |
| `effective_date` | `String` | Дата вступления тарифа водоканала в силу (`YYYY-MM-DD`). | `"2022-01-01"` |
| `decree_info` | `String` | Реквизиты действующего тарифа. Источник не публикует номера постановлений НКРЕКП по каждому водоканалу, поэтому поле формируется из периода действия. | `"Тариф НКРЕКП, чинний з 01.01.2022"` |

---

### 2.4. Блок `hot_water` (Горячая вода)

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `source_url` | `String` | Ссылка на сводный веб-источник тарифов. | `"https://index.minfin.com.ua/ua/tariff/hotwater/"` |
| `update_date` | `String` | Дата проверки/обновления раздела (`YYYY-MM-DD`). | `"2026-08-11"` |
| `cities` | `Array<Object>` | Массив тарифов теплоснабжающих предприятий по населённым пунктам. | `[...]` |

#### Элемент массива `hot_water.cities[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `city_code` | `String` | Уникальный латинский идентификатор (Primary Key). Стабилен между обновлениями, хранится в `config/ua/city_registry.json` (секция `heat_suppliers`). | `"kyiv"` |
| `city_name` | `String` | Название города на украинском для UI. | `"Київ"` |
| `supplier` | `String` | Наименование теплоснабжающего предприятия. | `"КП \"КИЇВТЕПЛОЕНЕРГО\""` |
| `rate` | `Double` | Тариф за 1 м³ горячей воды в UAH с НДС. | `97.89` |
| `component_water` | `Double?` | Только у двухкомпонентного тарифа: компонент на теплоноситель, за м³. Иначе поля нет. | `52.63` |
| `component_energy` | `Double?` | Только у двухкомпонентного тарифа: компонент на тепловую энергию, за Гкал. | `2706.23` |
| `heat_norm` | `Double?` | Только у двухкомпонентного тарифа: норматив, по которому свёрнут `rate`, Гкал на м³. | `0.05131` |
| `heat_norms` | `Array<Object>?` | Нормативы региона для всех типов домов, если источник их печатает. Иначе поля нет. | `[ ... ]` |
| `unit` | `String` | Единица измерения объёма. | `"m3"` |
| `effective_date` | `String` | Дата вступления тарифа в силу (`YYYY-MM-DD`). | `"2022-10-01"` |
| `decree_info` | `String` | Реквизиты действующего тарифа. | `"Розпорядження КМВА № 673 від 30.09.2022..."` |

Элемент `heat_norms[]`: `system` (`String`: `"open"`, `"closed"` или `"decentralized"`), `insulated_risers` (`Boolean?`), `towel_rails` (`Boolean?`), `value` (`Double`, Гкал на м³). `null` у признака означает, что норматив от него не зависит.

У двухкомпонентного тарифа `rate = component_water + component_energy × heat_norm`, округлённое до копеек; `heat_norm` — норматив самого распространённого типа дома, указанного в конфиге.

> 💡 В `rate` лежит тариф, который **реально платит население**. Для большинства предприятий он заморожен мораторием на весь период военного положения и шесть месяцев после него, поэтому `effective_date` часто указывает на 2021–2022 год — это не признак устаревших данных. Економічно обґрунтовані тарифи, которые публикуются рядом на сайтах компаний, в JSON не попадают.

---

### 2.5. Блок `heating` (Централизованное отопление)

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `source_url` | `String` | Ссылка на сводный веб-источник тарифов. | `"https://index.minfin.com.ua/ua/tariff/heating/"` |
| `update_date` | `String` | Дата проверки/обновления раздела (`YYYY-MM-DD`). | `"2026-08-11"` |
| `cities` | `Array<Object>` | Массив тарифов теплоснабжающих предприятий. | `[...]` |

#### Элемент массива `heating.cities[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `city_code` | `String` | Уникальный латинский идентификатор (Primary Key). | `"kyiv"` |
| `city_name` | `String` | Название города на украинском для UI. | `"Київ"` |
| `supplier` | `String` | Наименование теплоснабжающего предприятия. | `"КП \"КИЇВТЕПЛОЕНЕРГО\""` |
| `tariff_type` | `String` | Вид тарифа: `"one_rate"` (одноставковий) или `"two_rate"` (двоставковий). | `"one_rate"` |
| `rate_gcal` | `Double` | Тариф за 1 Гкал в UAH с НДС. Для двухставкового — умовно-змінна частина. | `1654.41` |
| `rate_gcal_hour` | `Double` | Умовно-постійна частина двухставкового тарифа, UAH за Гкал/год. `0.0` при `tariff_type = "one_rate"`. | `0.0` |
| `unit` | `String` | Единица измерения тепловой энергии. | `"Gcal"` |
| `effective_date` | `String` | Дата вступления тарифа в силу (`YYYY-MM-DD`). | `"2022-10-01"` |
| `decree_info` | `String` | Реквизиты действующего тарифа. | `"Розпорядження КМВА № 673 від 30.09.2022..."` |

> 💡 Умовно-постійна частина начисляется не на потреблённые Гкал, а на подключённую тепловую нагрузку дома (Гкал/год), которую жилец не знает. Поле отдаётся справочно; приложение вправе его не показывать и считать только по `rate_gcal`.

---

### 2.6. Блок `gas` (Природный газ)

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `source_url` | `String` | Единственная страница, с которой читается блок, или пустая строка. | `"https://index.minfin.com.ua/ua/tariff/gas/"` |
| `update_date` | `String` | Дата последнего обновления блока (`YYYY-MM-DD`). | `"2026-09-16"` |
| `cities` | `Array<Object>` | Одна запись на город — на газораспределительную сеть, если в городе их две. | `[...]` |

Блок есть в каждом файле; в стране, где газ ещё не собирается, `cities` пуст.

#### Элемент массива `gas.cities[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `city_code` | `String` | Постоянный ключ записи внутри блока, из раздела реестра `gas_suppliers`. | `"kyiv"`, `"ternopil_hazmerezhi"` |
| `city_name` | `String` | Название города для UI. | `"Київ"` |
| `supplier` | `String` | Поставщик плана по умолчанию. | `"ТОВ ГК \"Нафтогаз України\""` |
| `unit` | `String` | Всегда `"m3"`: все цены блока — за кубометр, в чём бы их ни печатал источник. | `"m3"` |
| `rate` | `Double` | Цена 1 м³ газа в плане по умолчанию: первая ступень, текущий сезон, с НДС. | `7.96` |
| `distributor` | `String` | Оператор газораспределительной сети, если доставка оплачивается отдельно от газа; иначе пусто. | `"ПАТ \"Київгаз\""` |
| `distribution_rate` | `Double` | Цена доставки за м³ с НДС; `0.0`, если доставка входит в цену газа. | `0.384` |
| `effective_date` | `String` | Дата, с которой действует текущая цена (`YYYY-MM-DD`). | `"2026-09-01"` |
| `decree_info` | `String` | Происхождение цен. | `"Ціни постачальників і тарифи операторів ГРМ станом на 01.09.2026"` |
| `plans` | `Array<Object>` | Все предложения, которые печатает источник. Ровно у одного `is_default`. | `[ ... ]` |
| `norms` | `Array<Object>` | Месячные нормы потребления для дома без счётчика; пусто, если источник их не печатает. | `[ ... ]` |
| `norms_decree` | `String` | Акт, которым установлены нормы; пусто, если норм нет. | `"Постанова КМ України № 143 від 27.02.2019"` |

Элемент `plans[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `plan_code` | `String` | Постоянный латинский ключ предложения внутри города. | `"naftohaz_ukrainy_annual"` |
| `name` | `String` | Название предложения на русском, для интерфейса. | `"Нафтогаз України, годовой тариф"` |
| `is_default` | `Boolean` | Предложение, из которого берутся `supplier` и `rate`. | `true` |
| `supplier` | `String` | Кто продаёт газ по этому предложению. | `"ТОВ \"Асканія Енерджи\""` |
| `contract` | `String?` | `"annual"` — цена зафиксирована на год, `"monthly"` — меняется каждый месяц, `null` — источник так не делит. | `"annual"` |
| `usage` | `String?` | `"cooking"` или `"heating"`, если цена зависит от назначения газа; иначе `null`. | `null` |
| `metered` | `Boolean?` | `true` — цена для дома со счётчиком, `false` — без, `null` — одинаково для обоих. | `null` |
| `monthly_charge` | `Double?` | Фиксированная плата в месяц, не зависящая от расхода; `null`, если её нет. | `null` |
| `rates` | `Array<Object>` | По элементу на каждую напечатанную цену. | `[ ... ]` |

Элемент `rates[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `tier` | `Int?` | Номер ступени потребления, с 1; `null`, если цена не зависит от расхода. | `1` |
| `above_m3` | `Double?` | Ступень действует для расхода свыше этого значения; `null` — с нуля или не напечатано. | `1200` |
| `up_to_m3` | `Double?` | Ступень действует до этого значения включительно; `null` — без верхней границы или не напечатано. | `2500` |
| `tier_period` | `String?` | `"month"` или `"year"` — за какой срок считаются границы ступеней; `null` без ступеней. | `"year"` |
| `season_from` | `String?` | `MM-DD`: первый день сезона, повторяющегося каждый год; `null` — весь год. | `"10-01"` |
| `season_to` | `String?` | `MM-DD`: последний день сезона включительно. | `"04-30"` |
| `rate` | `Double` | Цена за м³ с НДС. | `9.95` |

Элемент `norms[]`:

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `usage` | `String` | `"stove_with_hot_water"` — газовая плита при централизованном ГВС; `"stove_without_hot_water"` — плита без централизованного ГВС и без водонагревателя; `"stove_and_water_heater"` — плита и газовый водонагреватель; `"water_heater"` — только водонагреватель; `"heating"` — индивидуальное отопление. | `"stove_with_hot_water"` |
| `basis` | `String` | `"per_person"` — на жильца, `"per_m2"` — на м² отапливаемой площади. | `"per_person"` |
| `value` | `Double` | м³ в месяц. | `3.28` |
| `heating_season_only` | `Boolean` | Норма действует только в отопительный период. | `false` |

---

## 📱 3. Готовые Kotlin Data Classes (`kotlinx.serialization`)

Для парсинга файла тарифов в Android-приложении вы можете использовать следующие Data Classes.

Парсер обязательно создавайте с `ignoreUnknownKeys`, иначе следующее расширение формата уронит приложение:

```kotlin
val json = Json { ignoreUnknownKeys = true }
```

`hotWater` и `heating` объявлены nullable со значением по умолчанию, чтобы приложение могло прочитать и старый закэшированный файл, в котором этих блоков ещё нет.

```kotlin
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class TariffResponse(
    @SerialName("version") val version: String,
    @SerialName("last_updated_at") val lastUpdatedAt: String,
    @SerialName("country") val country: String,
    @SerialName("country_names") val countryNames: Map<String, String> = emptyMap(),
    @SerialName("currency") val currency: String,
    @SerialName("electricity") val electricity: ElectricityTariff,
    @SerialName("electricity_cities") val electricityCities: ElectricityCities? = null,
    @SerialName("water") val water: WaterTariff,
    @SerialName("hot_water") val hotWater: HotWaterTariff? = null,
    @SerialName("heating") val heating: HeatingTariff? = null,
    @SerialName("gas") val gas: GasTariff? = null
)

@Serializable
data class ElectricityTariff(
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("base_rate") val baseRate: Double,
    @SerialName("unit") val unit: String,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("update_date") val updateDate: String,
    @SerialName("decree_info") val decreeInfo: String,
    @SerialName("zones") val zones: ElectricityZones,
    @SerialName("plans") val plans: List<ElectricityPlan> = emptyList()
)

@Serializable
data class ElectricityPlan(
    @SerialName("plan_code") val planCode: String,
    @SerialName("name") val name: String,
    @SerialName("is_default") val isDefault: Boolean = false,
    @SerialName("tier_basis") val tierBasis: String? = null,
    @SerialName("tiers_per_resident") val tiersPerResident: Boolean? = null,
    @SerialName("monthly_charge") val monthlyCharge: Double? = null,
    @SerialName("rates") val rates: List<ElectricityRate> = emptyList()
)

@Serializable
data class ElectricityRate(
    @SerialName("meter") val meter: String,
    @SerialName("zone") val zone: String,
    @SerialName("hours") val hours: String = "",
    @SerialName("tier") val tier: Int? = null,
    @SerialName("above_kwh") val aboveKwh: Double? = null,
    @SerialName("up_to_kwh") val upToKwh: Double? = null,
    @SerialName("season_from") val seasonFrom: String? = null,
    @SerialName("season_to") val seasonTo: String? = null,
    @SerialName("rate") val rate: Double
)

@Serializable
data class ElectricityCities(
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("update_date") val updateDate: String? = null,
    @SerialName("cities") val cities: List<CityElectricityTariff> = emptyList()
)

@Serializable
data class CityElectricityTariff(
    @SerialName("city_code") val cityCode: String,
    @SerialName("city_name") val cityName: String,
    @SerialName("supplier") val supplier: String,
    @SerialName("unit") val unit: String,
    @SerialName("base_rate") val baseRate: Double,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("decree_info") val decreeInfo: String,
    @SerialName("zones") val zones: ElectricityZones,
    @SerialName("plans") val plans: List<ElectricityPlan> = emptyList()
)

@Serializable
data class ElectricityZones(
    @SerialName("two_zone") val twoZone: TwoZoneTariff,
    @SerialName("three_zone") val threeZone: ThreeZoneTariff
)

@Serializable
data class TwoZoneTariff(
    @SerialName("description") val description: String,
    @SerialName("day") val day: ZoneDetail,
    @SerialName("night") val night: ZoneDetail
)

@Serializable
data class ThreeZoneTariff(
    @SerialName("description") val description: String,
    @SerialName("peak") val peak: ZoneDetail,
    @SerialName("half_peak") val halfPeak: ZoneDetail,
    @SerialName("night") val night: ZoneDetail
)

@Serializable
data class ZoneDetail(
    @SerialName("hours") val hours: String,
    @SerialName("coefficient") val coefficient: Double,
    @SerialName("rate") val rate: Double
)

@Serializable
data class WaterTariff(
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("update_date") val updateDate: String,
    @SerialName("cities") val cities: List<CityWaterTariff>
)

@Serializable
data class CityWaterTariff(
    @SerialName("city_code") val cityCode: String,
    @SerialName("city_name") val cityName: String,
    @SerialName("supplier") val supplier: String,
    @SerialName("water_supply") val waterSupply: Double,
    @SerialName("sewage") val sewage: Double,
    @SerialName("total_rate") val totalRate: Double,
    @SerialName("unit") val unit: String,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("decree_info") val decreeInfo: String
)

@Serializable
data class HotWaterTariff(
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("update_date") val updateDate: String,
    @SerialName("cities") val cities: List<CityHotWaterTariff> = emptyList()
)

@Serializable
data class CityHotWaterTariff(
    @SerialName("city_code") val cityCode: String,
    @SerialName("city_name") val cityName: String,
    @SerialName("supplier") val supplier: String,
    @SerialName("rate") val rate: Double,
    @SerialName("component_water") val componentWater: Double? = null,
    @SerialName("component_energy") val componentEnergy: Double? = null,
    @SerialName("heat_norm") val heatNorm: Double? = null,
    @SerialName("heat_norms") val heatNorms: List<HeatNorm> = emptyList(),
    @SerialName("unit") val unit: String,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("decree_info") val decreeInfo: String
)

@Serializable
data class HeatNorm(
    @SerialName("system") val system: String,
    @SerialName("insulated_risers") val insulatedRisers: Boolean? = null,
    @SerialName("towel_rails") val towelRails: Boolean? = null,
    @SerialName("value") val value: Double
)

@Serializable
data class HeatingTariff(
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("update_date") val updateDate: String,
    @SerialName("cities") val cities: List<CityHeatingTariff> = emptyList()
)

@Serializable
data class CityHeatingTariff(
    @SerialName("city_code") val cityCode: String,
    @SerialName("city_name") val cityName: String,
    @SerialName("supplier") val supplier: String,
    @SerialName("tariff_type") val tariffType: String,
    @SerialName("rate_gcal") val rateGcal: Double,
    @SerialName("rate_gcal_hour") val rateGcalHour: Double = 0.0,
    @SerialName("unit") val unit: String,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("decree_info") val decreeInfo: String
)

@Serializable
data class GasTariff(
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("update_date") val updateDate: String,
    @SerialName("cities") val cities: List<CityGasTariff> = emptyList()
)

@Serializable
data class CityGasTariff(
    @SerialName("city_code") val cityCode: String,
    @SerialName("city_name") val cityName: String,
    @SerialName("supplier") val supplier: String,
    @SerialName("unit") val unit: String,
    @SerialName("rate") val rate: Double,
    @SerialName("distributor") val distributor: String = "",
    @SerialName("distribution_rate") val distributionRate: Double = 0.0,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("decree_info") val decreeInfo: String,
    @SerialName("plans") val plans: List<GasPlan> = emptyList(),
    @SerialName("norms") val norms: List<GasNorm> = emptyList(),
    @SerialName("norms_decree") val normsDecree: String = ""
)

@Serializable
data class GasPlan(
    @SerialName("plan_code") val planCode: String,
    @SerialName("name") val name: String,
    @SerialName("is_default") val isDefault: Boolean,
    @SerialName("supplier") val supplier: String,
    @SerialName("contract") val contract: String? = null,
    @SerialName("usage") val usage: String? = null,
    @SerialName("metered") val metered: Boolean? = null,
    @SerialName("monthly_charge") val monthlyCharge: Double? = null,
    @SerialName("rates") val rates: List<GasRate> = emptyList()
)

@Serializable
data class GasRate(
    @SerialName("tier") val tier: Int? = null,
    @SerialName("above_m3") val aboveM3: Double? = null,
    @SerialName("up_to_m3") val upToM3: Double? = null,
    @SerialName("tier_period") val tierPeriod: String? = null,
    @SerialName("season_from") val seasonFrom: String? = null,
    @SerialName("season_to") val seasonTo: String? = null,
    @SerialName("rate") val rate: Double
)

@Serializable
data class GasNorm(
    @SerialName("usage") val usage: String,
    @SerialName("basis") val basis: String,
    @SerialName("value") val value: Double,
    @SerialName("heating_season_only") val heatingSeasonOnly: Boolean
)
```

---

## 🧮 4. Логика расчетов коммунальных услуг для Android

### 4.1. Расчет стоимости Электроэнергии

Тип счетчика выбирается пользователем в настройках прибора учета (Однозонный, Двухзонный, Трехзонный).

1. **Однозонный счетчик:**
   $$\text{Сумма грн} = \Delta \text{кВт⋅ч} \times \text{electricity.base\_rate}$$

2. **Двухзонный счетчик (День / Ночь):**
   $$\text{Сумма грн} = (\Delta \text{кВт⋅ч}_{\text{день}} \times \text{electricity.zones.two\_zone.day.rate}) + (\Delta \text{кВт⋅ч}_{\text{ночь}} \times \text{electricity.zones.two\_zone.night.rate})$$

3. **Трехзонный счетчик (Пик / Полупик / Ночь):**
   $$\text{Сумма грн} = (\Delta \text{кВт⋅ч}_{\text{пик}} \times \text{rate}_{\text{peak}}) + (\Delta \text{кВт⋅ч}_{\text{полупик}} \times \text{rate}_{\text{half\_peak}}) + (\Delta \text{кВт⋅ч}_{\text{ночь}} \times \text{rate}_{\text{night}})$$

Три формулы выше используют старые поля и точны только для семьи из группы по умолчанию, чьё потребление не выходит за первую ступень. С `plans`:

1. Взять тариф города пользователя из `electricity_cities`, а если города там нет — `electricity`; затем группу, выбранную пользователем (`plan_code`), или ту, у которой `is_default`.
2. Оставить строки `meter` пользователя, сезон которых покрывает расчётный месяц (`season_from` равен `null` или месяц лежит между `season_from` и `season_to`, с переходом через Новый год, если `season_from` > `season_to`).
3. Без ступеней (`tier` равен `null`) у каждой зоны одна строка: считать по формулам выше.
4. Со ступенями, по каждой зоне: при `tier_basis` = `"part"` потребление до первой `up_to_kwh` оплачивается по цене первой ступени, следующая часть — по второй и так далее; при `"whole"` всё потребление оплачивается по цене ступени, в которую попало месячное потребление. Для многозонного счётчика файл не говорит, определяется ли ступень по каждой зоне или по сумме всех зон за месяц; пока источник этого не скажет, брать сумму. При `tiers_per_resident` = `true` границы умножаются на число проживающих. Если `tier_basis` равен `null` или границы равны `null`, по файлу разделить потребление нельзя — спросить пользователя или считать по первой ступени.
5. Если задан `monthly_charge`, прибавить его один раз за месяц.

---

### 4.2. Расчет стоимости Водоснабжения и Водоотведения

Пользователь выбирает свой город из списка `water.cities` (сохраняется `city_code`).

1. **Если у пользователя общее подключение (Вода + Канализация):**
   $$\text{Сумма грн} = \Delta \text{м}^3 \times \text{city.total\_rate}$$

2. **Если у пользователя только Водоснабжение (без канализации / частный сектор):**
   $$\text{Сумма грн} = \Delta \text{м}^3 \times \text{city.water\_supply}$$

3. **Если у пользователя только Водоотведение (своя скважина + центральная канализация):**
   $$\text{Сумма грн} = \Delta \text{м}^3 \times \text{city.sewage}$$

---

### 4.3. Расчет стоимости Горячей воды

Пользователь выбирает поставщика из `hot_water.cities` (сохраняется `city_code`). Показания снимаются со счётчика горячей воды в м³.

$$\text{Сумма грн} = \Delta \text{м}^3 \times \text{city.rate}$$

Для двухкомпонентного тарифа (задан `component_energy`), если пользователь указал в приложении свой тип дома, берётся норматив этого дома из `heat_norms`, а не свёрнутый в `rate`:

$$\text{цена за м}^3 = \text{component\_water} + \text{component\_energy} \times \text{норматив}$$

Без `heat_norms` или для дома, которого в нём нет, считать по `rate`.

---

### 4.4. Расчет стоимости Отопления

Пользователь выбирает поставщика из `heating.cities`. Показания снимаются с домового или квартирного теплосчётчика в Гкал.

1. **Одноставковый тариф (`tariff_type = "one_rate"`):**
   $$\text{Сумма грн} = \Delta \text{Гкал} \times \text{city.rate\_gcal}$$

2. **Двухставковый тариф (`tariff_type = "two_rate"`):** переменная часть считается так же, а постоянная зависит от подключённой тепловой нагрузки дома ($P$, Гкал/год), поделённой между квартирами. Жилец этой величины обычно не знает, поэтому рекомендуется считать только переменную часть, а `rate_gcal_hour` показывать справочно:
   $$\text{Сумма грн} = \Delta \text{Гкал} \times \text{city.rate\_gcal} + \frac{P \times \text{city.rate\_gcal\_hour}}{12}$$

> ⚠️ Перед расчётом проверьте, что выбранный пользователем `city_code` вообще присутствует в блоке — покрытие городов у `water`, `hot_water` и `heating` разное (см. раздел 1).

---

### 4.5. Расчет стоимости Газа

Пользователь выбирает город из `gas.cities`, а если предложений несколько — план (`plan_code`, по умолчанию тот, у которого `is_default`). Цена 1 м³ — цена плана плюс доставка:

$$\text{цена за м}^3 = \text{цена плана} + \text{city.distribution\_rate}$$

1. **Со счётчиком газа:**
   $$\text{Сумма грн} = \Delta \text{м}^3 \times \text{цена за м}^3$$
2. **Без счётчика:** пользователь указывает, на что расходуется газ (`norms[].usage`), и число жильцов, либо отапливаемую площадь для `per_m2`:
   $$\text{Сумма грн} = \text{norm.value} \times \text{жильцы (или м}^2\text{)} \times \text{цена за м}^3$$
   Норма с `heating_season_only` начисляется только в месяцы отопительного периода.

Цена плана выбирается так же, как цена электроэнергии (раздел 4.1, шаги 2–5): строки, сезон которых покрывает месяц; при ступенях — ступень, до которой дошёл расход, считая за месяц или за год по `tier_period`; плюс `monthly_charge`, если он задан.

В Украине доставка оплачивается по годовой заказанной мощности, которая для дома равна среднему месячному расходу (со счётчиком) или норме (без счётчика); `distribution_rate` — уже годовой тариф, поэтому его произведение на кубометры месяца и даёт сумму платёжки. Больше пользователю ничего вводить не нужно.

---

## 🔄 5. Стратегия обновления и оффлайн-режима

Файл каталога — один на страну, и всё, что ниже, происходит для каждой страны отдельно: свой файл
поставки, свой кэш, свои отметки о проверке.

1. **Первый запуск (Offline Fallback):**
   * Файл поставки лежит в приложении как `assets/tariffs/tariffs_<код>_default.json` (код страны в
     нижнем регистре: `tariffs_ua_default.json`, `tariffs_am_default.json`).
   * Приложение находит эти файлы во время работы, перебирая манифест ассетов, — список стран нигде
     в его коде не перечислен. Достаточно положить файл в папку.
   * При отсутствии сети интернет приложение работает на них.

2. **Фоновая синхронизация (Remote Update):**
   * Хосты пробуются по очереди, раскладка файлов у каждого своя:
     * **Cloudflare CDN / R2:** `https://tarrifs.foleks.com/<код>/tariffs_<код>.json`
     * **GitHub Pages:** `https://alxpanther.github.io/communal_tarrifs/tariffs_<код>.json`, и тот же
       файл по адресу `…/communal_tarrifs/<код>/tariffs_<код>.json`
   * Поле `path` в индексе (раздел 6) отменяет раскладку того хоста, который опубликовал этот
     индекс, и никакого другого.
   * Приложение сравнивает `last_updated_at` полученного файла с тем, что в кэше, и при более свежем
     штампе переписывает кэш.
   * Неполный файл отвергается: если издатель потерял блок электроэнергии или больше половины
     записей блока, кэш остаётся прежним.

---

## 🌍 6. Индекс стран (`tariffs_index.json`)

Список того, для каких стран тарифы вообще опубликованы. Нужен для одной вещи: чтобы страна,
добавленная после выхода версии приложения, появилась в выборе адреса у пользователя, который ничего
не обновлял.

Публикуется в корне **каждого** хоста:

* `https://tarrifs.foleks.com/tariffs_index.json`
* `https://alxpanther.github.io/communal_tarrifs/tariffs_index.json`

### 6.1. Пример

```json
{
  "version": "1.0",
  "generated_at": "2026-08-28T10:15:00",
  "countries": [
    {
      "country": "UA",
      "country_names": { "ru": "Украина", "uk": "Україна" },
      "currency": "UAH",
      "last_updated_at": "2026-08-11T13:56:38.856897",
      "path": "tariffs_ua.json",
      "enabled": true,
      "min_app_version": ""
    }
  ]
}
```

### 6.2. Поля

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `version` | `String` | да | Версия формата индекса. Приложение читает `1.x`; индекс со старшей мажорной версией игнорируется целиком, и список стран остаётся прежним. |
| `generated_at` | `String` | нет | Когда индекс собран, ISO 8601. Для диагностики. |
| `countries` | `Array<Object>` | да | Список стран. Порядок значения не имеет — приложение сортирует по названию. |
| `countries[].country` | `String` | да | ISO 3166-1 alpha-2. Ключ записи; запись без кода отбрасывается. |
| `countries[].country_names` | `Object` | да | То же, что в файле каталога. Нужно, чтобы показать страну в списке **до** того, как её файл скачан. |
| `countries[].currency` | `String` | нет | ISO 4217. Справочно; валюту приложения не меняет. |
| `countries[].last_updated_at` | `String` | да | Штамп из собственного файла тарифов этой страны. |
| `countries[].path` | `String` | нет | Путь к файлу тарифов **относительно корня публикации**. Без него действует стандартная раскладка хоста (раздел 5). |
| `countries[].enabled` | `Bool` | нет | По умолчанию `true`. `false` — страну не показывать, файл при этом можно не удалять. |
| `countries[].min_app_version` | `String` | нет | Минимальная версия приложения (`major.minor.patch`), ниже которой страна не показывается. Пусто — ограничения нет. Именно версия, а не номер сборки: `--split-per-abi` даёт одному релизу разные номера сборки на разных архитектурах. |

### 6.3. Почему у каждого хоста своя копия

Раскладки разные — плоская на GitHub Pages, по папкам стран на Cloudflare, — а значит, разные и
значения `path`. Генератор пишет обе копии (`docs/tariffs_index.json` для Pages и
`dist/cloudflare/tariffs_index.json` для R2) из одного реестра стран,
[`config/countries.json`](../../config/countries.json).

Приложение читает каждый хост через его собственный индекс: сначала индекс, затем файл по `path`,
который тот называет; хост, чей индекс не пришёл или не называет страну, пропускается целиком.
Сборки по 1.8.0 включительно поступали иначе — хранили тот индекс, который прочитали первым, обычно с
Cloudflare, и подставляли его `path` для каждого хоста. Поэтому на Pages каждый файл страны лежит
ещё и по пути Cloudflare: для этих сборок без такой копии зеркало отвечает 404 ровно тогда, когда
CDN недоступен.

### 6.4. Правила, которые соблюдает приложение

* **`path` принимается только относительный.** Абсолютный адрес (`http://…`, `//…`), путь от корня
  (`/…`), любой путь с `..` или с обратными слэшами игнорируется, и действует стандартная раскладка.
  Индекс приходит из сети, а по указанному в нём адресу приложение ходит само — уводить его на чужой
  хост нельзя.
* **Недоступный, битый или пустой индекс ничего не убирает.** Остаётся предыдущая сохранённая копия,
  а страны из файлов поставки есть всегда.
* **Страна, уже выбранная у адреса, из списка не исчезает** — даже если пропала из индекса, с одним
  исключением, о нём ниже.
* **Страну можно вывести из публикации, и тогда её нет в индексе вовсе.** `enabled: false` лишь
  скрывает страну, а её файл остаётся опубликованным; вывод же удаляет файл со всех хостов и не
  оставляет о стране записи в индексе. Это значит, что обновлять её тарифы больше некому, поэтому
  приложение обязано перестать предлагать страну и сообщить пользователю, который её выбрал, что
  тарифов для неё больше не существует, — а не считать по закэшированному файлу неограниченно
  долго. Туркменистан — первый такой случай: его коммунальные тарифы нигде не публикуются.
* Индекс запрашивается при старте приложения не чаще раза в сутки и перед каждой плановой проверкой
  тарифов.

---

## ➕ 7. Как добавить страну

1. Сгенерировать `tariffs_<код>.json` по формату из разделов 1–4, обязательно с `country`,
   `currency` и `country_names`.
2. Выложить его на оба хоста по стандартной раскладке (раздел 5).
3. Добавить запись о стране в `tariffs_index.json` на обоих хостах.
4. При желании положить тот же файл в `assets/tariffs/tariffs_<код>_default.json` следующей версии
   приложения — тогда страна будет работать и без сети, с первого запуска.

Шаг 4 необязателен: страна из индекса появится в выборе адреса и без него, а её тарифы приложение
скачает в момент выбора страны.

Со стороны генератора та же задача описана в [ADDING_A_COUNTRY.md](ADDING_A_COUNTRY.md).
