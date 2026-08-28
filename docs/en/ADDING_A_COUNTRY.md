# Adding tariffs for another country

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ADDING_A_COUNTRY.md](../ru/ADDING_A_COUNTRY.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

This page is for anyone — the maintainer, a contributor, or an AI agent — who wants to add a tariff
pipeline for one more country. Read [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) and
[ARCHITECTURE.md](ARCHITECTURE.md) first; this page only covers what is specific to a new country.

---

## 1. Current state

Three countries are published: Ukraine (`UA`), Armenia (`AM`) and Azerbaijan (`AZ`). They are two
different kinds of pipeline, and a new country will be one of them:

* **Scraping pipeline** — Ukraine. Official aggregate pages exist, so `src/countries/ua/fetcher.py`
  fetches, parses, validates and only then saves.
* **Config-driven pipeline** — Armenia and Azerbaijan. The regulator publishes decisions as prose and
  PDFs, with nothing a parser can rely on, so the numbers live in `config/<cc>/sources.json` under
  `manual_override` and `src/common/manual_pipeline.py` turns them into the same JSON file. The
  country's own `fetcher.py` is a dozen lines that name the country.

Start config-driven if there is no source worth scraping. It is a complete, supported pipeline, not
a placeholder: adding a scraping stage later does not change anything downstream of it.

---

## 2. Layout

A country is identified by its **ISO 3166-1 alpha-2 code**, upper case in the data, lower case in
paths (`ua`, `am`, `az`, `pl`).

```
config/
├── countries.json               # add your entry here — this is what publishes the country
└── pl/                          # your country
    ├── sources.json             # source URLs, zone schedule, manual_override
    └── city_registry.json       # starts as {"suppliers": {}, "heat_suppliers": {}}

src/
├── common/                      # shared, country-agnostic code — use it, do not copy it
└── countries/
    └── pl/fetcher.py            # your pipeline: a single main(notifier) entry point

assets/
└── tariffs_pl_default.json      # generated: offline fallback bundled into the app

docs/
└── tariffs_pl.json              # generated: the published file, flat at the web root
```

Both output files are written by `common/jsonio.py`; you never open them yourself.

The published layout is fixed by the Android app and differs per host:

| | Cloudflare R2 | GitHub Pages |
|---|---|---|
| Country file | `pl/tariffs_pl.json` | `tariffs_pl.json` |
| Country index | `tariffs_index.json` | `tariffs_index.json` |

`docs/` is the GitHub Pages root, so every country file stays **flat** in `docs/`, `tariffs_ua.json`
included — released Android builds fetch those exact URLs. The per-country folders exist on R2 only,
and the two copies of the index carry the matching `path` values (see
[JSON_SPECIFICATION.md](JSON_SPECIFICATION.md), section 6).

---

## 3. The output contract

Your pipeline must emit the same root object as the others. Full field reference:
[JSON_SPECIFICATION.md](JSON_SPECIFICATION.md).

```jsonc
{
  "version": "1.0",
  "last_updated_at": "2026-08-20T12:00:00.000000",  // ISO 8601
  "country": "PL",                                  // ISO 3166-1 alpha-2, upper case
  "country_names": { "ru": "Польша", "uk": "Польща" },
  "currency": "PLN",                                // ISO 4217
  "electricity": { ... },
  "water":       { ... },
  "hot_water":   { ... },
  "heating":     { ... }
}
```

Rules:

1. **Field names and types are frozen.** They are a contract with the Android app. Reuse them exactly
   as Ukraine does, including `unit` values (`"kWh"`, `"m3"`, `"Gcal"`) and the `YYYY-MM-DD` date
   format.
2. **The root fields come from `config/countries.json`**, through `common/jsonio.build_root()`.
   Never write `country`, `country_names` or `currency` by hand in a pipeline.
3. **A category your country does not have keeps an empty `cities` list.** Armenia has no district
   heating, so its `hot_water` and `heating` blocks are empty — that is the correct way to say it.
   Do not invent placeholder numbers, and do not repurpose a field for a different meaning.
4. **A category that does not exist in the current schema** (piped gas, waste collection, a fixed
   monthly standing charge) needs a new block. That is a schema change: **agree it with the
   maintainer before writing code**, because the app has to be extended in step.
5. **Units and rate semantics must match the field description.** If your country prices heat in
   GJ rather than Gcal, do not silently put GJ into `rate_gcal` — raise it as a schema question.
6. `city_code` must be a stable lower-case latin slug, unique inside its block, and assigned by a
   deterministic function — never by a language model.

---

## 4. Step by step

1. **Register the country** in `config/countries.json`: `code`, `country_names` for every app
   language, `currency`, `pipeline` (the folder name under `src/countries/`), `enabled`,
   `min_app_version`. Nothing is published until this entry exists.
2. **Create `config/<cc>/sources.json`.** Every URL you touch goes here, plus `settings` and a
   `manual_override` skeleton. For a config-driven country also fill `electricity.zones` with the
   zone schedule and coefficients — rates are always derived as `base_rate × coefficient`, never
   written twice.
3. **Create `config/<cc>/city_registry.json`** with the two empty sections.
4. **Write `src/countries/<cc>/fetcher.py`** exposing `main(notifier)`.
   * No scrapable source → call `common.manual_pipeline.run(country, notifier)` and stop. Armenia's
     fetcher is the whole template.
   * Scrapable source → for each category decide: rigid table → regular expressions; free-form page
     or irregular table → an LLM extraction call. Never use the model for numbers you can parse.
5. **Validate before trusting.** At minimum: sanity ceilings per rate, component sums matching the
   printed total, the row count matching the source table, no source row consumed twice. A failed
   validation must reject the whole block and keep the previous values — see the Ukrainian
   `validate_water_cities()` as the reference implementation.
6. **Take text fields from the source HTML**, not from the model's answer: supplier names, periods,
   decree references.
7. **Assign `city_code`** through `common/registry.py`: a registered supplier keeps its code, an
   unknown one is appended and reported to Telegram. For a scraping pipeline add deterministic
   transliteration for your language and the competition rule for cities with several suppliers.
8. **Delivery needs no new wiring.** `src/run_country.py` picks the country up from
   `config/countries.json`, and the CI workflow derives its R2 uploads from the generated index. Add
   the country to `docker-compose.yml` only if you use the local deploy container.
9. **Write the documentation** in `docs/en/` and `docs/ru/`, and update `docs/README.md` and
   `PROJECT_STRUCTURE.md`.
10. **Run it end to end at least twice** — `python src/run_country.py <cc>` — and confirm the second
    run produces byte-identical `city_code` values.

---

## 5. Non-negotiables

These are the invariants that make the published file trustworthy. A pipeline that breaks any of
them will not be merged.

* A failure never wipes data. Broken source, HTTP error, failed validation → keep the previous JSON
  block and send an alert.
* One country's failure never stops the others, and never removes a country from the index.
* `city_code` never changes once assigned, and the registry is committed to git.
* No hardcoded URLs, model names, timeouts, tariff values or country names in Python.
* No language model output is written to the file without being checked against the source.
* Generated files are never hand-edited.
* Code comments in English; documentation in both English and Russian.

---

## 6. Checklist for a pull request

- [ ] Entry in `config/countries.json` with `country_names` for every app language
- [ ] `config/<cc>/sources.json` with every URL used, and a `manual_override` skeleton
- [ ] `config/<cc>/city_registry.json` committed (may start empty)
- [ ] `src/countries/<cc>/fetcher.py` with a single `main(notifier)` entry point
- [ ] Shared logic used from `src/common/`, not copy-pasted
- [ ] Validation for every category, with rejection keeping the previous values
- [ ] Deterministic `city_code` assignment, verified stable across two runs
- [ ] `manual_override` supported and documented
- [ ] Output validated against [JSON_SPECIFICATION.md](JSON_SPECIFICATION.md); no schema change, or a
      schema change agreed with the maintainer in advance
- [ ] Outputs written to `docs/tariffs_<cc>.json` and `assets/tariffs_<cc>_default.json`
- [ ] The country appears in both copies of `tariffs_index.json` after a run
- [ ] Documentation added in `docs/en/` **and** `docs/ru/`, index updated
- [ ] A sample of the generated JSON included in the pull request description
