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

1. **Electricity (`electricity`)**: Regulated by CREM MNE RK (Committee for Regulation of Natural Monopolies).
   - Base single-zone rate: ~25.50 KZT/kWh (*Astana-Energosbyt* / *AlmatyEnergosbyt*).
2. **Water Supply & Sewage (`water`)**: Regulated by CREM MNE RK per region.
   - Astana (*Astana Su Arnasy*): Water supply 58.14 KZT/m³, Sewage 48.28 KZT/m³, Total 106.42 KZT/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Regulated by regional CREM branches.
   - Astana (*Astana-Teplotransit JSC*): Hot water ~300 KZT/m³, Heating ~3055 KZT/Gcal.

---

## Configuration & Scripts

- Pipeline module: `src/countries/kz/fetcher.py`
- Configuration file: `config/kz/sources.json`
- City registry: `config/kz/city_registry.json`
