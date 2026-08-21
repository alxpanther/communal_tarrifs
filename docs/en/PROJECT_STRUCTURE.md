# Project structure

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/PROJECT_STRUCTURE.md](../ru/PROJECT_STRUCTURE.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

This repository is a **data generator**, not an application. It scrapes official utility tariffs,
validates them, and publishes a single JSON file that the Android app consumes. There is no
application code here.

---

## 1. Directory map

```
kommeter_scripts/
├── AGENTS.md                     # Entry point for AI agents (thin pointer to CLAUDE.md)
├── CLAUDE.md                     # Entry point for AI agents: what to read before touching anything
├── README.md                     # Human-facing guide (Russian): setup, running, manual_override
├── requirements.txt              # Python dependencies of the pipeline
├── Dockerfile                    # Image that runs src/tariffs_fetcher.py
├── Dockerfile.wrangler           # Image that uploads the JSON to Cloudflare R2
├── docker-compose.yml            # Two services: tariffs-fetcher, tariffs-deploy
├── wrangler.toml                 # Cloudflare project: R2 bucket + ./docs as static assets
├── .env                          # Secrets, git-ignored (see section 4)
│
├── .agents/
│   └── rules/
│       └── main_rules.md         # Always-on rules for every AI agent working in this repo
│
├── .github/
│   └── workflows/
│       └── fetch_tariffs.yml     # Monthly cron: run pipeline, commit, deploy to R2 + Pages
│
├── config/                       # Input configuration — the only files edited by hand
│   ├── sources.json              # Source URLs, model settings, manual_override
│   └── city_registry.json        # Permanent supplier → city_code registry (never rewrite codes)
│
├── src/                          # Pipeline code
│   ├── tariffs_fetcher.py        # The whole Ukrainian pipeline: fetch → parse → validate → save
│   └── telegram_notifier.py      # Telegram delivery for alerts and discrepancy reports
│
├── assets/
│   └── tariffs_ua_default.json   # Generated. Offline fallback bundled into the Android app
│
└── docs/                         # Documentation + published data (this folder is the web root)
    ├── tariffs_ua.json           # Generated. Served by GitHub Pages and mirrored to R2
    ├── README.md                 # Documentation index
    ├── en/                       # English documentation — canonical, read by AI agents
    │   ├── PROJECT_STRUCTURE.md  # This file
    │   ├── ARCHITECTURE.md       # How the pipeline works, stage by stage
    │   ├── JSON_SPECIFICATION.md # The output contract: every field, Kotlin DTOs, formulas
    │   ├── ADDING_A_COUNTRY.md   # How to add a tariff source for another country
    │   ├── DOCUMENTATION_RULES.md# How documentation and structure must be maintained
    │   └── ANDROID_MIGRATION.md  # Task brief for the Android side (hot water + heating)
    └── ru/                       # Russian mirror, same six files, for the human maintainer
```

---

## 2. What each part is responsible for

### `config/` — the only hand-edited input

| File | Owner | Rules |
|---|---|---|
| `sources.json` | Maintainer | Every URL the pipeline touches lives here. **No URL may be hardcoded in Python.** Also holds `settings` (Gemini model choice, HTTP timeout) and `manual_override` (values forced on top of scraped data). |
| `city_registry.json` | Pipeline + maintainer | Maps a supplier name, exactly as printed on the source site, to a permanent `city_code`. New suppliers are appended automatically; **an existing `city_code` is never rewritten**, because the Android app stores it as the user's saved choice. Section `suppliers` = water utilities, section `heat_suppliers` = heat suppliers (shared by hot water and heating). |

### `src/` — the pipeline

| File | Responsibility |
|---|---|
| `tariffs_fetcher.py` | Everything: config loading, HTTP fetching, HTML parsing, LLM calls, validation, `city_code` assignment, manual overrides, cross-source comparison, writing both output files. See [ARCHITECTURE.md](ARCHITECTURE.md) for the stage-by-stage breakdown. |
| `telegram_notifier.py` | The only place that talks to Telegram. Degrades gracefully: with no token configured it prints the message to stdout and returns `False`, so the pipeline never fails because of notifications. |

### Generated files — never edit by hand

`assets/tariffs_ua_default.json` and `docs/tariffs_ua.json` are byte-identical and are **overwritten on every run**. Any manual edit is silently lost on the next run. To force a value, use `manual_override` in `config/sources.json` (see the README section "Ручное переопределение тарифов").

### `docs/` — documentation *and* web root

This folder has a double role: it holds the documentation *and* it is the directory published by
GitHub Pages and declared as the Cloudflare assets directory in `wrangler.toml`. Consequences:

* `docs/tariffs_ua.json` must stay at the root of `docs/`, its published URL depends on it.
* Markdown files inside `docs/` are published too. That is harmless, but do not put secrets or
  scratch files here.

---

## 3. Data flow between the parts

```
config/sources.json ─┐
                     ├─> src/tariffs_fetcher.py ─┬─> docs/tariffs_ua.json ──> GitHub Pages
config/city_registry ┘        │                  │                       └──> Cloudflare R2
        ▲                     │                  └─> assets/tariffs_ua_default.json ──> Android app bundle
        └── new suppliers ────┘                  
                              └─> src/telegram_notifier.py ──> Telegram (alerts, discrepancies)
```

Published URLs (both serve the same file):

* `https://tarrifs.foleks.com/ua/tariffs_ua.json` — Cloudflare R2
* `https://alxpanther.github.io/communal_tarrifs/tariffs_ua.json` — GitHub Pages

---

## 4. Environment variables

Read from `.env` locally (via `python-dotenv`) and from GitHub Actions secrets in CI.

| Variable | Required | Used for |
|---|---|---|
| `GEMINI_API_KEY` | yes | Extraction and Search Grounding calls |
| `GEMINI_MODEL` | no | Pins a specific model; overrides `settings` in `sources.json` |
| `TELEGRAM_BOT_TOKEN` | no | Notifications; without it messages go to stdout |
| `TELEGRAM_CHAT_ID` | no | Same |
| `CLOUDFLARE_API_TOKEN` | deploy only | `wrangler r2 object put` |
| `CLOUDFLARE_ACCOUNT_ID` | deploy only | Same |

`.env` is git-ignored and must stay that way.

---

## 5. Where to put new things

| You are adding | Put it here |
|---|---|
| A source URL, a model name, a timeout | `config/sources.json` — never in Python |
| A forced tariff value | `config/sources.json` → `manual_override` |
| A new country pipeline | See [ADDING_A_COUNTRY.md](ADDING_A_COUNTRY.md) — a new module under `src/`, its own config, its own output file |
| A new documentation page | `docs/en/` **and** `docs/ru/`, plus a line in `docs/README.md` — see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md) |
| A throwaway script or a debug dump | A `tmp/` folder in the repo root, deleted when you are done. Nothing temporary belongs in `src/`, `docs/` or the repo root |
| A change to the output JSON schema | Nothing, until the maintainer agrees. The schema is a contract with the Android app — see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md), section "Frozen contracts" |
