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
Only electricity is collected so far, and only Dushanbe is in the file.

- **Electricity** is set by a decision of the Government of Tajikistan and published by the ministry
  of energy — as a photograph of the decision's pages, not as text. The source is therefore the
  ministry's stable tariff page with `read_images` set, so the scan itself goes to the vision model
  (see ARCHITECTURE.md, section 8a). The table lists a dozen consumer groups; the published rate is
  the row "Для населения", in dirams per kWh, which the model converts to somoni. The decision's own
  note says the tariffs are net of VAT for every group **except** households, so the household
  figure is final.
- **Water, hot water and heating** have no readable source. Their tariffs are approved by the
  Antimonopoly Service and reported in the state press, which is not a source (a dated article; see
  ARCHITECTURE.md, section 8a). The water utility's own site serves a certificate that is expired
  and too weak for Python to accept — not something `config/certs/` can fix, because the problem is
  the site's own certificate rather than a missing intermediate. The city hall publishes a tariff
  page, but it covers housing-fund maintenance and waste removal, priced per square metre and per
  resident, which is not what these blocks hold. All three keep their previous values and every run
  reports them as not refreshed.

The figures still published for those three blocks came from the era when the country was entered by
hand, and they are wrong: the water tariff of Dushanbe has since been reported as 1.50 somoni per m³
plus 0.76 for sewerage. They are left alone rather than typed in, because a number nobody can
refresh is the thing this repository exists to avoid — but that also means they should not be
trusted until a source appears.

---

## Configuration & Scripts

- Pipeline module: `src/countries/tj/fetcher.py`
- Configuration file: `config/tj/sources.json`
- City registry: `config/tj/city_registry.json`
