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
- **Electricity** is set by each region. The country block is read for the city of Moscow and is
  only a fallback; Novosibirsk (Novosibirskenergosbyt's page), Kazan (Tatenergosbyt's page),
  Chelyabinsk (the ministry's decree linked by Uralenergosbyt) and Krasnodar (the department's order
  linked by NESK) are published in `electricity_cities` with gas-stove, electric-stove and rural
  plans, three consumption bands and zone prices. Krasnodar's band limits depend on the building type
  and the heating season and were misread, so only band numbers are published there. Yekaterinburg,
  Nizhny Novgorod and Samara have no electricity source yet: EnergosbyT Plus and TNS energo do not
  answer outside Russia, and Samaraenergo's decree is a scan behind a page per year.
- **A source is a page that is updated in place**: a supplier's or settlement centre's tariff page
  that will carry next year's figures at the same address. Moscow and Saint Petersburg were retired
  while their only readable sources were documents fixed to a year, and came back in September 2026
  on pages updated in place. The Moscow utilities' own sites (Mosvodokanal, MOEK, Mosenergosbyt,
  mos.ru) do not answer outside Russia, so Moscow's water, hot water and heating are read from the
  GARANT reference page "Prices, rates and tariffs for housing and utility services in Moscow",
  which names no decree numbers. Saint Petersburg is read from the household tariffs list of the
  city's Tariff Committee, which links this year's summary table first: water and sewerage (one
  price each), two-component hot water, heating, and electricity for the first consumption band of
  two plans, published in `electricity_cities`.
- **Astrakhan** (September 2026) is read from the city summary of the "MoyZhKKh" portal
  (my-gkh.ru), which reprints the decrees of the Astrakhan Region Tariff Service with their numbers:
  water and sewerage, heating, and electricity for the gas-stove and electric-stove plans without
  consumption bands, published in `electricity_cities`. The page is a reprint, not the regulator,
  so a typo there reaches the file: its three-zone peak price falls from 14.23 to 8.50 from
  1 October, which is worth checking once that period starts. Hot water is not collected: the page
  prints the two components but no heating norm, so no price per m³ can be computed.

---

## Configuration & Scripts

- Pipeline module: `src/countries/ru/fetcher.py`
- Configuration file: `config/ru/sources.json`
- City registry: `config/ru/city_registry.json`
