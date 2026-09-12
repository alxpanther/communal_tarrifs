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
  Council's decision as a table. It is tiered by monthly consumption; the published rate is the
  first tier — up to 200 kWh a month, VAT included — and the table prints it in qəpik, so the model
  converts to manat. Households have no day/night tariff, hence the zone coefficients of 1.0.
- **Heating and hot water** come from Azeristiliktechizat's own tariff page, which carries two
  tables: central heating by the gigacalorie and by the square metre, and hot water by the cubic
  metre per operating district and boiler house. Only the per-gigacalorie heating rate fits the
  schema — a meter reads gigacalories — so the monthly per-square-metre tariff for buildings without
  a meter is deliberately not published. The regulator's page is read alongside it for the decree
  that sets the current heating rate.
- **Water and sewage** have no readable source. Azersu's own tariff page answers from Azerbaijan
  but serves a parked hosting certificate to everyone else, including GitHub runners, and the Tariff
  Council publishes its water decisions only as dated PDFs. The block therefore keeps the value of
  the Council's decision of 30.01.2021, which is still the current one, and every run reports water
  as not refreshed. That alert is the reminder that a source is missing — do not silence it by
  writing the rate into config.

---

## Configuration & Scripts

- Pipeline module: `src/countries/az/fetcher.py`
- Configuration file: `config/az/sources.json`
- City registry: `config/az/city_registry.json`
