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

1. **Electricity (`electricity`)**: Regulated by the Department for Regulation of the Fuel and Energy Complex under the Ministry of Energy of KR.
   - Social norm rate (up to 700 kWh/month): 1.11 KGS/kWh.
2. **Water Supply & Sewage (`water`)**: Regulated by the Bishkek City Council.
   - Bishkek (*PEU "Bishkekvodokanal"*): Water supply 10.45 KGS/m³, Sewage 3.45 KGS/m³, Total 13.90 KGS/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Regulated by the Ministry of Energy of KR.
   - Bishkek (*OJSC "Bishkekteplotset"*): Hot water 85.00 KGS/m³, Heating 1540.00 KGS/Gcal (subsidized rate).

---

## Configuration & Scripts

- Pipeline module: `src/countries/kg/fetcher.py`
- Configuration file: `config/kg/sources.json`
- City registry: `config/kg/city_registry.json`
