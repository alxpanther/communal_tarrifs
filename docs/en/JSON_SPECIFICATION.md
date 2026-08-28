# Specification of the utility tariff JSON (`tariffs_<cc>.json`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/JSON_SPECIFICATION.md](../ru/JSON_SPECIFICATION.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

This document is the complete technical specification of the tariff file format: every field,
ready-to-use Kotlin data classes, and the billing formulas the Android metering app implements.

There is **one file per country** — `tariffs_ua.json`, `tariffs_am.json`, `tariffs_az.json` — all
in the same format, with the country named by the `country` field. The list of countries that are
actually published is a separate file, described in section 6 (`tariffs_index.json`).

---

## 1. Overall structure

The file consists of five parts:

1. **Root metadata** — file version, country, currency, update timestamp.
2. **`electricity`** — electricity tariffs (base rate plus one/two/three-zone meters).
3. **`water`** — centralised cold water supply and sewage, per city.
4. **`hot_water`** — centralised hot water supply (UAH per m³).
5. **`heating`** — centralised heating (UAH per Gcal).

> ⚠️ **Compatibility.** `hot_water` and `heating` were added after `electricity` and `water`. The
> format of the first two did not change, so existing code keeps reading them as before. The only
> requirement is that the parser ignores unknown root keys: `Json { ignoreUnknownKeys = true }` for
> `kotlinx.serialization` (Moshi and Gson do it by default).

### City coverage differs between blocks

The city lists in the three city-based blocks **do not match**, and are not expected to:

| Block | Who sets the tariff | Cities today |
|---|---|---|
| `water` | NKREKP, for every water utility | ~50 |
| `hot_water` | NKREKP plus local authorities | ~18 |
| `heating` | NKREKP plus local authorities | ~28 |

The aggregate source publishes only tariffs set by NKREKP, so a supplier with a municipal tariff
only reaches the JSON if it is configured separately (as KP "Kyivteploenergo" is). The app must
handle "no heating data for the selected city" gracefully.

**`city_code` matches across blocks only where a city has a single supplier.** For Київ, Львів,
Вінниця, Харків and most others it does (`kyiv`, `lviv`, `vinnytsia`, `kharkiv`). But Дніпро,
Миколаїв, Черкаси and Чернігів have several heat suppliers, and there the plain code belongs to
nobody — only `dnipro_teploenerho`, `dnipro_komenerhoservis` and so on. Use `city_name` to relate
services to each other, and `city_code` as the stable selection key inside one block.

---

## 2. Field description

### 2.1. Root object

| Field | Type | Description | Example |
|---|---|---|---|
| `version` | `String` | Version of the JSON schema. | `"1.0"` |
| `last_updated_at` | `String` | ISO 8601 timestamp of the last file update. | `"2026-08-02T18:04:37.758583"` |
| `country` | `String` | Country code, ISO 3166-1 alpha-2, upper case. | `"UA"` |
| `country_names` | `Object` | Country name for the interface: key = app language code, value = the name in that language. Required: the app lists the country by it when the user picks an address. Missing key for the current language → `ru` is used; missing that too → the raw `country` code is shown. | `{ "ru": "Армения", "uk": "Вірменія" }` |
| `currency` | `String` | Tariff currency, ISO 4217. | `"UAH"` |
| `electricity` | `Object` | Electricity block (section 2.2). | `{ ... }` |
| `water` | `Object` | Water supply and sewage block (section 2.3). | `{ ... }` |
| `hot_water` | `Object` | Hot water block (section 2.4). | `{ ... }` |
| `heating` | `Object` | Heating block (section 2.5). | `{ ... }` |

---

### 2.2. Block `electricity`

| Field | Type | Description | Example |
|---|---|---|---|
| `source_url` | `String` | Web source of the official tariff. | `"https://tariffa.com.ua/..."` |
| `base_rate` | `Double` | Base (single-zone) tariff per kWh, UAH. | `4.32` |
| `unit` | `String` | Consumption unit. | `"kWh"` |
| `effective_date` | `String` | Date the tariff came into force, `YYYY-MM-DD`. | `"2024-06-01"` |
| `update_date` | `String` | Date the value was last checked, `YYYY-MM-DD`. | `"2026-08-02"` |
| `decree_info` | `String` | Legal act the tariff rests on (Cabinet of Ministers / NKREKP). | `"постановлением КМУ № 632..."` |
| `zones` | `Object` | Coefficients for multi-zone meters. | `{ ... }` |

#### `electricity.zones`

