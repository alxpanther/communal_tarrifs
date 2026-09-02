# Turkmenistan Utility Tariffs Pipeline (`TM`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/tm/README.md](../../ru/tm/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Turkmenistan (`country: "TM"`, `currency: "TMT"`).

---

## Output Files

- `docs/tariffs_tm.json` — published JSON file for mobile application consumption.
- `assets/tariffs_tm_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

1. **Electricity (`electricity`)**: Regulated by the Ministry of Energy of Turkmenistan.
   - Base state residential tariff: 0.025 TMT/kWh.
2. **Water Supply & Sewage (`water`)**: Regulated by the Ministry of Municipal Economy / Ashgabat City Hyakimlik.
   - Ashgabat (*PO "Ashgabatvodokanal"*): Water supply 0.50 TMT/m³, Sewage 0.20 TMT/m³, Total 0.70 TMT/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Regulated by the Ministry of Municipal Economy.
   - Ashgabat (*PO "Ashgabat-teplo"*): Hot water 0.30 TMT/m³, Heating 5.00 TMT/Gcal.

---

## Configuration & Scripts

- Pipeline module: `src/countries/tm/fetcher.py`
- Configuration file: `config/tm/sources.json`
- City registry: `config/tm/city_registry.json`
