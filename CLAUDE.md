## General requirements

- Alway follow SOLID and KISS principles.
- Prioritize clean, efficient and maintainble code.
- if task is unclear ask clarifying quiestions.
- Follow best practices and design appropriate for the language, framework and project.
- Clean up unused code.
- If you need to create some temporary files for scripts or something else, then create a temporary folder with name 'tmp' in the project directory and do everything there. After completing your actions, clean out everything that is not needed there and delete the folder.
- Always answer on russian language.

- Before starting to think about your answer, understand which step you need to complete next.
- If the user's request contradicts the plan, fulfill the request anyway.
- If the user's request is not related to the current project, fulfill the request.
- Use Context7 MCP for writing code on a Flutter, Dart, Swift, Kotlin, Python, Shell, Bash, Rust, React, PHP

- There is no need to edit files, make line breaks, or vice versa, write code all in one line in those files that are not related to these changes, make changes only in those files that really need to be changed to obtain the desired result.

## Communication

1. If you are unsure about the requirements or direction of development, ask specific questions.
2. When proposing multiple implementation options, clearly explain the advantages and disadvantages of each.

## Comments in code

CRITICAL! Write all code comments on English.

## JSON file with tarrifs

CRITICALLY INPORTANT! Change the structure of the application file with tariffs and the description of this file as a last resort, since it determines how the Android application will process this file.
If you want to change something in the structure, then first agree with me. You can add new fields, but you still need to inform me about this additionally, since corrections will need to be made to the Android application.

# Working in this repository

This file is the entry point for AI agents. Read it fully before the first tool call, then read the
documentation listed below. It is written in English on purpose: **agents read the English
documentation only.**

## What this repository is

A data generator, not an application. It collects official utility tariffs (electricity, cold water
and sewage, hot water, centralised heating), validates them, and publishes one JSON file per country
plus an index of the published countries, all consumed by an Android metering app. The app itself
lives in a different project.

**Collects** is meant literally: every published number is fetched from the source that regulates
it and read out of that document on the same run. The repository is the machinery for doing that
reliably — fetching, extracting, and above all refusing to publish an extraction it cannot trust.
A country whose numbers are typed into config by hand has not been added to this repository; it has
been faked in it, and the fake is indistinguishable from working software until the tariffs change.

Every country has its own `config/<cc>/` folder and its own `src/countries/<cc>/fetcher.py`;
everything they share lives in `src/common/`. A fetcher names its country and delegates to one of
the shared pipelines — it is a handful of lines, not a place for logic.

There are two pipelines:

| Pipeline | Module | Countries | What it means |
|---|---|---|---|
| Aggregated source | `src/countries/ua/fetcher.py` | UA | One page lists every city; scraped and extracted in one pass |
| Per-city sources | `src/common/ai_pipeline.py` | RU, AM, AZ, MD, GE, TJ, BY, KG, KZ, UZ | Each city declares its own sources in config and is read separately |

There used to be a third, config-declared pipeline: countries entered by a model that wrote
plausible-looking numbers into config rather than building a collector, and those numbers were wrong —
the Russian ones were out by half against the regulator's own decrees. Every country has since been
moved to per-city collection and the pipeline was deleted. Do not bring it back: a country with no
readable source is retired (`"retired": true` in `config/countries.json`), not typed in.

## Read before starting a task

In this order, English versions only. `docs/ru/` is a Russian mirror for the human maintainer — do
not read it as a source of truth, and never treat a difference between the two as a decision point:
report it instead.

1. [`docs/en/PROJECT_STRUCTURE.md`](docs/en/PROJECT_STRUCTURE.md) — what lives where and where new
   things go.
2. [`docs/en/ARCHITECTURE.md`](docs/en/ARCHITECTURE.md) — how the pipelines work, how several
   countries are run, and which invariants must hold.
3. [`docs/en/DOCUMENTATION_RULES.md`](docs/en/DOCUMENTATION_RULES.md) — how documentation and
   structure must be maintained.
