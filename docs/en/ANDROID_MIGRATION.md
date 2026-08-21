# Android task brief: hot water and heating

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ANDROID_MIGRATION.md](../ru/ANDROID_MIGRATION.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

> **Audience:** the assistant (or developer) sent to this repository to implement the matching part
> in the Android application.
>
> **What this file is:** a description of the changes already made to `tariffs_ua.json` on the
> pipeline side, plus the list of what remains to be done in the app. It is not a changelog, it is a
> work brief — read it top to bottom.

---

## 0. Where to start

1. Read this file completely.
2. Read [JSON_SPECIFICATION.md](JSON_SPECIFICATION.md) — the full field reference and Kotlin DTOs
   you can copy verbatim.
3. Look at the real data: [docs/tariffs_ua.json](../tariffs_ua.json) — exactly what the app
   downloads.
4. Only then open the app project and find where the tariff JSON is parsed.

The application lives in a **separate directory** (a sibling project in `~/AndroidStudioProjects`).
This repository is only the data generator; there is no app code here.

---

## 1. What changed in the JSON

Two **new blocks** appeared at the root: `hot_water` and `heating`.

```jsonc
{
  "version": "1.0",
  "last_updated_at": "...",
  "country": "UA",
  "currency": "UAH",
  "electricity": { ... },   // UNCHANGED
  "water":       { ... },   // UNCHANGED
  "hot_water":   { ... },   // NEW
  "heating":     { ... }    // NEW
}
```

**`electricity` and `water` did not change by a single byte** — no field was renamed, removed or
re-typed. Every existing piece of code reading electricity and cold water keeps working untouched.

---

## 2. The mandatory minimum (without it the app crashes)

If the JSON is parsed with `kotlinx.serialization`, the parser must ignore unknown root keys:

```kotlin
val json = Json { ignoreUnknownKeys = true }
```

Without that flag `Json.decodeFromString<TariffResponse>(...)` throws
`SerializationException: Encountered an unknown key 'hot_water'`, and the app stops reading tariffs
**altogether, including the old blocks**.

* If the flag is already set — nothing to do, the app keeps working and simply does not show the new
  services.
* If Moshi or Gson is used — they ignore unknown keys by default, also nothing to do.

**This is the first thing to find and verify in the app project.**

---

## 3. Data models

Ready DTOs are in [JSON_SPECIFICATION.md, section 3](JSON_SPECIFICATION.md#3-ready-made-kotlin-data-classes-kotlinxserialization). Key points:

```kotlin
@Serializable
data class TariffResponse(
    // ... existing fields unchanged ...
    @SerialName("hot_water") val hotWater: HotWaterTariff? = null,
    @SerialName("heating")   val heating:  HeatingTariff?  = null
)
```

**Both fields must be nullable with a default.** Reason: the user's cache (Room / DataStore / a file
in `filesDir`) may hold a JSON downloaded earlier, without those blocks. Declaring them non-null
crashes the app when it reads its own cache after the update.

The block structure mirrors the existing `water`:

| Block | List element | Tariff |
|---|---|---|
| `hot_water` | `CityHotWaterTariff` | `rate: Double` — UAH per m³ incl. VAT |
| `heating` | `CityHeatingTariff` | `rateGcal: Double` — UAH per Gcal; `rateGcalHour: Double` — standing charge, `0.0` for single-rate; `tariffType: String` — `"one_rate"` / `"two_rate"` |

---

## 4. Calculations

The formulas with derivations are in
[JSON_SPECIFICATION.md, sections 4.3 and 4.4](JSON_SPECIFICATION.md#43-hot-water). In short:

**Hot water** (meter in m³, exactly like cold water):

```kotlin
val sum = deltaCubicMeters * city.rate
```

**Heating** (meter in Gcal):

```kotlin
val sum = deltaGcal * city.rateGcal
```

For `tariffType == "two_rate"` there is formally a standing part as well — `rateGcalHour` multiplied
by the building's connected heat load in Gcal/hour. **The resident does not know that figure** and
the app has nowhere to get it, therefore:

* bill on `rateGcal`;
* either hide `rateGcalHour` entirely, or show it for information with a caption such as
  "абонплата за підключене навантаження, нараховується постачальником".

Do not try to guess the load or ask the user for it — they will not find that number on their bill
in any usable form.

---

## 5. Four traps — read before writing code

### 5.1. The city lists of the three blocks differ

| Block | Cities |
|---|---|
| `water` | 50 |
| `hot_water` | 18 |
| `heating` | 28 |

This is not incomplete scraping: the aggregate source publishes only tariffs set by NKREKP, and
centralised heat simply does not exist everywhere. It is the normal state and will not change.

**Consequence:** the city the user selected may have no heating data at all. The app must survive
that — hide the service rather than crash or render zeros.

### 5.2. `city_code` does not always match across blocks

It matches where the city has **one** heat supplier: `kyiv`, `lviv`, `vinnytsia`, `kharkiv`,
`poltava`, `rivne`, `sumy`, `odesa`, `zaporizhzhia` and most of the rest.

It does not match where there are several suppliers — then the plain code goes to nobody:

| City | `water` | `heating` |
|---|---|---|
| Дніпро | `dnipro` | `dnipro_teploenerho`, `dnipro_komenerhoservis` |
| Миколаїв | `mykolaiv` | `mykolaiv_mykolaivoblteploenerho`, `mykolaiv_mykolaivska_teploelektrotsentral` |
| Черкаси | `cherkasy` | `cherkasy_cherkaske_khimvolokno`, `cherkasy_cherkasyteplokomunenerho` |
| Чернігів | `chernihiv` | `chernihiv_firma`, `chernihiv_oblteplokomunenerho` |

This is not a bug: different districts of those cities are served by different companies with
different tariffs, and the choice cannot be made for the user.

**How to do it right:**

* `city_code` is a stable primary key **within its own block**. Store the user's selection separately
  per service.
* Relate services through `city_name`: if the user picked Черкаси for water, offer both heating
  records with `cityName == "Черкаси"` and let them pick their supplier.
* Do not write `heating.cities.first { it.cityCode == waterCityCode }` — for four cities that
  silently returns null.

For the code assignment rules see [README.md → Как назначается «простой» код города](../../README.md#как-назначается-простой-код-города).

### 5.3. An `effective_date` in the past is normal

Most hot water and heating records carry `2021-02-01`, Kyiv carries `2022-10-01`. This is **not**
stale data. A moratorium on raising household heat tariffs is in force for the whole period of
martial law plus six months, so the numbers really are frozen since then. Verified against the
suppliers' own websites — they match to the kopeck.

The file holds **the tariff households actually pay**. The economically justified tariffs (one and a
half to two times higher, published next to it on company sites) never enter the file.

Do not label the tariff "outdated" in the UI based on the date. If you want to show something, show
`decree_info` — it carries a human caption such as "Розпорядження КМВА № 673 від 30.09.2022, тариф
для населення на період воєнного стану".

### 5.4. Kyiv heat means Kyivteploenergo

`city_code == "kyiv"` in `hot_water` and `heating` is КП «КИЇВТЕПЛОЕНЕРГО», the city's main supplier
(97.89 UAH/m³ and 1654.41 UAH/Gcal). The second Kyiv supplier, ТОВ «Євро-Реконструкція», serves part
of the districts and sits under the code `kyiv_yevro_rekonstruktsiia` (75.96 and 1408.27). Kyiv users
must be offered a choice between them.

---

## 6. Work checklist

- [ ] Find where the `Json` parser is created, make sure `ignoreUnknownKeys = true` is set. **Do this first.**
- [ ] Add the DTOs `HotWaterTariff`, `CityHotWaterTariff`, `HeatingTariff`, `CityHeatingTariff` (copy from the specification).
- [ ] Add `hotWater` and `heating` to `TariffResponse` — nullable, with `= null`.
- [ ] Extend the storage layer (Room entities / DataStore) for the two new city lists.
- [ ] Add two meter types to the domain model: hot water (m³) and heating (Gcal).
- [ ] Supplier selection screen: a separate selection for hot water and heating, do not reuse the cold water selection (see 5.2).
- [ ] Implement the calculations from section 4.
- [ ] Handle "no data for your city for this service" — hide the service instead of showing zeros.
- [ ] Refresh `app/src/main/assets/tariffs_ua_default.json` from [assets/tariffs_ua_default.json](../../assets/tariffs_ua_default.json) in this repository.
- [ ] Verify that an old cached JSON without the new blocks still parses and does not crash the app.
- [ ] UI strings only through `.arb` / `strings.xml`; hardcoded service names are not acceptable.

---

## 7. Where the data comes from (informational, no action needed)

| Block | Source |
|---|---|
| `electricity` | tariffa.com.ua |
| `water` | index.minfin.com.ua/ua/tariff/water/ |
| `hot_water` | index.minfin.com.ua/ua/tariff/hotwater/ plus a dedicated Kyiv page for КП «Київтеплоенерго» |
| `heating` | index.minfin.com.ua/ua/tariff/heating/ plus a manual override for КП «Київтеплоенерго» |

Kyiv heating is entered manually because КП «Київтеплоенерго» publishes its tariffs as PNG images
and PDFs, and the aggregate tables do not include it at all — they carry only NKREKP tariffs, while
KTE's tariff is municipal. Details in
[README.md → Ручное переопределение](../../README.md#-ручное-переопределение-тарифов-manual_override).

The file is published at two addresses, both serving the same content:

* `https://tarrifs.foleks.com/ua/tariffs_ua.json` (Cloudflare R2)
* `https://alxpanther.github.io/communal_tarrifs/tariffs_ua.json` (GitHub Pages)
