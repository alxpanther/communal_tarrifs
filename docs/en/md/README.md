# Moldova Utility Tariffs Pipeline (`MD`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/md/README.md](../../ru/md/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Moldova (`country: "MD"`, `currency: "MDL"`).

---

## Output Files

- `docs/tariffs_md.json` — published JSON file for mobile application consumption.
- `assets/tariffs_md_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Moldova is collected city by city by `src/common/ai_pipeline.py`; the sources are
`config/md/sources.json`. There are no tariff figures in this file on purpose.

Every tariff is set by ANRE, the national energy regulator, and **household utilities are exempt
from VAT in Moldova** — so the figures ANRE prints "fără TVA" are exactly what a household pays, and
no tax is added anywhere in the pipeline.

- **Electricity** comes from ANRE's "tariffs in force" table: the universal service price of
  Î.C.S. „Premier Energy” S.R.L. at low voltage, which is what a flat is connected to. The table
  prints bani per kWh, so the model converts to lei. Since April 2026 Moldova also has prices
  differentiated by hour, and the same table carries them; the published zone rates still come from
  the coefficients in config, which is a known compromise — the day and night prices are separate
  regulated numbers, not ratios of the single one.
- **Heating** comes from the same kind of ANRE table, one row per licence holder: Termoelectrica for
  Chișinău, CET-Nord for Bălți, both per gigacalorie.
- **Water and sewage** come from each utility's own page, not from ANRE's consolidated water table:
  that table prints the figures of every operator in the country but neither the date they took
  effect nor the decision behind them, and the schema needs both. Bălți charges water and sewerage as
  one figure, so its `sewage` is published as zero and `zero_allowed` in config says that is the
  truth rather than a misread cell.
- **Hot water** for Chișinău has no readable source. Termoelectrica publishes the price of a cubic
  metre only in PDFs named by date, which are not sources (see ARCHITECTURE.md, section 8a), so the
  entry keeps its previous value and every run reports it as not refreshed.
- **Cahul, Ungheni and Soroca** are retired from the water block. Their current figures exist on
  ANRE's consolidated table, but nothing published anywhere gives them together with a date and a
  decision, and an entry nobody can refresh is worse than no entry.

---

## Configuration & Scripts

- Pipeline module: `src/countries/md/fetcher.py`
- Configuration file: `config/md/sources.json`
- City registry: `config/md/city_registry.json`
