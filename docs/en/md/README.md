# Moldova Utility Tariffs Pipeline (`MD`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/md/README.md](../../ru/md/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Moldova (`country: "MD"`, `currency: "MDL"`).

---

## Output Files

- `docs/tariffs_md.json` — published JSON file for mobile application consumption.
- `assets/tariffs_md_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

1. **Electricity (`electricity`)**: Regulated by ANRE (National Agency for Energy Regulation).
   - Single-zone base rate: ~2.39 MDL/kWh (*Premier Energy*, central/southern region) / 2.84 MDL/kWh (*FEE Nord*, northern region).
2. **Water Supply & Sewage (`water`)**: Regulated by ANRE.
   - Chișinău (*SA "Apă-Canal Chișinău"*): Water supply 10.79 MDL/m³, Sewage 4.18 MDL/m³, Total 14.97 MDL/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Regulated by ANRE.
   - Chișinău (*SA "Termoelectrica"*): ~2138 MDL/Gcal.
   - Bălți (*SA "CET-Nord"*): ~2110 MDL/Gcal.

---

## Configuration & Scripts

- Pipeline module: `src/countries/md/fetcher.py`
- Configuration file: `config/md/sources.json`
- City registry: `config/md/city_registry.json`
