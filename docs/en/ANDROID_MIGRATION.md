# Android task brief

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ANDROID_MIGRATION.md](../ru/ANDROID_MIGRATION.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

> **Audience:** the assistant sent to the Android project (a sibling directory in
> `~/AndroidStudioProjects`, Flutter/Dart) to implement the app side of a data change made here.
>
> **What this file is:** a work brief, not a changelog. Read it top to bottom before touching the
> app, then read [JSON_SPECIFICATION.md](JSON_SPECIFICATION.md) for the field reference.

---

## 0. What is already done in the app — do not rebuild it

Verified in the app source, so that nothing below is implemented twice:

| Already there | Where |
|---|---|
| DTOs for all four blocks, unknown JSON keys ignored, `status` → `available` | `lib/domain/tariffs/tariff_catalog.dart` |
| `hasRates` per entry, so an entry with no rate never reaches the UI | same file |
| A separate saved supplier per service — `hotWaterCityCode`, `heatingCityCode` | `lib/domain/entities/house.dart` |
| Services related by `city_name`, not by `city_code` | `CityTariffs.named()` |
| Supplier picker with search, and the "my city is not in the list" path | `lib/presentation/widgets/city_picker_dialog.dart` |
| A new edition is rejected if a block loses too many charging cities | `TariffCatalog.acceptsAsSuccessor()` |
| Meter types `hotWater`, `heating`, and — already — `waterHeating` | `lib/domain/enums/meter_type.dart` |

The multi-supplier city case is handled too: a city with two heat companies offers both, and the
plain city code belongs to neither.

---

## 1. What changed on the data side

Tariffs are no longer copied from a hand-written config. Each city's tariff is fetched from the
regulator or the utility and read out of that document on the run that publishes it, then validated
before it may enter the file (see [ARCHITECTURE.md](ARCHITECTURE.md), section 8a).

Three consequences reach the app:

1. **`effective_date` and `decree_info` are now trustworthy and specific.** They come from the
   document the number was read from, not from a caption someone typed once.
2. **A city can now hold the same tariff for months and then change on a fixed date.** Regulators
   publish the whole indexation schedule years ahead; the file always carries the period in force
   on the day it was generated. Russia's indexation moved from 1 July to 1 October in 2026, so a
   date-based assumption about when tariffs change is wrong.
3. **A city may silently keep an old value.** When a source is unreachable the previous tariff stays
   published rather than being wiped — correct for the file, but it means `effective_date` is the
   only honest signal of freshness.

**The published schema has not changed.** No field was added, renamed or re-typed. Everything below
is app-side work that a schema change would enable, not work the current file forces.

---

## 2. The one real gap: two-component hot water

In Russia and several neighbouring countries hot water is not priced per cubic metre. It is priced
as two numbers:

* a **carrier component**, roubles per m³ — the water itself;
* an **energy component**, roubles per Gcal — heating that water.

A price per m³ exists only after multiplying the energy component by a **regional norm for heating
one m³**, and that norm depends on the building: open or closed system, insulated risers or not,
heated towel rails or not. In Sverdlovsk oblast the eight published norms run from 0.04912 to
0.06506 Gcal/m³ — a spread of a third on the heating part of the bill.

Today the pipeline folds the three numbers into a single `rate` and publishes that, picking the norm
for the most common building type. The arithmetic is spelled out in `decree_info`. This is honest
but approximate: a resident of a building with a different system pays a different price, and the
app has no way to say so.

### What to build

1. **Extend the DTO** — `CityHotWaterTariff` in `lib/domain/tariffs/tariff_catalog.dart`:
   `componentWater`, `componentEnergy`, `heatNorm`, all nullable with a default of `null`. Nullable
   is not a style choice: the user's cached file has no such keys, and a non-null field crashes the
   app when it reads its own cache after an update.
2. **Leave `rate` alone.** It stays the published price and the fallback. `hasRates` keeps meaning
   `available && rate > 0`.
3. **Ask the building's hot water system.** A new field on the house, next to the supplier pickers
   in `lib/presentation/screens/houses/house_edit_screen.dart`, with a Drift migration
   (`lib/data/database/tables.dart`, schema is at v13). Four to eight options, worded for a resident
   rather than for a regulator: "is there a heated towel rail on the hot water riser?" is answerable,
   "closed system with insulated risers" is not.
4. **Compute when possible.** Where all three components and the building's norm are known:
   `volume × (componentWater + componentEnergy × norm)`. Otherwise `volume × rate`, exactly as now.
5. **Show the breakdown** under the hot water figure — `52.63 + 2899.98 × 0.05131` — so a resident
   can check it against the bill. Today that arithmetic is buried in `decree_info` as prose.

Steps 1, 2 and 4 without step 3 change nothing: without the building's system there is no norm to
use, and the result is the same number the pipeline already computed. Do them together or not at all.

**This requires a schema change here first.** The three fields exist inside the pipeline and are
deliberately withheld from the published file (`PUBLISHED_FIELDS` in `common/ai_pipeline.py`),
because the field list is a contract with a released app. Ask before publishing them.

---

## 2a. A country can now disappear

Until now the country list only grew. A country can now be retired here — its file deleted from
both hosts and its record removed from the index — because nobody can refresh its tariffs any more.
Turkmenistan is the first: nothing published anywhere in the country carries a utility tariff.

The app has to handle that, and the current rule ("a country already chosen never disappears") is
not enough:

1. A country missing from a freshly downloaded index is gone deliberately, not by accident. Drop it
   from the list offered for new addresses.
2. Tell the user whose address uses it — not silently, and not by deleting their readings. The
   honest message is that tariffs for this country are no longer published, so what they see is the
   last known figure and will not update.
3. Keep distinguishing this from a failed download. An index that did not arrive, arrived broken or
   arrived empty changes nothing; that rule stays exactly as it is.

## 3. Smaller things worth doing

* **Do not label a tariff stale by its date.** Ukrainian heat tariffs are frozen since 2021 by a
  wartime moratorium and are genuinely current. Show `decree_info` instead — it now carries the real
  decree number for every collected country.
* **Electricity is one rate per country**, which is wrong for Russia: the published figure is
  Moscow's. Fixing it needs a schema change (regional electricity) and is not started. Do not build
  UI that assumes a single national electricity price will stay meaningful.
* **A city may appear in `water` and not in `heating`**, or the other way round. Already handled —
  keep it that way when touching those screens.

---

## 4. What not to do

* Do not add a hardcoded tariff, norm or supplier name to the app. The app renders what the file
  says; every number in it is traceable to a document, and a value typed into the app breaks that.
* Do not compute a hot water price from components until the building's system is asked for. The
  fallback `rate` is more accurate than a guessed norm.
* Do not treat a missing block or a missing city as an error. It is the normal state: central hot
  water does not reach every town.
