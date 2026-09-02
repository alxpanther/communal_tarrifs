# Project structure

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/PROJECT_STRUCTURE.md](../ru/PROJECT_STRUCTURE.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

This repository is a **data generator**, not an application. It collects official utility tariffs,
validates them, and publishes one JSON file per country plus an index of the published countries,
all consumed by the Android app. There is no application code here.

Countries live side by side: every one has its own configuration folder, its own pipeline module and
its own output file, and they share everything that is not country-specific.

---

## 1. Directory map

```
kommeter_scripts/
├── AGENTS.md                     # Entry point for AI agents (thin pointer to CLAUDE.md)
├── CLAUDE.md                     # Entry point for AI agents: what to read before touching anything
├── README.md                     # Human-facing guide (Russian): setup, running, manual_override
├── requirements.txt              # Python dependencies of the pipeline
├── Dockerfile                    # Image that runs src/run_country.py
├── Dockerfile.wrangler           # Image that uploads the JSON files to Cloudflare R2
├── docker-compose.yml            # Two services: tariffs-fetcher, tariffs-deploy
├── wrangler.toml                 # Cloudflare project: R2 bucket + ./docs as static assets
├── .env                          # Secrets, git-ignored (see section 4)
│
├── .agents/rules/main_rules.md   # Always-on rules for every AI agent working in this repo
│
├── .github/workflows/
│   └── fetch_tariffs.yml         # Monthly cron: run every country, commit, deploy to R2 + Pages
│
├── config/                       # Input configuration — the only files edited by hand
│   ├── countries.json            # The country registry: codes, names, currency, publication layout
│   ├── ua/
│   │   ├── sources.json          # Source URLs, model settings, manual_override
│   │   └── city_registry.json    # Permanent supplier → city_code registry (never rewrite codes)
│   ├── am/{sources.json, city_registry.json}
│   ├── az/{sources.json, city_registry.json}
│   ├── md/{sources.json, city_registry.json}
│   ├── uz/{sources.json, city_registry.json}
│   ├── kz/{sources.json, city_registry.json}
│   └── by/{sources.json, city_registry.json}
│
├── src/                          # Pipeline code
│   ├── run_country.py            # Entry point: runs one country, several, or all, then the index
│   ├── build_index.py            # Builds tariffs_index.json for every publication target
│   ├── common/                   # Shared, country-agnostic code
│   │   ├── paths.py              # Every path derived from a country code
│   │   ├── countries.py          # Reads config/countries.json
│   │   ├── jsonio.py             # Previous file, root object, writing both output files
│   │   ├── overrides.py          # manual_override semantics, identical for all countries
│   │   ├── registry.py           # city_code registry: read, reconcile, append
│   │   ├── manual_pipeline.py    # Pipeline for countries whose tariffs come from config only
│   │   └── telegram_notifier.py  # Telegram delivery for alerts and discrepancy reports
│   └── countries/
│       ├── ua/fetcher.py         # Ukraine: scrape → parse → validate → save
│       ├── am/fetcher.py         # Armenia: config-driven, uses common/manual_pipeline.py
│       ├── az/fetcher.py         # Azerbaijan: config-driven, uses common/manual_pipeline.py
│       ├── md/fetcher.py         # Moldova: config-driven, uses common/manual_pipeline.py
│       ├── uz/fetcher.py         # Uzbekistan: config-driven, uses common/manual_pipeline.py
│       ├── kz/fetcher.py         # Kazakhstan: config-driven, uses common/manual_pipeline.py
│       └── by/fetcher.py         # Belarus: config-driven, uses common/manual_pipeline.py
│
├── assets/                       # Generated. Offline fallbacks bundled into the Android app
│   ├── tariffs_ua_default.json
│   ├── tariffs_am_default.json
│   ├── tariffs_az_default.json
│   ├── tariffs_md_default.json
│   ├── tariffs_uz_default.json
│   ├── tariffs_kz_default.json
│   └── tariffs_by_default.json
│
├── dist/cloudflare/
│   └── tariffs_index.json        # Generated. The R2 copy of the index (its own `path` values)
│
└── docs/                         # Documentation + published data (this folder is the web root)
    ├── tariffs_ua.json           # Generated. Served by GitHub Pages and mirrored to R2
    ├── tariffs_am.json           # Generated
    ├── tariffs_az.json           # Generated
    ├── tariffs_md.json           # Generated
    ├── tariffs_uz.json           # Generated
    ├── tariffs_kz.json           # Generated
    ├── tariffs_by.json           # Generated
    ├── tariffs_index.json        # Generated. The GitHub Pages copy of the country index
    ├── README.md                 # Documentation index
    ├── en/                       # English documentation — canonical, read by AI agents
    │   ├── PROJECT_STRUCTURE.md  # This file
    │   ├── ARCHITECTURE.md       # How the pipelines work, stage by stage
    │   ├── JSON_SPECIFICATION.md # The output contract: every field, Kotlin DTOs, formulas, index
    │   ├── ADDING_A_COUNTRY.md   # How to add a tariff pipeline for another country
    │   ├── DOCUMENTATION_RULES.md# How documentation and structure must be maintained
    │   └── ANDROID_MIGRATION.md  # Task brief for the Android side (hot water + heating)
    └── ru/                       # Russian mirror, same files, for the human maintainer
```

---

## 2. What each part is responsible for

### `config/` — the only hand-edited input

| File | Owner | Rules |
|---|---|---|
| `countries.json` | Maintainer | The registry of published countries: code, `country_names`, currency, `enabled`, `min_app_version`, the pipeline module, and the publication layout of each host. Both copies of `tariffs_index.json` are rendered from it, and every pipeline takes its root fields from it. A country not listed here is not published. |
| `<cc>/sources.json` | Maintainer | Every URL that country's pipeline touches. **No URL may be hardcoded in Python.** Also holds `settings` (Gemini model choice, HTTP timeout), `electricity.zones` (zone schedule and coefficients for config-driven countries), and `manual_override` (values forced on top of whatever the pipeline produced). |
| `<cc>/city_registry.json` | Pipeline + maintainer | Maps a supplier name, exactly as printed on the source site, to a permanent `city_code`. New suppliers are appended automatically; **an existing `city_code` is never rewritten**, because the Android app stores it as the user's saved choice. Section `suppliers` = water utilities, section `heat_suppliers` = heat suppliers (shared by hot water and heating). |

### `src/` — the pipelines

| File | Responsibility |
|---|---|
| `run_country.py` | The only entry point. Resolves which countries to run, runs them one after another, isolates a failure to the country that caused it, and rebuilds the index at the end. |
| `build_index.py` | Renders `tariffs_index.json` once per publication target, reading the country registry and the tariff files that actually exist on disk. |
| `common/paths.py` | The single place that knows the file layout of the repository. A pipeline never composes a path itself. |
| `common/countries.py` | Loads and validates `config/countries.json`. |
| `common/jsonio.py` | Loads the previous published file, assembles the root object (including `country_names`), writes both output files, and refuses to write a file with an empty electricity block. |
| `common/overrides.py` | `manual_override` semantics, shared by every country so they cannot drift apart. |
| `common/registry.py` | The permanent `city_code` registry: read, force registered codes onto the data, append new suppliers, notify. |
| `common/manual_pipeline.py` | The whole pipeline of a country that has no scrapable source: previous file → config values → validation → save. |
| `common/telegram_notifier.py` | The only place that talks to Telegram. Degrades gracefully: with no token configured it prints the message to stdout and returns `False`, so a pipeline never fails because of notifications. |
| `countries/<cc>/fetcher.py` | One country's pipeline, exposing a single `main(notifier)`. Ukraine scrapes and validates; Armenia and Azerbaijan only name the country and delegate to the shared manual pipeline. |

### Generated files — never edit by hand

`docs/tariffs_<cc>.json` and `assets/tariffs_<cc>_default.json` are byte-identical and are
**overwritten on every run**, and so are the two `tariffs_index.json` copies. Any manual edit is
silently lost on the next run. To force a value, use `manual_override` in `config/<cc>/sources.json`
(see the README section "Ручное переопределение тарифов").

### `docs/` — documentation *and* web root

This folder has a double role: it holds the documentation *and* it is the directory published by
GitHub Pages and declared as the Cloudflare assets directory in `wrangler.toml`. Consequences:

* `docs/tariffs_<cc>.json` and `docs/tariffs_index.json` must stay at the root of `docs/`, flat.
  Their published URLs depend on it, and released Android builds fetch those exact URLs.
* Markdown files inside `docs/` are published too. That is harmless, but do not put secrets or
  scratch files here.

### `dist/` — what is published somewhere other than Pages

Only the Cloudflare copy of the index lives here, because on R2 the files sit in per-country folders
and the index has to carry different `path` values. The country files themselves are uploaded to R2
straight from `docs/`; they are identical on both hosts.

---

## 3. Data flow between the parts

```
config/countries.json ──────────────┬─> src/run_country.py ─> src/countries/<cc>/fetcher.py ─┬─> docs/tariffs_<cc>.json ──> GitHub Pages
config/<cc>/sources.json ───────────┤                                    │                   │                        └──> Cloudflare R2
config/<cc>/city_registry.json ─────┘                                    │                   └─> assets/tariffs_<cc>_default.json ──> Android app bundle
        ▲                                                                │
        └── new suppliers ───────────────────────────────────────────────┤
                                                                         └─> src/common/telegram_notifier.py ──> Telegram (alerts, discrepancies)

docs/tariffs_<cc>.json ──> src/build_index.py ──┬─> docs/tariffs_index.json           ──> GitHub Pages
                                                └─> dist/cloudflare/tariffs_index.json ──> Cloudflare R2
```

Published URLs:

| What | Cloudflare R2 | GitHub Pages |
|---|---|---|
| Country file | `https://tarrifs.foleks.com/<cc>/tariffs_<cc>.json` | `https://alxpanther.github.io/communal_tarrifs/tariffs_<cc>.json` |
| Country index | `https://tarrifs.foleks.com/tariffs_index.json` | `https://alxpanther.github.io/communal_tarrifs/tariffs_index.json` |

---

## 4. Environment variables

Read from `.env` locally (via `python-dotenv`) and from GitHub Actions secrets in CI.

| Variable | Required | Used for |
|---|---|---|
| `GEMINI_API_KEY` | for Ukraine | Extraction and Search Grounding calls |
| `GEMINI_MODEL` | no | Pins a specific model; overrides `settings` in `config/ua/sources.json` |
| `TELEGRAM_BOT_TOKEN` | no | Notifications; without it messages go to stdout |
| `TELEGRAM_CHAT_ID` | no | Same |
| `CLOUDFLARE_API_TOKEN` | deploy only | `wrangler r2 object put` |
| `CLOUDFLARE_ACCOUNT_ID` | deploy only | Same |

`.env` is git-ignored and must stay that way.

---

## 5. Where to put new things

| You are adding | Put it here |
|---|---|
| A source URL, a model name, a timeout | `config/<cc>/sources.json` — never in Python |
| A forced tariff value | `config/<cc>/sources.json` → `manual_override` |
| A country name, currency or publication path | `config/countries.json` — never in Python |
| A new country pipeline | See [ADDING_A_COUNTRY.md](ADDING_A_COUNTRY.md): an entry in `config/countries.json`, a `config/<cc>/` folder, a `src/countries/<cc>/fetcher.py` |
| Logic two countries need | `src/common/` — never a copy in the second country's fetcher |
| A new documentation page | `docs/en/` **and** `docs/ru/`, plus a line in `docs/README.md` — see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md) |
| A throwaway script or a debug dump | A `tmp/` folder in the repo root, deleted when you are done. Nothing temporary belongs in `src/`, `docs/` or the repo root |
| A change to the output JSON schema | Nothing, until the maintainer agrees. The schema is a contract with the Android app — see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md), section "Frozen contracts" |
