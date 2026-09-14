# Azerbaijan Utility Tariffs Pipeline (`AZ`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/az/README.md](../../ru/az/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Azerbaijan (`country: "AZ"`, `currency: "AZN"`).

---

## Output Files

- `docs/tariffs_az.json` — published JSON file for mobile application consumption.
- `assets/tariffs_az_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Azerbaijan is collected by `src/common/ai_pipeline.py`; the sources are `config/az/sources.json`.
There are no tariff figures in this file on purpose. Every tariff is set centrally by the Tariff
(Price) Council, so Baku is the only entry and its numbers hold country-wide.

- **Electricity** comes from the tariff tables of the energy regulator (AERA), which republishes the
  Council's decision as a table. Households pay by three bands of monthly consumption, and the table
  says each price is "for the part" of the month's consumption, so `tier_basis` is `"part"`; there is
  also a fixed 1 manat a month (`monthly_charge`). Prices are printed in qəpik and divided by the
  code. `base_rate` is the first band, up to 200 kWh. Households have no day/night tariff, so both
  zone meters carry the base rate.
- **Heating and hot water** come from Azeristiliktechizat's own tariff page, which carries two
  tables: central heating by the gigacalorie and by the square metre, and hot water by the cubic
  metre per operating district and boiler house. Only the per-gigacalorie heating rate fits the
  schema — a meter reads gigacalories — so the monthly per-square-metre tariff for buildings without
  a meter is deliberately not published. The regulator's page is read alongside it for the decree
  that sets the current heating rate.
- **Water and sewage** come from the Tariff Council's water section: the page lists the decisions in
  force, and the current tariff table hangs off it as a PDF, which the pipeline reads as a table.
  Azersu's own tariff page is useless from outside Azerbaijan — it serves a parked hosting
  certificate to everyone else, GitHub runners included, which is why the regulator's copy is used
  instead. The PDF is addressed by an opaque id with no date in it; when the Council replaces the
  file the link breaks and the run reports that the source did not open, which is a loud failure
  rather than a page that has quietly stopped being current.

---

## Configuration & Scripts

- Pipeline module: `src/countries/az/fetcher.py`
- Configuration file: `config/az/sources.json`
- City registry: `config/az/city_registry.json`
