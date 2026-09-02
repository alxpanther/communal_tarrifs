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

1. **Electricity (`electricity`)**: Regulated by the Council of Ministers of RB / MART.
   - Base rate (subsidized rate for homes with electric stoves): ~0.2541 BYN/kWh.
   - Two-zone tariff: Day (17:00 - 22:00) 0.3557 BYN/kWh, Night (22:00 - 17:00) 0.1779 BYN/kWh.
2. **Water Supply & Sewage (`water`)**: Regulated by Minsk City Executive Committee / MART.
   - Minsk (*UP "Minskvodokanal"*): Water supply 1.5553 BYN/m³, Sewage 1.3095 BYN/m³, Total 2.8648 BYN/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Subsidized state rate per Gcal.
   - Minsk (*UP "Minskkommun teploset"* / *RUP "Minskenergo"*): ~24.7187 BYN/Gcal.

---

## Configuration & Scripts

- Pipeline module: `src/countries/by/fetcher.py`
- Configuration file: `config/by/sources.json`
- City registry: `config/by/city_registry.json`
