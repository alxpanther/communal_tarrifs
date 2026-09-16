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

The file consists of seven parts:

1. **Root metadata** — file version, country, currency, update timestamp.
2. **`electricity`** — the country-wide electricity tariff: a base rate, one/two/three-zone meters,
   and every household tariff the source prints (`plans`).
3. **`electricity_cities`** — electricity tariffs of cities whose tariff differs from the country-wide
   one, in the same shape, per city.
4. **`water`** — centralised cold water supply and sewage, per city.
5. **`hot_water`** — centralised hot water supply (per m³).
6. **`heating`** — centralised heating (per Gcal).
7. **`gas`** — natural gas, per city: the price of the gas, the price of delivering it, every offer
   the source prints and the consumption norms of a household without a meter.

> ⚠️ **Compatibility.** `hot_water` and `heating` were added after `electricity` and `water`;
> `electricity_cities`, `electricity.plans` and the hot water components were added in September
> 2026, and `gas` — a new root block — later that month. No existing field was renamed, removed or re-typed, so existing code keeps reading the file
> as before. The only requirement is that the parser ignores unknown keys:
> `Json { ignoreUnknownKeys = true }` for `kotlinx.serialization` (Moshi and Gson do it by default).

### City coverage differs between blocks

The city lists in the three city-based blocks **do not match**, and are not expected to:

| Block | Who sets the tariff | Cities today |
|---|---|---|
| `water` | NKREKP, for every water utility | ~50 |
| `hot_water` | NKREKP plus local authorities | ~18 |
| `heating` | NKREKP plus local authorities | ~28 |
| `gas` | suppliers (gas price) and NKREKP (delivery) | ~33 |

The aggregate source publishes only tariffs set by NKREKP, so a supplier with a municipal tariff
only reaches the JSON if it is configured separately (as KP "Kyivteploenergo" is). The app must
handle "no heating data for the selected city" gracefully.

### `source_url` can be empty

The field comes from the days when one aggregate page held a whole block, and a country collected
city by city usually has no such page: Moldova reads each water utility's own site. It is therefore
filled only when every city of a block is read from the same single page, and is an empty string
otherwise. The app must treat it as informational and never assume it is set — an empty value means
"several sources", not "no data".

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
| `electricity_cities` | `Object` | Electricity tariffs of single cities (section 2.2a). Always present; `cities` is empty where the country-wide tariff applies everywhere. | `{ ... }` |
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
| `zones` | `Object` | Rates for multi-zone meters. | `{ ... }` |
| `plans` | `Array<Object>` | Every household tariff the source prints, as printed (section 2.2, `electricity.plans[]`). | `[ ... ]` |

#### `electricity.zones`

* **`two_zone`** (`Object`): two-zone tariff (day / night).
  * `description` (`String`): human description ("Двухзонный тариф (День/Ночь)").
  * `day` (`Object`): day zone.
    * `hours` (`String`): time window as the source prints it, e.g. `"07:00 - 23:00"`; an empty string when the source prints none.
    * `coefficient` (`Double`): `rate / base_rate`, rounded to four digits. Informational.
    * `rate` (`Double`): price per kWh, e.g. `4.32`.
  * `night` (`Object`): night zone, same fields (`"23:00 - 07:00"`, `0.5`, `2.16`).

* **`three_zone`** (`Object`): three-zone tariff (peak / half-peak / night).
  * `description` (`String`): human description ("Трехзонный тариф (Пик/Полупик/Ночь)").
  * `peak` (`Object`): peak zone (`hours`: `"08:00 - 11:00, 20:00 - 22:00"`, `coefficient`: `1.5`, `rate`: `6.48`).
  * `half_peak` (`Object`): half-peak zone (`hours`: `"07:00 - 08:00, 11:00 - 20:00, 22:00 - 23:00"`, `coefficient`: `1.0`, `rate`: `4.32`).
  * `night` (`Object`): night zone (`hours`: `"23:00 - 07:00"`, `coefficient`: `0.4`, `rate`: `1.73`).

