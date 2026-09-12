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
  of the registry reads the same two documents: the PSRC decision that sets the tariff, and the
  utility's own FAQ page, which repeats the figures. The decision carries the dates and the decree;
  the FAQ is the check. When the two disagree the model must return nothing, which is what makes a
  new PSRC decision visible instead of silently stale: it arrives as a "tariff not found" alert.
- **Hot water and heating** do not exist for Armenian households — there is no district heating —
  so both blocks stay empty by design.

---

## Configuration & Scripts

- Pipeline module: `src/countries/am/fetcher.py`
- Configuration file: `config/am/sources.json`
- City registry: `config/am/city_registry.json`
