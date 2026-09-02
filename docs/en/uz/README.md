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

1. **Electricity (`electricity`)**: Regulated by the Cabinet of Ministers of the Republic of Uzbekistan / Ministry of Energy.
   - Base social consumption norm (up to 200 kWh/month): 450 UZS/kWh.
2. **Water Supply & Sewage (`water`)**: Regulated by Uzsuvtaminot JSC.
   - Tashkent (*Uzsuvtaminot JSC*): Water supply 1400 UZS/m³, Sewage 1000 UZS/m³, Total 2400 UZS/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Operated in Tashkent by Veolia Energy Tashkent.
   - Hot water rate: 10575.04 UZS/m³.
   - Heating rate: 105654 UZS/Gcal.

---

## Configuration & Scripts

- Pipeline module: `src/countries/uz/fetcher.py`
- Configuration file: `config/uz/sources.json`
- City registry: `config/uz/city_registry.json`
