# Kyrgyzstan Utility Tariffs Pipeline (`KG`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/kg/README.md](../../ru/kg/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Kyrgyzstan (`country: "KG"`, `currency: "KGS"`).

---

## Output Files

- `docs/tariffs_kg.json` — published JSON file for mobile application consumption.
- `assets/tariffs_kg_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

Kyrgyzstan is collected by `src/common/ai_pipeline.py`; the sources are `config/kg/sources.json`.
Only Bishkek is in the file.

- **Electricity** is set by orders of the Department for Regulation of the Fuel and Energy Complex,
  listed on its page for end-consumer tariffs, each attached as a PDF (`read_documents`); the model
  picks the order in force. `base_rate` is households consuming up to 700 kWh a month; `plans` also
  carries the band above 700 kWh, highland areas, low-income families and unlimited consumption.
- **Heating and hot water** come from Bishkekteploset's tariff page. Its newest entry holds the
  table as an image pasted into the page (`read_images`). Heating is the household rate within the
  80 m² social norm, per Gcal; hot water is the metered price per m³.
- The orders print tariffs "excluding taxes", which is nonetheless what households pay.
- **Water** tariffs are approved by the Bishkek city council. The source is the council's list of
  resolutions of the current convocation, from which `read_documents` with a text filter follows the
  resolutions on water tariffs — each is a page of its own. The model takes the newest one in force;
  it takes effect on publication, so the date is the page's "Опубликовано". The водоканал's own
  tariff section is empty and the city hall's service page has not changed since 2015, so neither is
  used. The list's address holds the convocation number (29th, until the 2028 elections) and will
  need changing once, when the next convocation's list opens.

---

## Configuration & Scripts

- Pipeline module: `src/countries/kg/fetcher.py`
- Configuration file: `config/kg/sources.json`
- City registry: `config/kg/city_registry.json`
