# Спецификация JSON формата тарифов ЖКХ (tariffs_ua.json)

Данный документ содержит полную техническую спецификацию формата `tariffs_ua.json`, детальное описание каждого поля, готовые Kotlin data-классы и бизнес-логику расчетов коммунальных услуг для использования в Android-приложении (учет счетчиков).

---

## 📋 1. Общая структура JSON

Файл `tariffs_ua.json` состоит из трех основных блоков:
1. **Метаданные (Root)** — общая информация о файле, валюте, версии и времени обновления.
2. **`electricity`** — тарифы на электроэнергию (базовый тариф и зонные тарифы: 1/2/3 зоны).
3. **`water`** — тарифы на централизованное водоснабжение и водоотведение по городам Украины.

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

## 📱 3. Готовые Kotlin Data Classes (`kotlinx.serialization`)

Для парсинга `tariffs_ua.json` в Android-приложении вы можете использовать следующие Data Classes:

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
    @SerialName("water") val water: WaterTariff
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
