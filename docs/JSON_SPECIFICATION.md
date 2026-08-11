# Спецификация JSON формата тарифов ЖКХ (tariffs_ua.json)

Данный документ содержит полную техническую спецификацию формата `tariffs_ua.json`, детальное описание каждого поля, готовые Kotlin data-классы и бизнес-логику расчетов коммунальных услуг для использования в Android-приложении (учет счетчиков).

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
| `country` | `String` | Код страны по стандарту ISO 3166-1 alpha-2. | `"UA"` |
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
| `city_code` | `String` | Уникальный латинский идентификатор города (slug, Primary Key для приложения). Стабилен между обновлениями: значения хранятся в постоянном реестре `config/city_registry.json` и после первого назначения не меняются. | `"kyiv"`, `"lviv"` |
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
| `city_code` | `String` | Уникальный латинский идентификатор (Primary Key). Стабилен между обновлениями, хранится в `config/city_registry.json` (секция `heat_suppliers`). | `"kyiv"` |
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

Для парсинга `tariffs_ua.json` в Android-приложении вы можете использовать следующие Data Classes.

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

1. **Первый запуск (Offline Fallback):**
   * При сборке Android APK поместите актуальный `tariffs_ua.json` в папку `app/src/main/assets/tariffs_ua_default.json`.
   * При отсутствии сети интернет приложение загружает данные из локальных `assets`.

2. **Фоновая синхронизация (Remote Update):**
   * При наличии интернет-соединения приложение обращается по одному из адресов:
     * **Cloudflare CDN / R2:** `https://tarrifs.foleks.com/ua/tariffs_ua.json`
     * **GitHub Pages:** `https://alxpanther.github.io/communal_tarrifs/tariffs_ua.json`
   * Приложение сравнивает поле `last_updated_at` (или `update_date`) удаленного JSON с сохраненным локально.
   * Если удаленный даташтамп новее — кэш в локальной БД (Room / SharedPreferences / DataStore) обновляется.
