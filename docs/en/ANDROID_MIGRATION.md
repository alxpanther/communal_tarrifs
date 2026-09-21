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
| A new edition is rejected only when it carries no rate at all; lost cities or services, electricity included, are no reason | `TariffCatalog.acceptsAsSuccessor()` |
| Meter types `hotWater`, `heating`, and — already — `waterHeating` | `lib/domain/enums/meter_type.dart` |
| `plans`, `electricity_cities`, hot water components and `heat_norms` are read | `lib/domain/tariffs/electricity_plans.dart`, `tariff_catalog.dart` |
| An address picks its electricity supplier, plan and hot water system (schema v14) | `house_edit_screen.dart`, `ElectricitySelection` |
| A plan becomes the tariff of a meter with seasons and limits, and the user is told | `PlanGridBuilder`, `plan_notes_dialog.dart` |
| Notices about a lost country, city, service, plan or norm and about a city's own tariff | `TariffNotice`, `TariffNoticeStore`, `TariffNoticeBanner` |

The multi-supplier city case is handled too: a city with two heat companies offers both, and the
plain city code belongs to neither.

**Sections 2, 2a, 2b and 2c were done in the app on 14.09.2026.** Where the file says too little:
`tier_basis` = `null` with limited bands — "only the part above the limit costs more", with a note
to check it against the bill; months no season covers (May for Ukrainian electric heating, as the
source page prints it) are charged by the season before and named to the user; bands without
limits and bands on a multi-zone meter — the first band; `monthly_charge` — a separate service with
a constant sum; a plan with no rows for a meter with that many zones puts in no rates.

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

**The published schema grew in September 2026, and only grew.** No field was renamed, removed or
re-typed, so the released app reads the file as before. Added: `electricity.plans`, the root block
`electricity_cities`, and on two-component hot water `component_water`, `component_energy`,
`heat_norm` and `heat_norms` (see [JSON_SPECIFICATION.md](JSON_SPECIFICATION.md), sections 2.2, 2.2a
and 2.4). Later that month the root block `gas` was added (section 2.6). Sections 2, 2c and 2d below
are the app work those fields make possible.

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
   `componentWater`, `componentEnergy`, `heatNorm`, all nullable with a default of `null`, and
   `heatNorms`, a list defaulting to empty. Nullable
   is not a style choice: the user's cached file has no such keys, and a non-null field crashes the
   app when it reads its own cache after an update.
2. **Leave `rate` alone.** It stays the published price and the fallback. `hasRates` keeps meaning
   `available && rate > 0`.
3. **Ask the building's hot water system.** The options are the combinations `heat_norms` can
   hold — `system` × `insulated_risers` × `towel_rails`; a `null` flag in a norm means it does not
   matter for that norm. A new field on the house, next to the supplier pickers
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

The fields are published. `heat_norms` is present only where the source prints the region's table
(Yekaterinburgenergo today); elsewhere the app has `heat_norm` alone and step 4 falls back to `rate`.

## 2c. Electricity: every tariff the source prints

Until September 2026 a country file carried one electricity price and derived zone prices from
coefficients. Now each block carries `plans`: every group of consumers the source prices — gas or
electric stove, rural, low-income, electric heating — with every printed price as a row (meter,
zone, hours, consumption band, season), plus a fixed monthly charge where there is one. And a city
whose region sets its own tariff — Russia's do — is published in `electricity_cities`.

`base_rate` and `zones` still hold the default plan's first band, so nothing breaks. What to build:

1. **DTOs for `plans`, `rates` and `electricity_cities`** — every new field nullable or defaulted,
   for the same cached-file reason as in section 2.
2. **Pick the tariff by the user's city.** Look the city up in `electricity_cities` first — by
   `city_name`, as services are related today — and fall back to `electricity`.
3. **Ask the user's group** when a block has more than one plan: a picker on the house next to the
   supplier pickers, stored as `plan_code`, defaulting to the plan with `is_default`.
4. **Bill by bands and seasons**, following section 4.1 of JSON_SPECIFICATION.md. Where
   `tier_basis` or the band limits are `null`, the file does not say enough to split consumption:
   ask the user, or bill by the first band and say so.
5. **Add `monthly_charge`** to the month's electricity sum where it is set.

A zone's `hours` may be empty — several sources print no hours for the half-peak or day zone — and
must not be parsed. A meter kind a source does not price carries the base rate in every zone and a
description ending in "(не применяется, ставка одна)"; the app may hide that meter kind for the
country.