> `base_rate` and `zones` repeat the prices of the default plan (`is_default: true` in `plans`),
> first consumption band, in the season of the day the file was generated. They exist for apps that
> do not read `plans`. A source that prints no single-rate price — Armenia prints day and night only —
> has `base_rate` equal to the day price. A meter kind the source does not price at all carries
> `base_rate` in every zone, `coefficient` `1.0`, empty `hours`, and a description ending in "(не
> применяется, ставка одна)". No rate is ever derived from a coefficient.

#### `electricity.plans[]`

One element per group of consumers the source prices separately — a flat with a gas stove, a flat
with an electric stove, a rural household, a low-income family, electric heating. Which groups are
read is set in config; a group the source does not print on a given run is absent.

| Field | Type | Description | Example |
|---|---|---|---|
| `plan_code` | `String` | Stable latin key of the group inside the country. | `"standard"`, `"electric_stove"`, `"rural"` |
| `name` | `String` | Name of the group, in Russian, for the interface. | `"Квартиры с электроплитами"` |
| `is_default` | `Boolean` | The group `base_rate` and `zones` are taken from. Exactly one per block. | `true` |
| `tier_basis` | `String?` | How consumption bands apply: `"part"` — each part of the month's consumption is billed at the price of its band; `"whole"` — the whole month is billed at the price of the band it reaches; `null` — no bands, or the source does not say. | `"part"` |
| `tiers_per_resident` | `Boolean?` | `true` when the band limits are per resident of the flat, `false` when per flat, `null` when there are no bands or the source does not say. | `true` |
| `monthly_charge` | `Double?` | Fixed charge per month, independent of consumption; `null` when there is none. | `1.0` |
| `rates` | `Array<Object>` | One element per printed price. | `[ ... ]` |

Element of `rates[]`:

| Field | Type | Description | Example |
|---|---|---|---|
| `meter` | `String` | `"single"`, `"two_zone"` or `"three_zone"`. | `"two_zone"` |
| `zone` | `String` | `"all"` for `single`; `"day"`/`"night"` for `two_zone`; `"peak"`/`"half_peak"`/`"night"` for `three_zone`. | `"night"` |
| `hours` | `String` | Hours of the zone as printed; empty when not printed. | `"23:00 - 07:00"` |
| `tier` | `Int?` | Number of the consumption band, from 1; `null` when the price does not depend on consumption. | `2` |
| `above_kwh` | `Double?` | The band applies to monthly consumption above this; `null` from zero or when not printed. | `200` |
| `up_to_kwh` | `Double?` | The band applies up to this, inclusive; `null` when open-ended or not printed. | `400` |
| `season_from` | `String?` | `MM-DD`: first day of a season recurring every year; `null` for all year. | `"10-01"` |
| `season_to` | `String?` | `MM-DD`: last day of that season, inclusive. A season may cross the new year. | `"04-30"` |
| `rate` | `Double` | Price per kWh, VAT included. | `36.48` |

A band may carry a `tier` without limits: Almaty prints the price of each level and not its bounds.
Then the band a household is in cannot be computed from the file, and the app has to ask the user
or fall back to the first band.

### 2.2a. Block `electricity_cities`

Where a city's electricity tariff differs from the country-wide one — Russian regions set their own —
the city is listed here. For a city absent from this block the country-wide `electricity` applies.

| Field | Type | Description |
|---|---|---|
| `source_url` | `String` | The single page every city is read from, or an empty string. |
| `update_date` | `String` | Date the block was last refreshed, `YYYY-MM-DD`. |
| `cities` | `Array<Object>` | One element per city. |