* **`two_zone`** (`Object`): two-zone tariff (day / night).
  * `description` (`String`): human description ("Двозонний тариф (День/Ніч)").
  * `day` (`Object`): day zone.
    * `hours` (`String`): time window, e.g. `"07:00 - 23:00"`.
    * `coefficient` (`Double`): payment coefficient, e.g. `1.0`.
    * `rate` (`Double`): resulting price per kWh in UAH, e.g. `4.32`.
  * `night` (`Object`): night zone.
    * `hours` (`String`): time window, e.g. `"23:00 - 07:00"`.
    * `coefficient` (`Double`): payment coefficient, e.g. `0.5` — a 50% discount.
    * `rate` (`Double`): resulting price per kWh in UAH, e.g. `2.16`.

* **`three_zone`** (`Object`): three-zone tariff (peak / half-peak / night).
  * `description` (`String`): human description ("Тризонний тариф (Пік/Напівпік/Ніч)").
  * `peak` (`Object`): peak zone (`hours`: `"08:00 - 11:00, 20:00 - 22:00"`, `coefficient`: `1.5`, `rate`: `6.48`).
  * `half_peak` (`Object`): half-peak zone (`hours`: `"07:00 - 08:00, 11:00 - 20:00, 22:00 - 23:00"`, `coefficient`: `1.0`, `rate`: `4.32`).
  * `night` (`Object`): night zone (`hours`: `"23:00 - 07:00"`, `coefficient`: `0.4`, `rate`: `1.728`).

> Every `rate` is derived by the pipeline as `base_rate × coefficient`; the zone rates are never
> taken from a model answer or edited independently.

---

### 2.3. Block `water` (supply and sewage)

| Field | Type | Description | Example |
|---|---|---|---|
| `source_url` | `String` | Aggregate web source for water utility tariffs. | `"https://index.minfin.com.ua/..."` |
| `update_date` | `String` | Date the section was last checked, `YYYY-MM-DD`. | `"2026-08-02"` |
| `cities` | `Array<Object>` | Per-city water utility tariffs. | `[...]` |

#### Element of `water.cities[]`

| Field | Type | Description | Example |
|---|---|---|---|
| `city_code` | `String` | Unique latin identifier (slug), the primary key for the app. Stable across updates: values are kept in the permanent registry `config/ua/city_registry.json` and never change once assigned. | `"kyiv"`, `"lviv"` |
| `city_name` | `String` | City or region name in Ukrainian, for the UI. | `"Київ"`, `"Львів"` |
| `supplier` | `String` | Water utility company name. | `"ПАТ АК \"Київводоканал\""` |
| `water_supply` | `Double` | Price per m³ of centralised cold water, UAH. `0.0` if the supplier does not provide the service. | `16.164` |
| `sewage` | `Double` | Price per m³ of sewage, UAH. `0.0` if not provided. | `14.22` |
| `total_rate` | `Double` | Sum of the two, per m³, UAH. | `30.384` |
| `unit` | `String` | Volume unit. | `"m3"` |
| `effective_date` | `String` | Date the tariff came into force, `YYYY-MM-DD`. | `"2022-01-01"` |
| `decree_info` | `String` | Provenance of the tariff. The source does not publish NKREKP decree numbers per utility, so this is composed from the validity period. | `"Тариф НКРЕКП, чинний з 01.01.2022"` |

---

### 2.4. Block `hot_water`

| Field | Type | Description | Example |
|---|---|---|---|
| `source_url` | `String` | Aggregate web source. | `"https://index.minfin.com.ua/ua/tariff/hotwater/"` |
| `update_date` | `String` | Date the section was last checked, `YYYY-MM-DD`. | `"2026-08-11"` |
| `cities` | `Array<Object>` | Per-city heat supplier tariffs. | `[...]` |

#### Element of `hot_water.cities[]`

| Field | Type | Description | Example |
|---|---|---|---|
| `city_code` | `String` | Unique latin identifier (primary key). Stable across updates, stored in `config/ua/city_registry.json`, section `heat_suppliers`. | `"kyiv"` |
| `city_name` | `String` | City name in Ukrainian, for the UI. | `"Київ"` |
| `supplier` | `String` | Heat supplier company name. | `"КП \"КИЇВТЕПЛОЕНЕРГО\""` |
| `rate` | `Double` | Price per m³ of hot water, UAH incl. VAT. | `97.89` |
| `unit` | `String` | Volume unit. | `"m3"` |
| `effective_date` | `String` | Date the tariff came into force, `YYYY-MM-DD`. | `"2022-10-01"` |
| `decree_info` | `String` | Provenance of the tariff. | `"Розпорядження КМВА № 673 від 30.09.2022..."` |

> 💡 `rate` holds the tariff **households actually pay**. For most suppliers it is frozen by the
> moratorium in force for the whole period of martial law and six months after it, which is why
> `effective_date` often points to 2021–2022 — that is not stale data. The economically justified
> tariffs published next to it on company sites never enter this file.

