# Working in this repository

This file is the entry point for AI agents. Read it fully before the first tool call, then read the
documentation listed below. It is written in English on purpose: **agents read the English
documentation only.**

## What this repository is

A data generator, not an application. It scrapes official Ukrainian utility tariffs (electricity,
cold water and sewage, hot water, centralised heating), validates them, and publishes one JSON file
that an Android metering app consumes. The app itself lives in a different project.

## Read before starting a task

In this order, English versions only. `docs/ru/` is a Russian mirror for the human maintainer — do
not read it as a source of truth, and never treat a difference between the two as a decision point:
report it instead.

1. [`docs/en/PROJECT_STRUCTURE.md`](docs/en/PROJECT_STRUCTURE.md) — what lives where and where new
   things go.
2. [`docs/en/ARCHITECTURE.md`](docs/en/ARCHITECTURE.md) — how the pipeline works and which
   invariants must hold.
3. [`docs/en/DOCUMENTATION_RULES.md`](docs/en/DOCUMENTATION_RULES.md) — how documentation and
   structure must be maintained.
4. Task-specific: [`docs/en/JSON_SPECIFICATION.md`](docs/en/JSON_SPECIFICATION.md) for anything
   touching the output format, [`docs/en/ADDING_A_COUNTRY.md`](docs/en/ADDING_A_COUNTRY.md) for a
   new country, [`docs/en/ANDROID_MIGRATION.md`](docs/en/ANDROID_MIGRATION.md) for the app side.

General agent rules also apply: [`.agents/rules/main_rules.md`](.agents/rules/main_rules.md).

## Hard rules

* **Ask before changing the output JSON schema.** Field names and types are a contract with the
  released Android app. Adding a field is allowed but must be reported explicitly; renaming,
  removing or re-typing is not allowed without the maintainer's agreement.
* **Never rewrite an assigned `city_code`.** `config/city_registry.json` is permanent state; the app
  stores those codes as the user's saved selection.
* **Never hand-edit generated files** (`docs/tariffs_ua.json`, `assets/tariffs_ua_default.json`).
  Force values through `manual_override` in `config/sources.json`.
* **No hardcoded URLs, model names or timeouts in Python.** They belong in `config/`.
* **A failure must never wipe good data.** Keep the previous block and alert instead.
* **Update both `docs/en/` and `docs/ru/` in the same change.** Documentation is part of the change,
  not a follow-up.
* **Code comments in English.** Chat replies to the maintainer are in Russian.
* **Temporary files go to a `tmp/` folder** in the repository root and are deleted afterwards.

## Running it

```bash
python src/tariffs_fetcher.py
```

Docker and CI variants, plus the full `manual_override` reference, are in the Russian
[`README.md`](README.md).