Element of `electricity_cities.cities[]`: `city_code`, `city_name`, `supplier` and `unit` as in
`water.cities[]`, plus `base_rate`, `effective_date`, `decree_info`, `zones` and `plans` exactly as in
section 2.2. `city_code` is the city's code in the country, the same as in its water block where the
city has one water utility.

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
| `component_water` | `Double?` | Two-component tariff only: the carrier component, per m³. Absent otherwise. | `52.63` |
| `component_energy` | `Double?` | Two-component tariff only: the energy component, per Gcal. | `2706.23` |
| `heat_norm` | `Double?` | Two-component tariff only: the norm `rate` was folded with, Gcal per m³. | `0.05131` |
| `heat_norms` | `Array<Object>?` | The region's norms for every kind of building, where the source prints them. Absent otherwise. | `[ ... ]` |
| `unit` | `String` | Volume unit. | `"m3"` |
| `effective_date` | `String` | Date the tariff came into force, `YYYY-MM-DD`. | `"2022-10-01"` |
| `decree_info` | `String` | Provenance of the tariff. | `"Розпорядження КМВА № 673 від 30.09.2022..."` |

Element of `heat_norms[]`: `system` (`String`: `"open"`, `"closed"` or `"decentralized"`),
`insulated_risers` (`Boolean?`), `towel_rails` (`Boolean?`), `value` (`Double`, Gcal per m³). A `null`
flag means the norm does not depend on it.

For a two-component tariff `rate = component_water + component_energy × heat_norm`, rounded to
kopecks; `heat_norm` is the norm of the most common building, named in config.

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

### 2.6. Block `gas` (natural gas)

| Field | Type | Description | Example |
|---|---|---|---|
| `source_url` | `String` | The single page the block is read from, or an empty string. | `"https://index.minfin.com.ua/ua/tariff/gas/"` |
| `update_date` | `String` | Date the block was last refreshed, `YYYY-MM-DD`. | `"2026-09-16"` |
| `cities` | `Array<Object>` | One element per city — per distribution network, where a city has two. | `[...]` |

Present in every file; its `cities` is empty in a country whose gas is not collected yet.

#### Element of `gas.cities[]`

| Field | Type | Description | Example |
|---|---|---|---|
| `city_code` | `String` | Stable key of the entry inside the block, from the registry section `gas_suppliers`. | `"kyiv"`, `"ternopil_hazmerezhi"` |
| `city_name` | `String` | City name, for the UI. | `"Київ"` |
| `supplier` | `String` | Supplier of the default plan. | `"ТОВ ГК \"Нафтогаз України\""` |
| `unit` | `String` | Always `"m3"`: every price in the block is per cubic metre, whatever the source printed. | `"m3"` |
| `rate` | `Double` | Price of 1 m³ of gas in the default plan: first band, today's season, VAT included. | `7.96` |
| `distributor` | `String` | Distribution network operator, where delivery is billed apart from the gas; empty otherwise. | `"ПАТ \"Київгаз\""` |
| `distribution_rate` | `Double` | Delivery price per m³, VAT included; `0.0` where delivery is part of the gas price. | `0.384` |
| `effective_date` | `String` | Date the current price took effect, `YYYY-MM-DD`. | `"2026-09-01"` |
| `decree_info` | `String` | Provenance of the prices. | `"Ціни постачальників і тарифи операторів ГРМ станом на 01.09.2026"` |
| `plans` | `Array<Object>` | Every offer the source prints. Exactly one has `is_default`. | `[ ... ]` |
| `norms` | `Array<Object>` | Monthly consumption norms of a household without a meter; empty when the source prints none. | `[ ... ]` |
| `norms_decree` | `String` | The act that sets the norms; empty when there are none. | `"Постанова КМ України № 143 від 27.02.2019"` |

Element of `plans[]`:

