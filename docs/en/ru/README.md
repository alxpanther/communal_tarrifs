# Russia Utility Tariffs Pipeline (`RU`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/ru/README.md](../../ru/ru/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Russia (`country: "RU"`, `currency: "RUB"`).

---

## Output Files

- `docs/tariffs_ru.json` — published JSON file for mobile application consumption.
- `assets/tariffs_ru_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Russia is collected city by city by `src/common/ai_pipeline.py`. There are no tariff figures in this
file on purpose: every number is read from the city's sources on the run that publishes it, and the
published JSON is the only place to look them up.

- **Water, hot water, heating** are set by the tariff authority of each region, so every city has
  its own sources. Which cities are collected, and from where, is `cities` in
  `config/ru/sources.json`; a city or service with no usable source is listed in `retired_cities`.
- **Electricity** is one value for the whole country today, read for the city of Moscow. Tariffs
  differ by region, so this figure is wrong elsewhere; regional electricity needs a schema change
  and is not done yet.
- **A source is a page that is updated in place**: a supplier's or settlement centre's tariff page
  that will carry next year's figures at the same address. Moscow and Saint Petersburg are retired
  because the only sources that could be read from GitHub for them were documents fixed to a year
  (a 2026 tariff menu, a 2026 PDF) and a dated article.

---

## Configuration & Scripts

- Pipeline module: `src/countries/ru/fetcher.py`
- Configuration file: `config/ru/sources.json`
- City registry: `config/ru/city_registry.json`
