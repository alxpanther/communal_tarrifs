# Georgia Utility Tariffs Pipeline (`GE`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/ge/README.md](../../ru/ge/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Georgia (`country: "GE"`, `currency: "GEL"`).

---

## Output Files

- `docs/tariffs_ge.json` — published JSON file for mobile application consumption.
- `assets/tariffs_ge_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

1. **Electricity (`electricity`)**: Regulated by GNERC (Georgian National Energy and Water Supply Regulatory Commission).
   - Base Tier 1 tariff (up to 101 kWh/month): ~0.18041 GEL/kWh (*Telasi* in Tbilisi / *Energo-Pro Georgia*).
2. **Water Supply & Sewage (`water`)**: Regulated by GNERC.
   - Tbilisi (*Georgian Water and Power - GWP*): Water supply 0.50 GEL/m³, Sewage 0.103 GEL/m³, Total 0.603 GEL/m³ (metered).
3. **Hot Water & Heating (`hot_water`, `heating`)**: Georgia does not have centralized district heating for households; residents use individual heating systems. The city lists for these blocks remain empty (`[]`).

---

## Configuration & Scripts

- Pipeline module: `src/countries/ge/fetcher.py`
- Configuration file: `config/ge/sources.json`
- City registry: `config/ge/city_registry.json`
