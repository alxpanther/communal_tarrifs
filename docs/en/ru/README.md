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
  on pages updated in place. Mosvodokanal, Mosenergosbyt and mos.ru do not answer outside Russia.
  Moscow's hot water and heating are read from MOEK's tariff page, which links the current
  "Тарифное меню ПАО «МОЭК»" first: a table with five cells per year (two dates without VAT, the
  decree, two dates for households with VAT), which the hints spell out cell by cell because both
  models took the column without VAT. Hot water is read by `qwen3-max`: `qwen-plus` kept returning the
  price without VAT for October, which no check can catch, as it is a real and plausible number.
  Moscow's water came from the GARANT reference page "Prices, rates and tariffs for housing and
  utility services in Moscow" until October 2026, when GARANT cut the page down to a list of old
  decrees. **It is retired** (`moscow.water`): Mosvodokanal and mos.ru refuse connections from
  abroad, and what is left are news articles and third-party pages without a start date. Saint Petersburg is read from the household tariffs list of the
  city's Tariff Committee, which links this year's summary table first: water and sewerage (one
  price each), two-component hot water, heating, and electricity for the first consumption band of
  two plans, published in `electricity_cities`.
- **Astrakhan** (September 2026). Water and sewerage are read from the "Абонентам" page of
  МУП «Астрводоканал», which links one page per tariff period ("Тарифы с 01.01.2026", "Тарифы с
  01.10.2026"). Gas is read from the home page of ООО «Газпром межрегионгаз Астрахань», whose link
  "Подробнее о тарифах и нормативах на газ" leads to the prices in force: one price per thousand m³
  with delivery included, and the consumption norms of a flat without a meter in a building with
  central heating, published in `gas`. Heating and electricity (gas-stove and electric-stove plans,
  no consumption bands, in `electricity_cities`) are still read from the city summary of the
  "MoyZhKKh" portal (my-gkh.ru), which since September 2026 answers robots with a captcha, so they
  are not refreshed. The sites of the heat company (teploseti30.ru) and of the energy retailer
  (astsbyt.ru) answer 403 from GitHub too (checked in October 2026); the heat company's newer site
  ats.vdkenergo.ru prints no tariffs, and astteplo.ru belongs to another supplier, МУП
  «Коммунэнерго», and prices heating per m² of floor area in xlsx files rather than per Gcal. On my-gkh.ru the
  three-zone peak price falls from 14.23 to 8.50 from 1 October — likely a typo of the reprint. Hot
  water is not collected: no source prints the heating norm, so no price per m³ can be computed.
- **Krasnodar heating** (October 2026) is read from АО «Краснодартеплосеть»'s list of tariff orders
  (`read_documents` with the file-name fragment `na-te-i-gvs-na-20`, two newest), whose households
  table gives every period with its dates. tkuk.ru, read before, prints the decree date and no start
  date, so every reading was refused and the 2024 figure stayed published. The scan of the order
  does not show its own number legibly, so the caption is its title as read. **Krasnodar's water is
  retired** (`krasnodar.water`): tkuk.ru has the same problem, Rosvodokanal's own page answers 403
  from GitHub, and the published figure was from 2024.

---

## Configuration & Scripts

- Pipeline module: `src/countries/ru/fetcher.py`
- Configuration file: `config/ru/sources.json`
- City registry: `config/ru/city_registry.json`
