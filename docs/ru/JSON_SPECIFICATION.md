# Спецификация JSON формата тарифов ЖКХ (`tariffs_<код страны>.json`)

> **Язык:** русский — зеркало для чтения человеком.
> Каноническая версия: [../en/JSON_SPECIFICATION.md](../en/JSON_SPECIFICATION.md), именно её читают AI-агенты.
> Оба файла обязаны совпадать по смыслу; см. [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).


Данный документ содержит полную техническую спецификацию формата файла тарифов, детальное описание каждого поля, готовые Kotlin data-классы и бизнес-логику расчетов коммунальных услуг для использования в Android-приложении (учет счетчиков).

Файл — **один на страну**: `tariffs_ua.json`, `tariffs_am.json`, `tariffs_az.json`. Формат у всех один, страну называет поле `country`. Список стран, которые действительно опубликованы, лежит в отдельном файле — он описан в разделе 6 (`tariffs_index.json`).

---

## 📋 1. Общая структура JSON

Файл `tariffs_ua.json` состоит из пяти основных блоков:
1. **Метаданные (Root)** — общая информация о файле, валюте, версии и времени обновления.
2. **`electricity`** — тарифы на электроэнергию (базовый тариф и зонные тарифы: 1/2/3 зоны).
3. **`water`** — тарифы на централизованное водоснабжение и водоотведение по городам Украины.
4. **`hot_water`** — тарифы на централизованное постачання гарячої води (грн/м³).
5. **`heating`** — тарифы на централизованное опалення (грн/Гкал).

> ⚠️ **Совместимость.** Блоки `hot_water` и `heating` были добавлены позже `electricity` и `water`. Формат первых двух при этом не менялся, поэтому старый код продолжает читать их как раньше. Единственное требование — парсер должен игнорировать неизвестные корневые ключи: `Json { ignoreUnknownKeys = true }` для `kotlinx.serialization` (Moshi и Gson делают это по умолчанию).

### Разное покрытие городов

Списки городов в трёх блоках **не совпадают** и совпадать не обязаны:

| Блок | Кто устанавливает тариф | Городов сейчас |
|---|---|---|
| `water` | НКРЕКП для всех водоканалов | ~50 |
| `hot_water` | НКРЕКП + местные власти | ~18 |
| `heating` | НКРЕКП + местные власти | ~28 |

Источник публикует только тарифы, установленные НКРЕКП, поэтому предприятия с «городским» тарифом попадают в JSON лишь если заведены отдельно (как КП «Київтеплоенерго»). Приложение обязано корректно переживать ситуацию «для выбранного города нет данных по отоплению».

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
| `zones` | `Object` | Объект с коэффициентами для многозонных счетчиков. | `{ ... }` |

#### Блок `electricity.zones`
* **`two_zone`** (`Object`): Двухзонный тариф (День / Ночь).
  * `description` (`String`): Описание ("Двозонний тариф (День/Ніч)").
  * `day` (`Object`): Дневная зона.
    * `hours` (`String`): Интервал времени действия (например, `"07:00 - 23:00"`).
    * `coefficient` (`Double`): Коэффициент оплаты (например, `1.0`).
    * `rate` (`Double`): Итоговый тариф за 1 кВт⋅ч в грн (например, `4.32`).
  * `night` (`Object`): Ночная зона.
    * `hours` (`String`): Интервал времени (например, `"23:00 - 07:00"`).
    * `coefficient` (`Double`): Коэффициент оплаты (например, `0.5` — скидка 50%).
    * `rate` (`Double`): Итоговый тариф за 1 кВт⋅ч в грн (например, `2.16`).

* **`three_zone`** (`Object`): Трехзонный тариф (Пик / Полупик / Ночь).
  * `description` (`String`): Описание ("Тризонний тариф (Пік/Напівпік/Ніч)").
  * `peak` (`Object`): Пиковая зона (`hours`: `"08:00 - 11:00, 20:00 - 22:00"`, `coefficient`: `1.5`, `rate`: `6.48`).
  * `half_peak` (`Object`): Полупиковая зона (`hours`: `"07:00 - 08:00, 11:00 - 20:00, 22:00 - 23:00"`, `coefficient`: `1.0`, `rate`: `4.32`).
  * `night` (`Object`): Ночная зона (`hours`: `"23:00 - 07:00"`, `coefficient`: `0.4`, `rate`: `1.728`).

---

### 2.3. Блок `water` (Водоснабжение и Водоотведение)

| Поле | Тип | Описание | Пример |
|---|---|---|---|
| `source_url` | `String` | Ссылка на сводный веб-источник тарифов по водоканалам. | `"https://index.minfin.com.ua/..."` |
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
| `unit` | `String` | Единица измерения объёма. | `"m3"` |
| `effective_date` | `String` | Дата вступления тарифа в силу (`YYYY-MM-DD`). | `"2022-10-01"` |
| `decree_info` | `String` | Реквизиты действующего тарифа. | `"Розпорядження КМВА № 673 від 30.09.2022..."` |

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
    @SerialName("water") val water: WaterTariff,
    @SerialName("hot_water") val hotWater: HotWaterTariff? = null,
    @SerialName("heating") val heating: HeatingTariff? = null
)

@Serializable
data class ElectricityTariff(
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("base_rate") val baseRate: Double,
    @SerialName("unit") val unit: String,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("update_date") val updateDate: String,
    @SerialName("decree_info") val decreeInfo: String,
    @SerialName("zones") val zones: ElectricityZones
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
    @SerialName("unit") val unit: String,
    @SerialName("effective_date") val effectiveDate: String,
    @SerialName("decree_info") val decreeInfo: String
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

---

### 4.4. Расчет стоимости Отопления

Пользователь выбирает поставщика из `heating.cities`. Показания снимаются с домового или квартирного теплосчётчика в Гкал.

1. **Одноставковый тариф (`tariff_type = "one_rate"`):**
   $$\text{Сумма грн} = \Delta \text{Гкал} \times \text{city.rate\_gcal}$$

2. **Двухставковый тариф (`tariff_type = "two_rate"`):** переменная часть считается так же, а постоянная зависит от подключённой тепловой нагрузки дома ($P$, Гкал/год), поделённой между квартирами. Жилец этой величины обычно не знает, поэтому рекомендуется считать только переменную часть, а `rate_gcal_hour` показывать справочно:
   $$\text{Сумма грн} = \Delta \text{Гкал} \times \text{city.rate\_gcal} + \frac{P \times \text{city.rate\_gcal\_hour}}{12}$$

> ⚠️ Перед расчётом проверьте, что выбранный пользователем `city_code` вообще присутствует в блоке — покрытие городов у `water`, `hot_water` и `heating` разное (см. раздел 1).

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
     * **GitHub Pages:** `https://alxpanther.github.io/communal_tarrifs/tariffs_<код>.json`
   * Поле `path` в индексе (раздел 6) отменяет обе раскладки, если файл лежит не там.
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

### 6.4. Правила, которые соблюдает приложение

* **`path` принимается только относительный.** Абсолютный адрес (`http://…`, `//…`), путь от корня
  (`/…`), любой путь с `..` или с обратными слэшами игнорируется, и действует стандартная раскладка.
  Индекс приходит из сети, а по указанному в нём адресу приложение ходит само — уводить его на чужой
  хост нельзя.
* **Недоступный, битый или пустой индекс ничего не убирает.** Остаётся предыдущая сохранённая копия,
  а страны из файлов поставки есть всегда.
* **Страна, уже выбранная у адреса, из списка не исчезает** — даже если пропала из индекса.
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