---

### 2.5. Block `heating` (centralised heating)

| Field | Type | Description | Example |
|---|---|---|---|
| `source_url` | `String` | Aggregate web source. | `"https://index.minfin.com.ua/ua/tariff/heating/"` |
| `update_date` | `String` | Date the section was last checked, `YYYY-MM-DD`. | `"2026-08-11"` |
| `cities` | `Array<Object>` | Per-city heat supplier tariffs. | `[...]` |

#### Element of `heating.cities[]`

| Field | Type | Description | Example |
|---|---|---|---|
| `city_code` | `String` | Unique latin identifier (primary key). | `"kyiv"` |
| `city_name` | `String` | City name in Ukrainian, for the UI. | `"Київ"` |
| `supplier` | `String` | Heat supplier company name. | `"КП \"КИЇВТЕПЛОЕНЕРГО\""` |
| `tariff_type` | `String` | `"one_rate"` (одноставковий) or `"two_rate"` (двоставковий). | `"one_rate"` |
| `rate_gcal` | `Double` | Price per Gcal, UAH incl. VAT. For a two-rate tariff this is the variable part. | `1654.41` |
| `rate_gcal_hour` | `Double` | Standing part of a two-rate tariff, UAH per Gcal/hour. `0.0` when `tariff_type = "one_rate"`. | `0.0` |
| `unit` | `String` | Heat energy unit. | `"Gcal"` |
| `effective_date` | `String` | Date the tariff came into force, `YYYY-MM-DD`. | `"2022-10-01"` |
| `decree_info` | `String` | Provenance of the tariff. | `"Розпорядження КМВА № 673 від 30.09.2022..."` |

> 💡 The standing part is charged not on consumed Gcal but on the building's connected heat load
> (Gcal/hour), a figure the resident does not know. The field is informational; the app may hide it
> and bill on `rate_gcal` alone.

---

## 3. Ready-made Kotlin data classes (`kotlinx.serialization`)

Always construct the parser with `ignoreUnknownKeys`, otherwise the next format extension crashes
the app:

```kotlin
val json = Json { ignoreUnknownKeys = true }
```

`hotWater` and `heating` are nullable with defaults so the app can still read an older cached file
that predates those blocks.

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

## 4. Billing formulas for the Android app

### 4.1. Electricity

The meter type is chosen by the user in the meter settings (single-zone, two-zone, three-zone).

1. **Single-zone meter:**
   $$\text{UAH} = \Delta \text{kWh} \times \text{electricity.base\_rate}$$

2. **Two-zone meter (day / night):**
   $$\text{UAH} = (\Delta \text{kWh}_{\text{day}} \times \text{electricity.zones.two\_zone.day.rate}) + (\Delta \text{kWh}_{\text{night}} \times \text{electricity.zones.two\_zone.night.rate})$$

3. **Three-zone meter (peak / half-peak / night):**
   $$\text{UAH} = (\Delta \text{kWh}_{\text{peak}} \times \text{rate}_{\text{peak}}) + (\Delta \text{kWh}_{\text{half-peak}} \times \text{rate}_{\text{half\_peak}}) + (\Delta \text{kWh}_{\text{night}} \times \text{rate}_{\text{night}})$$

---

### 4.2. Water supply and sewage

The user picks a city from `water.cities`; the app stores the `city_code`.

1. **Both services (water + sewage):**
   $$\text{UAH} = \Delta \text{m}^3 \times \text{city.total\_rate}$$

2. **Water supply only (no sewage connection / private house):**
   $$\text{UAH} = \Delta \text{m}^3 \times \text{city.water\_supply}$$

3. **Sewage only (own well plus municipal sewage):**
   $$\text{UAH} = \Delta \text{m}^3 \times \text{city.sewage}$$

---

### 4.3. Hot water

The user picks a supplier from `hot_water.cities` (the `city_code` is stored). Readings come from a
hot water meter in m³.

$$\text{UAH} = \Delta \text{m}^3 \times \text{city.rate}$$

---

### 4.4. Heating

The user picks a supplier from `heating.cities`. Readings come from a building or apartment heat
meter in Gcal.

1. **Single-rate tariff (`tariff_type = "one_rate"`):**
   $$\text{UAH} = \Delta \text{Gcal} \times \text{city.rate\_gcal}$$

2. **Two-rate tariff (`tariff_type = "two_rate"`):** the variable part is computed the same way, and
   the standing part depends on the building's connected heat load ($P$, Gcal/hour) split between
   apartments. Residents normally do not know that figure, so the recommendation is to bill the
   variable part only and show `rate_gcal_hour` for information:
   $$\text{UAH} = \Delta \text{Gcal} \times \text{city.rate\_gcal} + \frac{P \times \text{city.rate\_gcal\_hour}}{12}$$

