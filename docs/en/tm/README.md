# Turkmenistan Utility Tariffs Pipeline (`TM`) — retired

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../../ru/tm/README.md](../../ru/tm/README.md). Both files must stay identical in meaning.

**Turkmenistan is no longer published.** `config/countries.json` carries `"retired": true` for it, so
the country is not collected, is absent from both copies of `tariffs_index.json`, and its files —
`docs/tariffs_tm.json` and `assets/tariffs_tm_default.json` — have been deleted; the workflow deletes
the object in R2 as well. See ARCHITECTURE.md, section 8b, and ANDROID_MIGRATION.md, section 2a, for
what the app does when a country disappears.

---

## Why

Utility tariffs in Turkmenistan are set by presidential decree and published nowhere a pipeline can
read. Checked on 12 September 2026, so that nobody repeats the search:

| Where | What is there |
|---|---|
| `turkmenistan.gov.tm` | a news archive; the 2017 post about charges being introduced is superseded — free allowances were abolished in 2019 |
| `minenergo.gov.tm` and its enterprises (Türkmenenergo, Energohyzmat, Energoüpjünçilik) | no prices; the legal acts section holds the electricity law |
| `ashgabat.gov.tm`, `e.ashgabat.gov.tm` | single-page apps; the first has a documented API — news, services, schedules, contacts, no tariffs |
| `turkmenmetbugat.gov.tm`, `metbugat.gov.tm` | the state press, no tariff publications |
| `cis-legislation.com` | the decree text is behind a paywall; only the title is visible |
| Searches in Turkmen, Russian and English | news about the abolition of free allowances, and third-party estimates such as ≈0.01 USD/kWh |

What had been published here were round numbers from 2019 — 0.025 TMT/kWh, 0.5 + 0.2 per m³, 0.3 per
m³ of hot water, 5.0 per Gcal — with no source anyone could check. A tariff nobody can refresh is
worse than no tariff, because the app shows it as current, which is why the country was retired
rather than left in place.

---

## If a source appears

Remove `"retired": true` from `config/countries.json`, move the country to per-city collection the
way Georgia or Tajikistan are configured, and run it once. The city registry
(`config/tm/city_registry.json`) was kept, so Ashgabat comes back under the same `city_code` its
users had saved.
