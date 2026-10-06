# Task: price of electricity a household exports to the grid (`grid_export`)

Written 2026-10-06 from the app project (KomMeter) for an agent working in this repository. The
maintainer has agreed to a **new root block** in the country file; it is additive — no existing
field is renamed, removed or re-typed. Read `CLAUDE.md` and the documents it lists first: every
hard rule there applies, above all **"a tariff is collected, never typed in"**.

## Why the app needs it

The app is getting an address switch "I export energy to the grid" for households with a solar
station and a two-way meter. In the first release it supports two settlement schemes:

1. **Monthly surplus is sold** — for the month, exported minus imported; a positive difference is
   paid at a fixed price per kWh, a negative one is billed at the ordinary tariff.
2. **The user types the amount in** — the price changes every hour (net billing), the app cannot
   compute it and needs nothing from this repository.

Scheme 1 needs the **price per exported kWh**. The app shows it to the user and lets them type
their own. This task makes the price arrive with the country file, so it is filled in and updated
by itself, like every other tariff.

## Countries in this task

### Ukraine (`ua`) — household "green" tariff

- Set by the regulator NKREKP for the whole country: it does **not** depend on the city or any
  supplier. It is one country-wide table, the same way `electricity` is one country-wide block.
- The rate depends on the **type of station** (ground-mounted solar up to 30 kW; solar on roofs
  and facades up to 50 kW; wind; combined wind and solar) and on the **period the station was put
  into operation**. Each row also has a **period of validity** (currently up to 2029-12-31).
- Rates are printed **without VAT**, in kopecks per kWh. Publish them in hryvnias per kWh (the unit
  `electricity` uses) — convert, do not copy kopecks.
- The rate is pegged to the euro and NKREKP re-issues the resolution several times a year. The
  latest seen by the app project is resolution No. 498 of 2026-03-31, the 16th edition:
  https://www.nerc.gov.ua/acts/pro-vstanovlennya-zelenih-tarifiv-na-elektrichnu-energiyu-viroblenu-generuyuchimi-ustanovkami-privatnih-domogospodarstv-16
  This page is tied to one edition and **must not be the source** (CLAUDE.md, "Running it"). Find a
  page updated in place that prints the current table, prove it with `src/check_sources.py`, and
  report what you chose. Candidates seen, not verified: pages "«Зелені» тарифи" of universal service
  suppliers, e.g. https://www.ez.rv.ua/zeleni-taryfy-na-elektrychnu-energiyu-vyroblenu-generuyuchymy-ustanovkamy-pryvatnyh-domogospodarstv/ ,
  https://www.kresc.com.ua/green-tariffs.shtml , https://koec.com.ua/page?id=11&root=3 , and the
  NKREKP site itself.
- Tax on the income: 18 % personal income tax plus 5 % military levy, withheld by the supplier
  (23 % in total). Publish it only if a source prints it and the pipeline reads it; otherwise leave
  the field empty as described below — the app lets the user enter it.

### Uzbekistan (`uz`) — "Solar house" programme

- Households with a solar station up to 50 kW, since 2023-04-01. For the monthly surplus over own
  consumption the state pays **1000 UZS per kWh** (as of 2026-10). A draft decree to lower it from
  2026 was under public discussion — this is exactly why the number must be read from a source
  and not typed.
- One rate for the whole country; no station types or commissioning periods known.
- Find a source updated in place (lex.uz consolidated text, the Ministry of Energy, the tax
  service). If there is no readable source, publish the block empty and report it — do not type
  1000 into config.

### Every other country

Not in this task. Armenia, Georgia, Moldova, Russia, Kazakhstan, Kyrgyzstan, Tajikistan use other
schemes (kWh netting over a year, separate sale at a market price) that the app will support later.
Belarus does not let households sell at all; Azerbaijan has only drafts. Their files get the block
**empty** (see below), the same way `gas` is present everywhere with an empty `cities`.

## Proposed block

