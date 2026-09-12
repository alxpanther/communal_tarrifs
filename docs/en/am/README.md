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
  table by Electric Networks of Armenia. The table is tiered by monthly consumption; the published
  rate is the one an ordinary flat pays — up to 200 kWh a month, daytime, VAT included. The night
  rate of a two-zone meter is currently derived from a coefficient in config, which is a known
  compromise: in Armenia the night tariff is a separate regulated number, 10 dram below the day one,
  not a ratio of it. It goes away when electricity is reworked (see ANDROID_MIGRATION.md).
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
