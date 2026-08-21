# Adding tariffs for another country

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ADDING_A_COUNTRY.md](../ru/ADDING_A_COUNTRY.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

This page is for anyone — the maintainer, a contributor, or an AI agent — who wants to add a tariff
pipeline for a country other than Ukraine. Read [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) and
[ARCHITECTURE.md](ARCHITECTURE.md) first; this page only covers what is specific to a new country.

---

## 1. Current state, honestly

Today the repository holds **one** pipeline, `src/tariffs_fetcher.py`, written for Ukraine, with the
Ukrainian paths and the value `"country": "UA"` inlined. It works and it is committed as is.

Everything in sections 2–4 below is the **agreed target layout for the second country**. It is a
convention, not existing code. The first person to add a country implements it. Moving the Ukrainian
pipeline into that layout is a separate change that **requires the maintainer's agreement**, because
the CI workflow, the Docker files and the published URLs depend on the current paths.

---

## 2. Target layout

A country is identified by its **ISO 3166-1 alpha-2 code in lower case** (`ua`, `pl`, `de`, `kz`).

```
config/
├── ua/
│   ├── sources.json
│   └── city_registry.json
└── pl/                          # your country
    ├── sources.json             # source URLs, model settings, manual_override
    └── city_registry.json       # starts as {"suppliers": {}, "heat_suppliers": {}}

src/
├── common/                      # shared, country-agnostic helpers
│   ├── telegram_notifier.py
│   ├── http.py                  # fetch_html and friends
│   ├── registry.py              # city_code registry: load / assign / save
│   ├── llm.py                   # Gemini model resolution, extract, search grounding
│   └── jsonio.py                # base schema loading, saving both output files
└── countries/
    ├── ua/fetcher.py
    └── pl/fetcher.py            # your pipeline: one main(config) entry point

assets/
├── tariffs_ua_default.json
└── tariffs_pl_default.json      # offline fallback bundled into the app

docs/
├── tariffs_ua.json              # legacy path, kept for backwards compatibility
└── pl/
    └── tariffs_pl.json          # new countries get their own folder
```

The Cloudflare R2 key follows the same shape as the existing one: `pl/tariffs_pl.json`.

`docs/tariffs_ua.json` stays at the root of `docs/` **forever**: released Android builds fetch that
exact URL. Do not "tidy" it into `docs/ua/`.

---

## 3. The output contract

Your pipeline must emit the same root object as Ukraine does. Full field reference:
[JSON_SPECIFICATION.md](JSON_SPECIFICATION.md).

```jsonc
{
  "version": "1.0",
  "last_updated_at": "2026-08-20T12:00:00.000000",  // ISO 8601
  "country": "PL",                                  // ISO 3166-1 alpha-2, upper case
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
2. **A category your country does not have is omitted or left with an empty `cities` list.** Do not
   invent placeholder numbers, and do not repurpose an existing field for a different meaning.
3. **A category that does not exist in the current schema** (piped gas, waste collection, a fixed
   monthly standing charge) needs a new block. That is a schema change: **agree it with the
   maintainer before writing code**, because the app has to be extended in step.
4. **Units and rate semantics must match the field description.** If your country prices heat in
   GJ rather than Gcal, do not silently put GJ into `rate_gcal` — raise it as a schema question.
5. `city_code` must be a stable lower-case latin slug, unique inside its block, and assigned by a
   deterministic function — never by a language model.

---

## 4. Step by step

1. **Pick the sources.** Prefer one official aggregate page per category (a regulator or a national
   statistics portal). Write every URL into `config/<cc>/sources.json`; nothing goes into the code.
2. **Create an empty registry** `config/<cc>/city_registry.json` with the two empty sections.
3. **Write the parser.** For each category decide: rigid table → regular expressions; free-form page
   or irregular table → an LLM extraction call. Never use the model for numbers you can parse.
4. **Validate before trusting.** At minimum: sanity ceilings per rate, component sums matching the
   printed total, the row count matching the source table, no source row consumed twice. A failed
   validation must reject the whole block and keep the previous values — see the Ukrainian
   `validate_water_cities()` as the reference implementation.
5. **Take text fields from the source HTML**, not from the model's answer: supplier names, periods,
   decree references.
6. **Assign `city_code`** through the shared registry helper: known supplier → registry value,
   unknown supplier → deterministic transliteration of the city name for your language, then append
   to the registry and notify Telegram. Copy the competition rule for cities with several suppliers.
7. **Support `manual_override`** with the same semantics: `null` means "do not override", city keys
   are `city_code`, a new city requires the complete field set.
8. **Wire up delivery**: an entry in `docker-compose.yml` if useful, a step or a matrix entry in
   `.github/workflows/fetch_tariffs.yml`, and the R2 upload key `<cc>/tariffs_<cc>.json`.
9. **Write the documentation** in `docs/en/` and `docs/ru/`, and add the new lines to
   `docs/README.md` and `PROJECT_STRUCTURE.md`.
10. **Run it end to end at least twice** and confirm the second run produces byte-identical
    `city_code` values.

---

## 5. Non-negotiables

These are the invariants that make the published file trustworthy. A pipeline that breaks any of
them will not be merged.

* A failure never wipes data. Broken source, HTTP error, failed validation → keep the previous JSON
  block and send an alert.
* `city_code` never changes once assigned, and the registry is committed to git.
* No hardcoded URLs, model names or timeouts in Python.
* No language model output is written to the file without being checked against the source.
* Generated files are never hand-edited.
* Code comments in English; documentation in both English and Russian.

---

## 6. Checklist for a pull request

- [ ] `config/<cc>/sources.json` with every URL used, and a `manual_override` skeleton
- [ ] `config/<cc>/city_registry.json` committed (may start empty)
- [ ] `src/countries/<cc>/fetcher.py` with a single entry point
- [ ] Shared logic used from `src/common/`, not copy-pasted
- [ ] Validation for every category, with rejection keeping the previous values
- [ ] Deterministic `city_code` assignment, verified stable across two runs
- [ ] `manual_override` supported and documented
- [ ] Output validated against [JSON_SPECIFICATION.md](JSON_SPECIFICATION.md); no schema change, or a
      schema change agreed with the maintainer in advance
- [ ] Outputs written to `docs/<cc>/tariffs_<cc>.json` and `assets/tariffs_<cc>_default.json`
- [ ] CI workflow updated (run, commit, R2 upload, Pages)
- [ ] Documentation added in `docs/en/` **and** `docs/ru/`, index updated
- [ ] A sample of the generated JSON included in the pull request description