Name and shape are a proposal; if the existing conventions of this repository suggest something
better, propose it to the maintainer before writing code (CLAUDE.md, "Ask before changing the
output JSON schema").

```json
"grid_export": {
  "source_url": "https://...",
  "update_date": "2026-10-06",
  "scheme": "monthly_surplus",
  "unit": "kWh",
  "decree_info": "Постанова НКРЕКП № 498 від 31.03.2026",
  "income_tax_percent": 23.0,
  "income_tax_info": "ПДФО 18 % + військовий збір 5 %",
  "rates": [
    {
      "station_type": "solar_ground",
      "max_capacity_kw": 30,
      "commissioned_from": "2025-01-01",
      "commissioned_to": "2025-12-31",
      "rate": 6.6944,
      "vat_included": false,
      "valid_from": "2026-01-01",
      "valid_to": "2029-12-31"
    }
  ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `source_url` | `String` | The page the block is read from; empty when the block is empty. |
| `update_date` | `String` | Date the block was last refreshed, `YYYY-MM-DD`. |
| `scheme` | `String` | `"monthly_surplus"` for both countries of this task; empty when the block is empty. Other values will come with other countries. |
| `unit` | `String` | Always `"kWh"`. |
| `decree_info` | `String` | The act the rates rest on, as printed. |
| `income_tax_percent` | `Double` | Tax withheld from the income, percent; `0.0` when not collected. |
| `income_tax_info` | `String` | What the percent is made of; **empty means "not collected"** and the app then asks the user. |
| `rates` | `Array<Object>` | One row per station type and commissioning period; empty when nothing is collected. |
| `rates[].station_type` | `String` | `solar_ground`, `solar_roof`, `wind`, `wind_solar`; `solar` where the country does not split by type (Uzbekistan). |
| `rates[].max_capacity_kw` | `Double` | Capacity limit of the row, kW. |
| `rates[].commissioned_from` / `commissioned_to` | `String` | Commissioning period the row applies to; `commissioned_to` empty when open-ended. |
| `rates[].rate` | `Double` | Price of 1 exported kWh in the country currency. |
| `rates[].vat_included` | `Boolean` | Whether `rate` includes VAT, as printed. |
| `rates[].valid_from` / `valid_to` | `String` | Period the rate is valid; `valid_to` empty when open-ended. |

**Empty block** (every country outside this task, and a country whose source failed for the first
time): `source_url` `""`, `scheme` `""`, `income_tax_percent` `0.0`, `income_tax_info` `""`,
`rates` `[]`. A later failure keeps the previously published block (CLAUDE.md, "A failure must never
wipe good data").

## What to change in this repository

1. `config/ua/sources.json` and `config/uz/sources.json` — the source of the new block (URLs and
   limits only, no rates).
2. Ukraine: collect the table in the aggregated pipeline (`src/countries/ua/fetcher.py`) or a shared
   module in `src/common/` if it is generic. Uzbekistan: the per-city pipeline is per city and this
   price is country-wide — decide with the maintainer where a country-wide block of a per-city
   country is read; do not copy logic between fetchers.
3. Validation: reject a table with no rows, a non-positive rate, overlapping periods of the same
   station type, and a rate that moved by more than a sane share since the last run (alert, keep the
   previous block).
4. Write the empty block into every other country file.
5. Documentation, both `docs/en/` and `docs/ru/`: `JSON_SPECIFICATION.md` (new section for the
   block, the Kotlin data class, the compatibility note), `ANDROID_MIGRATION.md` (what the app must
   read), `ARCHITECTURE.md` / `PROJECT_STRUCTURE.md` where the new collection lives.
6. Test with `src/run_city.py` / the smallest run that touches the new block, show the result to the
   maintainer, and collect the countries only with their agreement (a model call is paid for).

## Done when

- `docs/tariffs_ua.json` carries a filled `grid_export` read from a page updated in place; the
  numbers match the current NKREKP resolution for at least the solar rows.
- `docs/tariffs_uz.json` carries either a filled block from a real source or an empty block plus a
  report to the maintainer why.
- Every other country file carries the empty block.
- Both language versions of the documentation describe the block.
- This file is deleted from `docs/en/` and `docs/ru/` once the work is merged — it is a task, not
  documentation.
