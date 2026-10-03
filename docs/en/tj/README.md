# Tajikistan Utility Tariffs Pipeline (`TJ`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/tj/README.md](../../ru/tj/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Tajikistan (`country: "TJ"`, `currency: "TJS"`).

---

## Output Files

- `docs/tariffs_tj.json` — published JSON file for mobile application consumption.
- `assets/tariffs_tj_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Tajikistan is collected by `src/common/ai_pipeline.py`; the sources are `config/tj/sources.json`.
Only electricity is collected so far.

- **Electricity** is set by a decision of the Government of Tajikistan and published by the ministry
  of energy — as a scanned PDF with no text layer, linked from the ministry's stable tariff page.
  The source is therefore that page with `read_documents` set to «О тарифах», so only the tariff
  decision goes to the model, not the tariff methodology linked next to it (see ARCHITECTURE.md,
  section 8a). Until October 2026 the page carried the scan as images and was read with
  `read_images`. The table lists a dozen consumer groups; the published rate is
  the row "Для населения", in dirams per kWh, which the code divides into somoni. The decision's own
  note says the tariffs are net of VAT for every group **except** households, so the household
  figure is final.
- **Water, hot water and heating** of Dushanbe are retired (`retired_cities`). Their tariffs are
  approved by the Antimonopoly Service and reported in the state press, which is not a source (a dated
  article; see ARCHITECTURE.md, section 8a). The water utility's own site is closed for maintenance,
  and the city hall's tariff page covers housing-fund maintenance and waste removal. The figures once
  published there came from the era when the country was entered by hand and were wrong, so the
  entries were removed; the file now carries electricity only. Removing an entry makes the released app reject the country's new file until the app is changed (see ANDROID_MIGRATION.md, section 2b).

---

## Configuration & Scripts

- Pipeline module: `src/countries/tj/fetcher.py`
- Configuration file: `config/tj/sources.json`
- City registry: `config/tj/city_registry.json`
