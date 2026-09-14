# Armenia Utility Tariffs Pipeline (`AM`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/am/README.md](../../ru/am/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Armenia (`country: "AM"`, `currency: "AMD"`).

---

## Output Files

- `docs/tariffs_am.json` — published JSON file for mobile application consumption.
- `assets/tariffs_am_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Armenia is collected by `src/common/ai_pipeline.py`; the sources are `config/am/sources.json`.
There are no tariff figures in this file on purpose — every number is read from the source on the
run that publishes it.

- **Electricity** is set by the Public Services Regulatory Commission (PSRC) and published as a
  table by Electric Networks of Armenia. Every price is published in `plans`: residents on 0.38 kV
  in three bands of monthly consumption (up to 200, 201–400, above 400 kWh), each with a day and a
  night price, and socially vulnerable families. The table prints no single-rate price, so
  `base_rate` is the day price of the first band, and the night price is read, not derived. The
  page does not say whether a band applies to the whole month or to its part, so `tier_basis` is
  `null`, and it prints no zone hours.
- **Water and sewage** are one tariff for the whole country, provided by Veolia Jur, so every city
  of the registry reads the same document: the PSRC decision that sets the tariff, published by the
  ARLIS legal database. The utility's own FAQ page carries the same figures and was meant to be the
  cross-check, but it answers 403 to a GitHub runner, so it is not in the source list — a source
  that always fails where the pipeline runs is noise, not redundancy.
  PSRC replaces that decision every November, and a per-decision page cannot report that by itself.
  The guard is the database: ARLIS marks a repealed act as `ուժը կորցրած`, and the instruction tells
  the model to return nothing when it sees that. The tariff then stops being refreshed and the run
  says so, instead of quietly publishing last year's number for another twelve months.
- **Hot water and heating** do not exist for Armenian households — there is no district heating —
  so both blocks stay empty by design.

---

## Configuration & Scripts

- Pipeline module: `src/countries/am/fetcher.py`
- Configuration file: `config/am/sources.json`
- City registry: `config/am/city_registry.json`