| Field | Type | Description | Example |
|---|---|---|---|
| `plan_code` | `String` | Stable latin key of the offer inside the city. | `"naftohaz_ukrainy_annual"` |
| `name` | `String` | Name of the offer, in Russian, for the interface. | `"Нафтогаз України, годовой тариф"` |
| `is_default` | `Boolean` | The offer `supplier` and `rate` are taken from. | `true` |
| `supplier` | `String` | Who sells the gas under this offer. | `"ТОВ \"Асканія Енерджи\""` |
| `contract` | `String?` | `"annual"` — a price fixed for a year, `"monthly"` — a price that changes monthly, `null` — the source makes no such distinction. | `"annual"` |
| `usage` | `String?` | `"cooking"` or `"heating"` when the price depends on what the gas is used for; `null` otherwise. | `null` |
| `metered` | `Boolean?` | `true` — price for a household with a meter, `false` — without, `null` — the same for both. | `null` |
| `monthly_charge` | `Double?` | Fixed charge per month, independent of consumption; `null` when there is none. | `null` |
| `rates` | `Array<Object>` | One element per printed price. | `[ ... ]` |

Element of `rates[]`:

| Field | Type | Description | Example |
|---|---|---|---|
| `tier` | `Int?` | Number of the consumption band, from 1; `null` when the price does not depend on consumption. | `1` |
| `above_m3` | `Double?` | The band applies to consumption above this; `null` from zero or when not printed. | `1200` |
| `up_to_m3` | `Double?` | The band applies up to this, inclusive; `null` when open-ended or not printed. | `2500` |
| `tier_period` | `String?` | `"month"` or `"year"` — what the band limits are counted over; `null` without bands. | `"year"` |
| `season_from` | `String?` | `MM-DD`: first day of a season recurring every year; `null` for all year. | `"10-01"` |
| `season_to` | `String?` | `MM-DD`: last day of that season, inclusive. | `"04-30"` |
| `rate` | `Double` | Price per m³, VAT included. | `9.95` |

Element of `norms[]`:

| Field | Type | Description | Example |
|---|---|---|---|
| `usage` | `String` | `"stove_with_hot_water"` — gas stove with centralised hot water; `"stove_without_hot_water"` — stove, no centralised hot water and no water heater; `"stove_and_water_heater"` — stove and gas water heater; `"water_heater"` — water heater only; `"heating"` — individual heating. | `"stove_with_hot_water"` |
| `basis` | `String` | `"per_person"` — per resident, `"per_m2"` — per m² of heated area. | `"per_person"` |
| `value` | `Double` | m³ per month. | `3.28` |
| `heating_season_only` | `Boolean` | The norm applies only during the heating season. | `false` |

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

## 4. Billing formulas for the Android app

### 4.1. Electricity

The meter type is chosen by the user in the meter settings (single-zone, two-zone, three-zone).

1. **Single-zone meter:**
   $$\text{UAH} = \Delta \text{kWh} \times \text{electricity.base\_rate}$$

2. **Two-zone meter (day / night):**
   $$\text{UAH} = (\Delta \text{kWh}_{\text{day}} \times \text{electricity.zones.two\_zone.day.rate}) + (\Delta \text{kWh}_{\text{night}} \times \text{electricity.zones.two\_zone.night.rate})$$

3. **Three-zone meter (peak / half-peak / night):**
   $$\text{UAH} = (\Delta \text{kWh}_{\text{peak}} \times \text{rate}_{\text{peak}}) + (\Delta \text{kWh}_{\text{half-peak}} \times \text{rate}_{\text{half\_peak}}) + (\Delta \text{kWh}_{\text{night}} \times \text{rate}_{\text{night}})$$

The three formulas above use the older fields and are exact only for a household in the default
plan whose consumption stays in the first band. With `plans`:

1. Take the tariff of the user's city from `electricity_cities`, or `electricity` when the city is
   not there; then the plan the user picked (`plan_code`), or the one with `is_default`.
2. Keep the rows of the user's `meter` whose season covers the billing month (`season_from` is
   `null`, or the month falls between `season_from` and `season_to`, crossing the new year if
   `season_from` > `season_to`).