4. Task-specific: [`docs/en/JSON_SPECIFICATION.md`](docs/en/JSON_SPECIFICATION.md) for anything
   touching the output format, [`docs/en/ADDING_A_COUNTRY.md`](docs/en/ADDING_A_COUNTRY.md) for a
   new country, [`docs/en/ANDROID_MIGRATION.md`](docs/en/ANDROID_MIGRATION.md) for the app side.

General agent rules also apply. They are imported below rather than linked: an import is loaded
into the context together with this file, while a link is only followed by an agent that remembers
to open it — which is exactly how these rules came to be ignored before.

@.claude/rules/main_rules.md

## Hard rules

* **Ask before changing the output JSON schema.** Field names and types are a contract with the
  released Android app. Adding a field is allowed but must be reported explicitly; renaming,
  removing or re-typing is not allowed without the maintainer's agreement.
* **Never rewrite an assigned `city_code`.** `config/<cc>/city_registry.json` is permanent state; the
  app stores those codes as the user's saved selection.
* **A tariff is collected, never typed in. This is the rule the repository exists for.**
  Every number published for a country must come out of that country's own sources, fetched
  and read on the run that publishes it. Writing a rate into `config/<cc>/sources.json`
  because you found it on a site, because the source was down, or because it was faster than
  making the pipeline read it, is the one change that is never acceptable — it looks like
  data, survives every check, and rots silently until a user notices the bill does not match.
  `config/<cc>/sources.json` holds **URLs, names and limits; it holds no rates.** If a source
  cannot be read, fix the source list or the pipeline; leaving the previous value published
  and alerting is the correct outcome, hand-entering a fresh one is not. The single narrow
  exception is `manual_override`, described below.
* **`manual_override` is a patch, not a place to keep data.** It exists to hold a value for
  the days between a tariff changing and the pipeline learning to read it, and every entry in
  it is a bug report against the pipeline. An override that has been sitting there for months
  means the source list is wrong and needs fixing. It is never the way to add a country, a
  city or a service.
* **Never hand-edit generated files** (`docs/tariffs_<cc>.json`, `assets/tariffs_<cc>_default.json`,
  both copies of `tariffs_index.json`). Force values through `manual_override` in
  `config/<cc>/sources.json`.
* **No hardcoded URLs, model names, timeouts, tariff values or country names in Python.** They belong
  in `config/`: sources in `config/<cc>/sources.json`, countries in `config/countries.json`.
* **A failure must never wipe good data.** Keep the previous block and alert instead, and never let
  one country's failure affect another.
* **Shared behaviour goes to `src/common/`.** Do not copy logic into a second country's fetcher.
* **Update both `docs/en/` and `docs/ru/` in the same change.** Documentation is part of the change,
  not a follow-up.
* **Code comments in English.** Chat replies to the maintainer are in Russian.
* **Temporary files go to a `tmp/` folder** in the repository root and are deleted afterwards.
* **A model call is paid for.** Make every fix first, then test only the cities it touches with
  `src/run_city.py`, and collect a whole country only after telling the maintainer what was
  changed and what the city tests showed, and getting their agreement.

## Running it

```bash
python src/run_country.py          # every enabled country, then the country index
python src/run_country.py ua       # one country
python src/run_country.py am az    # several
```

To test a change, run only the cities it touches. A dry run by default — it writes nothing:

```bash
python src/run_city.py ru yekaterinburg                 # every service of one city
python src/run_city.py ru yekaterinburg --block water   # one service
python src/run_city.py ru yekaterinburg --write         # publish just this city
```

Before a URL goes into config, prove it downloads — from GitHub, where the pipeline runs (the
"Check Sources" workflow). It calls no model and costs nothing. Never enter a guessed address,
and never a document tied to a date — a decree PDF, a tariff menu "for 2026", a news article about
"new tariffs from 1 October". A source is a page updated in place, which will carry next year's
figures at the same address:

```bash
python src/check_sources.py ru                          # every source of a country
python src/check_sources.py --url <candidate>           # before it goes into config
```

Docker and CI variants, plus the full `manual_override` reference, are in the Russian
[`README.md`](README.md).
