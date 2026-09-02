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

1. **Electricity (`electricity`)**: Regulated by the Antimonopoly Service and the Government of the Republic of Tajikistan.
   - Base residential tariff: 0.3075 TJS/kWh (*OAO "Shabakahoi taksimoti bark"*).
2. **Water Supply & Sewage (`water`)**: Regulated by the Executive Authority of Dushanbe City.
   - Dushanbe (*SUE "Obi Dushanbe"*): Water supply 1.80 TJS/m³, Sewage 0.70 TJS/m³, Total 2.50 TJS/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Operated by Dushanbe District Heating Network.
   - Hot water: 15.00 TJS/m³.
   - Heating: 45.00 TJS/Gcal.

---

## Configuration & Scripts

- Pipeline module: `src/countries/tj/fetcher.py`
- Configuration file: `config/tj/sources.json`
- City registry: `config/tj/city_registry.json`