> ⚠️ Before computing, check that the user's `city_code` exists in that block at all — coverage
> differs between `water`, `hot_water` and `heating` (see section 1).

---

## 5. Update and offline strategy

One file per country, and everything below happens per country: its own bundled file, its own
cache, its own check marks.

1. **First launch (offline fallback):**
   * The bundled file lives in the app as `assets/tariffs/tariffs_<cc>_default.json` (country code
     in lower case: `tariffs_ua_default.json`, `tariffs_am_default.json`).
   * The app discovers those files at run time through the asset manifest — the list of countries is
     nowhere in its code. Dropping a file in is enough.
   * With no network available, the app runs on them.

2. **Background sync (remote update):**
   * Hosts are tried in turn, and each has its own file layout:
     * **Cloudflare CDN / R2:** `https://tarrifs.foleks.com/<cc>/tariffs_<cc>.json`
     * **GitHub Pages:** `https://alxpanther.github.io/communal_tarrifs/tariffs_<cc>.json`
   * The `path` field of the index (section 6) overrides both layouts when a file lives elsewhere.
   * The app compares `last_updated_at` of the downloaded file with the cached one and rewrites the
     cache when the timestamp is newer.
   * An incomplete file is rejected: if the publisher lost the electricity block or more than half of
     a block's records, the cache is kept as it was.

---

## 6. Country index (`tariffs_index.json`)

The list of countries whose tariffs are published at all. It exists for one reason: a country added
after an app release must show up in the address form of a user who never updated the app.

Published at the root of **each** host:

* `https://tarrifs.foleks.com/tariffs_index.json`
* `https://alxpanther.github.io/communal_tarrifs/tariffs_index.json`

### 6.1. Example

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

### 6.2. Fields

| Field | Type | Req. | Description |
|---|---|---|---|
| `version` | `String` | yes | Index format version. The app reads `1.x`; an index with a higher major version is ignored whole and the country list stays as it was. |
| `generated_at` | `String` | no | When the index was built, ISO 8601. Diagnostics only. |
| `countries` | `Array<Object>` | yes | The countries. Order is irrelevant — the app sorts by name. |
| `countries[].country` | `String` | yes | ISO 3166-1 alpha-2. The key of the record; a record without it is dropped. |
| `countries[].country_names` | `Object` | yes | Same as in the tariff file. Needed to show the country **before** its file has been downloaded. |
| `countries[].currency` | `String` | no | ISO 4217. Informational; it does not change the app's currency. |
| `countries[].last_updated_at` | `String` | yes | The stamp taken from the country's own tariff file. |
| `countries[].path` | `String` | no | Path to the tariff file **relative to the root of the publication**. Without it the host's standard layout applies (section 5). |
| `countries[].enabled` | `Bool` | no | Defaults to `true`. `false` hides the country without deleting its file. |
| `countries[].min_app_version` | `String` | no | Minimum app version (`major.minor.patch`) below which the country is not shown. Empty means no limit. A version, not a build number: `--split-per-abi` gives one release different build numbers per architecture. |

### 6.3. Why each host carries its own copy

The layouts differ — flat on GitHub Pages, one folder per country on Cloudflare — so `path` differs
too. The generator writes both copies (`docs/tariffs_index.json` for Pages,
`dist/cloudflare/tariffs_index.json` for R2) from the same country registry,
[`config/countries.json`](../../config/countries.json).

### 6.4. Rules the app follows

* **Only a relative `path` is accepted.** An absolute address (`http://…`, `//…`), a root-relative
  path (`/…`), anything containing `..` or backslashes is ignored and the standard layout applies.
  The index arrives from the network, and the app walks the path it names — it must not be led to
  someone else's host.
* **An unreachable, broken or empty index removes nothing.** The previously saved copy stays, and
  the bundled countries are always there.
* **A country already chosen for an address never disappears** from the list, even if it left the
  index.
* The index is requested at app start at most once a day, and before every scheduled tariff check.

---

## 7. How to add a country

1. Generate `tariffs_<cc>.json` in the format of sections 1–4, with `country`, `currency` and
   `country_names` filled in.
2. Publish it on both hosts using the standard layout (section 5).
3. Add the country to `tariffs_index.json` on both hosts.
4. Optionally ship the same file as `assets/tariffs/tariffs_<cc>_default.json` in the next app
   version — then the country works offline from the first launch.

Step 4 is optional: a country from the index appears in the address form without it, and its tariffs
are downloaded the moment the user selects that country.

On the generator side the same job is described in
[ADDING_A_COUNTRY.md](ADDING_A_COUNTRY.md).
