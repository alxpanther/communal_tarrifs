# Uzbekistan Utility Tariffs Pipeline (`UZ`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/uz/README.md](../../ru/uz/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Uzbekistan (`country: "UZ"`, `currency: "UZS"`).

---

## Output Files

- `docs/tariffs_uz.json` — published JSON file for mobile application consumption.
- `assets/tariffs_uz_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Uzbekistan is collected by `src/common/ai_pipeline.py`; the sources are `config/uz/sources.json`.

- **Water:** the tariff page of the national water company Uzsuvtaminot is a script that loads its
  table from `api.uzsuv.uz`; that JSON, one address for all regions, is the source. Each city reads
  its regional company's `population` rate and `effective_date`. The figures are net of VAT — the
  company's own tariff sheets print them with 12% added (Samarkand 2 800 → 3 136) — so
  `vat_percent: 12` is set.
- **Heating, Tashkent:** Veolia Energy Tashkent's news feed (a Tilda JSON feed) is read with
  `read_documents`, which follows the tariff announcements in it; the household rate per Gcal is net
  of VAT, which the code adds.
- **Electricity:** the tariff calculator of Regional Electric Networks, which prints the current
  household scale; the first tier, up to 200 kWh, is published.

Retired (`retired_cities`), because the published figures were invented and no source exists: Tashkent
hot water (Veolia publishes the price per m³ only in a Google Drive table whose text has no row
labels) and heating in Samarkand and Bukhara (no official page of their heat suppliers was found). Removing an entry makes the released app reject the country's new file until the app is changed (see ANDROID_MIGRATION.md, section 2b).

---

## Configuration & Scripts

- Pipeline module: `src/countries/uz/fetcher.py`
- Configuration file: `config/uz/sources.json`
- City registry: `config/uz/city_registry.json`