## 2d. Gas: a new service

Not done in the app yet. The root block `gas` carries natural gas per city: the price of the gas, the
price of delivering it, every offer the source prints, and the consumption norms of a household
without a meter. Ukraine (33 cities, every supplier minfin lists, Naftogaz by default), Astrakhan,
Armenia (one national price of Gazprom Armenia, delivery included, no norms), Baku (annual bands
billed by part, a fixed monthly charge), Moldova (one national price of Energocom, delivery
included) and Belarus (one national price per regional gas company; a flat with gas heating has its
own plan with annual bands) are collected; in
every other country the block is present with no cities. The released app ignores the block. What
to build:

1. **DTOs for `gas`, its `plans`, `rates` and `norms`** — the Kotlin classes in JSON_SPECIFICATION.md,
   section 3, every field nullable or defaulted, for the cached-file reason in section 2.
2. **A gas meter type** in m³, and a gas supplier picker on the house next to the others, stored as
   the gas `city_code`. Relate it to the house's city by `city_name`, as the other services are; a
   city may have two entries — Ternopil has two network operators — and the user picks theirs.
3. **The offer.** When a city has more than one plan, ask which one — in Ukraine that is the
   supplier and the monthly or annual price — stored as `plan_code`, defaulting to `is_default`.
4. **Without a meter.** Ukraine's flats mostly have no gas meter, so this path is the main one there,
   not an edge case: ask what the gas is for (`norms[].usage`) and how many residents live there — or
   the heated area for a `per_m2` norm — and bill by the norm. A norm with `heating_season_only` is
   charged only during the heating season.
5. **Bill** as in JSON_SPECIFICATION.md, section 4.5: the plan's price plus `distribution_rate`, times
   the metered m³ or the norm. The user never enters the contracted capacity. Annual bands
   (`tier_period` = `"year"`) need the m³ consumed since the start of the year, from the meter
   readings the app already has.
6. **Losing gas.** A city or the whole block may disappear from a later file; handle it as section 2b
   does.

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

## 2b. A city or a service can disappear from a country

A country can also lose single entries. When nobody publishes a readable tariff for a city's service
any more — or the number once published turns out to have no source — the entry is removed from the
file (`retired_cities` in config) rather than left standing as a current tariff. On 13 September 2026
this removed Tashkent's hot water, heating in Samarkand and Bukhara, all three city services of
Dushanbe, Chișinău's hot water and Astana's heating and hot water.

**The released app rejects such a file.** `TariffCatalog.acceptsAsSuccessor()` refuses a new edition
when a block keeps fewer than half of its charging cities (`minimumSurvivingShare = 0.5`), so for
Uzbekistan, Tajikistan and Moldova every installed app stopped taking updates of the whole country —
their fresh water and electricity tariffs included — until this is changed. The maintainer accepted
that, on the condition that the change below is made when the app is reworked:

1. **A removal the publisher made on purpose is not a broken download.** The guard exists against a
   half-downloaded or damaged file; it must not block a well-formed edition that simply carries fewer
   entries. Keep rejecting a file that fails to parse, is empty, or has lost its electricity block;
   stop rejecting a complete file because a block got shorter.
2. **Tell the user, per entry.** When a city or a service the user relies on (a saved supplier for
   one of their addresses) is no longer in the file, say so in plain words: the tariff for that city
   and service has been removed and is no longer updated — most likely the tariff collection system
   stopped finding it at its source. Do not delete the user's readings.
3. **Keep what the user already has.** The last known tariff may stay visible, clearly marked as no
   longer updated, so a calculation does not silently switch to nothing.

This is the same idea as section 2a, one level down: section 2a handles a whole country leaving the
index, this section a single city or service leaving a country file.

## 3. Smaller things worth doing

* **Do not label a tariff stale by its date.** Ukrainian heat tariffs are frozen since 2021 by a
  wartime moratorium and are genuinely current. Show `decree_info` instead — it now carries the real
  decree number for every collected country.
* **The country-wide electricity block is a fallback, not the tariff of every city.** Russia's
  country block is Moscow's price; Saint Petersburg, Novosibirsk, Kazan, Chelyabinsk and Krasnodar are in
  `electricity_cities` (section 2c). A city in neither has no electricity tariff of its own in the
  file yet.
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
