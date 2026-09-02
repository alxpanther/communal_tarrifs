# Russia Utility Tariffs Pipeline (`RU`)

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/ru/README.md](../../ru/ru/README.md). Both files must stay identical in meaning.

This pipeline fetches and publishes utility tariffs for Russia (`country: "RU"`, `currency: "RUB"`).

---

## Output Files

- `docs/tariffs_ru.json` — published JSON file for mobile application consumption.
- `assets/tariffs_ru_default.json` — offline fallback asset bundled inside the Android app.

---

## Sources & Regulations

1. **Electricity (`electricity`)**: Regulated by the Department of Economic Policy and Development of Moscow (DEPIR) / FAS RF.
   - Base single-zone tariff: 6.99 RUB/kWh (*Mosenergosbyt*, homes with gas stoves, Range 1).
   - Two-zone tariff: Day (07:00 - 23:00) 8.04 RUB/kWh, Night (23:00 - 07:00) 2.62 RUB/kWh.
   - Three-zone tariff: Peak 9.37 RUB/kWh, Half-peak 6.99 RUB/kWh, Night 2.62 RUB/kWh.
2. **Water Supply & Sewage (`water`)**: Regulated by DEPIR Moscow.
   - Moscow (*AO "Mosvodokanal"*): Water supply 59.80 RUB/m³, Sewage 45.91 RUB/m³, Total 105.71 RUB/m³.
3. **Hot Water & Heating (`hot_water`, `heating`)**: Regulated by DEPIR Moscow.
   - Moscow (*PAO "MOEK"*): Hot water 272.79 RUB/m³, Heating 2912.24 RUB/Gcal.

---

## Configuration & Scripts

- Pipeline module: `src/countries/ru/fetcher.py`
- Configuration file: `config/ru/sources.json`
- City registry: `config/ru/city_registry.json`
