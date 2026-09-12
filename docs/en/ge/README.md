# Georgia Utility Tariffs Pipeline (`GE`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/ge/README.md](../../ru/ge/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Georgia (`country: "GE"`, `currency: "GEL"`).

---

## Output Files

- `docs/tariffs_ge.json` — published JSON file for mobile application consumption.
- `assets/tariffs_ge_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Georgia is collected by `src/common/ai_pipeline.py`; the sources are `config/ge/sources.json`. There
are no tariff figures in this file on purpose. Both sources are pages of the same regulator — GNERC,
which sets electricity, gas and water tariffs alike.

- **Electricity** comes from GNERC's end user tariff table, from the rows of TELMICO, the supplier
  serving Tbilisi. Household tariffs are tiered by monthly consumption, and the published rate is the
  first tier — up to 101 kWh. The table prints tetri per kWh and says "including VAT", so the model
  only converts to lari. Households have no day/night tariff, hence the zone coefficients of 1.0.
- **Water and sewage** come from GNERC's water supply page, from the metered household tariffs of
  Georgian Water and Power, which serves Tbilisi. Two details matter there: the row named
  "Water supply" is the sum of the other two, so the drinking water and wastewater rows are the ones
  read; and the table prints its figures **excluding VAT**, unlike the electricity one next door.
  `vat_percent: 18` in config makes the pipeline add the tax, which keeps the arithmetic out of the
  model's hands.
- **Hot water and heating** do not exist for Georgian households — there is no district heating — so
  both blocks stay empty by design.

GNERC's own site sends its certificate without the intermediate that links it to a trusted root, so
`config/certs/` carries that intermediate; without it the whole country fails to download. The water
utility's own site, `gwp.ge`, does not answer from outside Georgia at all, which is why the
regulator's copy is used for water as well.

---

## Configuration & Scripts

- Pipeline module: `src/countries/ge/fetcher.py`
- Configuration file: `config/ge/sources.json`
- City registry: `config/ge/city_registry.json`
