# Kazakhstan Utility Tariffs Pipeline (`KZ`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/kz/README.md](../../ru/kz/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Kazakhstan (`country: "KZ"`, `currency: "KZT"`).

---

## Output Files

- `docs/tariffs_kz.json` — published JSON file for mobile application consumption.
- `assets/tariffs_kz_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Kazakhstan is collected by `src/common/ai_pipeline.py`; the sources are `config/kz/sources.json`.
Every tariff is approved by the regional department of the Committee for the Regulation of Natural
Monopolies and published by the supplier on its own site, so each city reads its own companies.
Households pay VAT (16% in 2026): where a page prints a "with VAT" column it is taken, and where it
prints only the net figure (Almaty Heat Networks) `vat_percent` adds the tax.

- **Water:** Astana Su Arnasy, Almaty Su, Vodnye Resursy-Marketing (Shymkent), Qaragandy Su and Aqtobe
  su-energy group. Aktobe lists every decision since 2022 as a PDF, oldest first, so its source uses
  `read_documents` with `from_end`.
- **Heating:** Almaty Heat Networks, Kuatzhyluortalyk-3 (Shymkent) and Teplotranzit Karaganda — the
  general household tariff per Gcal, not the metered or unmetered sub-tariffs.
- **Hot water:** Almaty Heat Networks, the metered price per m³ for the open system in the heating
  season.
- **Electricity:** Astana-REC, the first consumption tier for a flat without an electric stove.

Retired (`retired_cities`): **Astana heating and hot water**. There is no source — the tariff section of
Astana-Teplotranzit's site leads to a 404, and Astanaenergosbyt last updated its tariffs in January
2025 — and the published figures were invented, so the two entries were removed rather than left
standing. They come back under the same `city_code` if a source appears.

Known gaps, each reported on every run:
- **Almaty water** and **Shymkent heating**: the suppliers' own tariff pages still show only the
  January–March 2026 period. The published figures are those official ones; the pipeline refreshes
  them when the pages are updated.

---

## Configuration & Scripts

- Pipeline module: `src/countries/kz/fetcher.py`
- Configuration file: `config/kz/sources.json`
- City registry: `config/kz/city_registry.json`
