# Belarus Utility Tariffs Pipeline (`BY`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/by/README.md](../../ru/by/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Belarus (`country: "BY"`, `currency: "BYN"`).

---

## Output Files

- `docs/tariffs_by.json` — published JSON file for mobile application consumption.
- `assets/tariffs_by_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Belarus is collected by `src/common/ai_pipeline.py`; the sources are `config/by/sources.json`.
Six cities: Minsk and the five oblast centres.

- **Water** tariffs for households are fixed by each oblast executive committee (Minsk by the city
  one) and read from the city's own водоканал page. Every водоканал prints them there as a table,
  except Gomel, which attaches a PDF — that source uses `read_documents` with a filter, since the
  same page links two dozen unrelated PDFs. The subsidised column is the one households pay; the
  "full cost recovery" column is not.
- **Heating and hot water** share one tariff per Gcal set by the Council of Ministers for the whole
  republic, with a second period from 1 June. It is read from the page for individuals of Belenergo,
  the national energy association, which attaches the decision as a PDF (`read_documents`). That
  document names no supplier, so each city's heat supplier is the name declared in config. Hot water
  is billed as the heat used to warm it, so its unit is `Gcal` (see ARCHITECTURE.md, section 8a).
- **Electricity** comes from the same Belenergo page: the subsidised single-rate tariff for an
  ordinary flat (item 5, a gas stove), not the electric-stove tariff and not the full-cost one. The
  two- and three-period tariffs are the official 0.7 / 2.0 and 0.6 / 0.7 / 1.8 multiples of it.
- Household utilities in Belarus are VAT-exempt, so every printed figure is final.

The "other cities (republic tariff)" entry was retired: water tariffs differ by oblast, so a single
republic figure never existed. Four heat suppliers entered by hand were invented or mangled names
and were replaced in the registry by the real companies, with every `city_code` kept.

---

## Configuration & Scripts

- Pipeline module: `src/countries/by/fetcher.py`
- Configuration file: `config/by/sources.json`
- City registry: `config/by/city_registry.json`