3. Without bands (`tier` is `null`) each zone has one row: bill as in the formulas above.
4. With bands, per zone: when `tier_basis` is `"part"`, the consumption up to the first
   `up_to_kwh` is billed at the first band's rate, the next part at the second, and so on; when
   `"whole"`, all consumption is billed at the rate of the band the month's consumption falls in.
   For a multi-zone meter the file does not say whether the band is found per zone or from the
   month's total over all zones; until a source says, use the total. When
   `tiers_per_resident` is `true`, multiply the limits by the number of residents. When
   `tier_basis` is `null` or the limits are `null`, the file does not say enough to split — ask the
   user or bill by the first band.
5. Add `monthly_charge` once per month when it is set.

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

For a two-component tariff (`component_energy` is set) and a user who told the app their building,
use the norm of that building from `heat_norms` instead of the one folded into `rate`:

$$\text{price per m}^3 = \text{component\_water} + \text{component\_energy} \times \text{norm}$$

Without `heat_norms`, or with a building not in it, bill by `rate`.

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

### 4.5. Gas

The user picks a city from `gas.cities` and, where it has several, a plan (`plan_code`, defaulting to
the one with `is_default`). The price of 1 m³ is the plan's rate plus delivery:

$$\text{price per m}^3 = \text{plan rate} + \text{city.distribution\_rate}$$

1. **With a gas meter:**
   $$\text{UAH} = \Delta \text{m}^3 \times \text{price per m}^3$$
2. **Without a meter:** the user says what the gas is used for (`norms[].usage`) and how many
   residents there are, or the heated area for `per_m2`:
   $$\text{UAH} = \text{norm.value} \times \text{residents (or m}^2\text{)} \times \text{price per m}^3$$
   A norm with `heating_season_only` is charged only in the months of the heating season.

The plan rate is picked like an electricity price (section 4.1, steps 2–5): the rows whose season
covers the month; with bands, the band the consumption reaches — counted over the month or the year
by `tier_period`; plus `monthly_charge` where it is set.

Ukraine bills delivery by the annual contracted capacity, which for a household is its average
monthly consumption (with a meter) or the norm (without one); `distribution_rate` is already the
annual tariff, so multiplying it by the month's m³ gives the bill. The user needs to enter nothing
more.

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
     * **GitHub Pages:** `https://alxpanther.github.io/communal_tarrifs/tariffs_<cc>.json`, and the
       same file at `…/communal_tarrifs/<cc>/tariffs_<cc>.json`
   * The `path` field of the index (section 6) overrides the layout of the host that published that
     index, and of no other host.
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

The app reads each host through that host's own index: the index first, then the file at the
`path` it names; a host whose index does not arrive or does not list the country is passed over as
a whole. Builds up to 1.8.0 did otherwise — they kept whichever index they read first, normally the
Cloudflare one, and applied its `path` to every host. That is why Pages carries each country file at
the Cloudflare path as well: for those builds, without that copy the mirror answers 404 exactly
when the CDN is unreachable.

### 6.4. Rules the app follows

* **Only a relative `path` is accepted.** An absolute address (`http://…`, `//…`), a root-relative
  path (`/…`), anything containing `..` or backslashes is ignored and the standard layout applies.
  The index arrives from the network, and the app walks the path it names — it must not be led to
  someone else's host.
* **An unreachable, broken or empty index removes nothing.** The previously saved copy stays, and
  the bundled countries are always there.
* **A country already chosen for an address never disappears** from the list, even if it left the
  index — with one exception, described next.
* **A country can be retired, and then it is gone from the index entirely.** `enabled: false` only
  hides a country while its file stays published; retirement deletes the file from every host and
  leaves no record in the index at all. It means nobody can refresh those tariffs any more, so the
  app must stop offering the country, and must tell a user who had selected it that its tariffs no
  longer exist rather than keep charging from a cached file forever. Turkmenistan is the first:
  nothing published anywhere carries its utility tariffs.
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
