# Architecture of the tariff pipeline

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ARCHITECTURE.md](../ru/ARCHITECTURE.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

One entry point for everything: `src/run_country.py`. It is a batch job — it starts, runs the
pipeline of every requested country one after another, rebuilds the country index, notifies
Telegram, and exits. There is no server, no database, no state other than the generated JSON files
and the `config/<cc>/city_registry.json` registries.

Sections 2–6 describe the Ukrainian pipeline, which is the richest one and the reference for
everything else. Section 8 covers the config-driven pipeline used by every country except Ukraine, and
section 9 the country index.

---

## 1. Design principles

These are the rules the current code follows. Keep following them.

1. **Never destroy good data.** Every stage falls back to the previous run's value. A broken source,
   a failed HTTP request or a rejected validation leaves the old numbers in place and sends a
   Telegram alert. An empty or half-filled block is never written.
2. **Only use the model where a machine cannot cope.** Free-form pages (electricity) and irregular
   multi-row tables (water) go through Gemini. Rigid 2–4 column tables (hot water, heating) are
   parsed by regular expressions. In the steady state the heat blocks make zero model calls.
3. **Numbers and text come from the source, not from the model.** For water, the model only returns
   the triple of numbers used as a key to find the row; `supplier` and the validity period are then
   read back from the HTML. Models routinely "fix" unusual Ukrainian company names, and only the
   spelling from the site may reach the JSON.
4. **Identifiers are permanent.** `city_code` is assigned once by a pure Python function and stored
   in `config/ua/city_registry.json`. It never changes, whatever the model or the source returns,
   because the Android app persists it as the user's choice.
5. **No hardcoded URLs.** Everything a pipeline fetches is declared in `config/<cc>/sources.json`,
   and everything about a country itself in `config/countries.json`.
6. **Notifications must never break the run.** `TelegramNotifier` swallows its own errors.
7. **Countries are independent.** One country failing must not stop, delay or alter another, and must
   not remove it from the index.
8. **Shared behaviour lives in `src/common/`.** Anything two countries do the same way — overrides,
   the registry, writing the file — has exactly one implementation.

---

## 2. Execution order of the Ukrainian pipeline (`main()`)

| # | Step | Function | Failure behaviour |
|---|---|---|---|
| 1 | Load config | `load_config()` | Missing file or missing `electricity`/`water` source → the country is aborted by `run_country.py`, which alerts Telegram and moves on to the next one; nothing is written |
| 2 | Resolve model | `resolve_latest_gemini_model()` | `GEMINI_MODEL` env → auto-selected newest Flash model via `client.models.list()` → `settings.gemini_model` as the last fallback |
| 3 | Scrape and parse | `extract_reference_tariffs()` | Per-block fallback to the previous JSON, see section 3 |
| 4 | Apply overrides | `apply_manual_overrides()` | Incomplete override records are skipped and reported to Telegram; a dated `periods` record is collapsed to the version in force today |
| 5 | Cross-check | `search_alternative_tariffs()` + `compare_and_validate()` | Purely advisory, see section 5 |
| 6 | Write output | `build_root()` + `save_country_json()` (both in `common/jsonio.py`) | Writes `docs/tariffs_ua.json` and `assets/tariffs_ua_default.json`; refuses to write at all if the electricity block came out empty |
| 7 | Report | `TelegramNotifier.send_discrepancy_report()` | Only when discrepancies were found |

The order matters: **the file is always saved**, and discrepancies only produce a message. A
disagreeing third-party source never blocks an update.

---

## 3. Ukraine, stage 3 in detail: building the four blocks

`extract_reference_tariffs()` starts from `load_base_schema()`, which loads the previous
`docs/tariffs_ua.json` (or `assets/tariffs_ua_default.json`, or a built-in default) and uses it as
the base to patch. That is what makes the per-block fallback work.

### `electricity`

Free-form page → the first 15 000 characters of HTML go to `call_gemini_extract()`, which returns
`base_rate`, `effective_date`, `decree_info`. Only `base_rate` is stored directly;
`apply_base_rate_to_zones()` recomputes every zone rate as `base_rate × coefficient`, so the
two-zone and three-zone tariffs are always internally consistent and are never taken from the model.

### `water`

The heaviest path, `extract_water_tariffs()`:

1. `extract_water_table_html()` cuts out the table, `count_supplier_rows()` counts how many supplier
   rows it really has, `source_rows()` indexes them by their numeric triple.
2. The model receives the table and returns one record per city.
3. `validate_water_cities()` rejects the whole block unless every condition holds:
   * each `water_supply / sewage / total_rate` triple exists in the source **in that exact order**;
   * the number of returned rows equals the number of rows in the table;
   * no source row is claimed twice;
   * `water_supply + sewage == total_rate` within `RATE_SUM_TOLERANCE`;
   * every component is below `MAX_WATER_RATE`.
4. `supplier` and the validity period are copied from the matched HTML row, overwriting whatever the
   model wrote. `decree_info` is composed from the period, because the source does not publish
   decree numbers per water utility.
5. `resolve_city_identity()` assigns final `city_code` / `city_name` from the registry.

A single failed check rejects the block: the previous cities are kept and Telegram receives the list
of complaints.

### `hot_water` and `heating`

`extract_heat_blocks()`. Both source tables are rigid, so `hot_water_rows()` and `heating_rows()`
parse them with regular expressions, and `validate_hot_water_rows()` / `validate_heating_rows()`
apply sanity limits (`MAX_HOT_WATER_RATE`, `MAX_HEAT_GCAL_RATE`, `MAX_HEAT_GCAL_HOUR_RATE`). The
validity date comes from the table caption via `parse_caption_date()`.

Two special cases:

* **Kyiv hot water** — `extract_kyiv_hot_water()` reads a separate minfin page declared as
  `reference_sources.hot_water_kyiv`. Only the number is taken from HTML; `supplier`, `city_name`,
  `effective_date` and `decree_info` come from that same config block.
* **Kyiv heating** — not on any aggregate source at all (the supplier's own site publishes PNG
  images and PDFs), so it is entered through `manual_override`.

The model is only asked for one thing here: the city name of a supplier that is not yet in the
registry (`CITY_NAME_PROMPT` / `resolve_city_names()`). Once every supplier is registered, these
blocks run without any model call.

---

## 4. The city registry

`resolve_city_identity()` is the single place where a `city_code` is born.

* Known supplier (normalised name match) → `city_code` and `city_name` are taken from the registry,
  the model's answer is discarded.
* Unknown supplier → `assign_city_code()` transliterates the city name per Ukrainian Cabinet
  Resolution No. 55 of 27.01.2010 (`translit_uk()`, pure Python, no LLM), resolves competition for
  the "plain" code, appends the entry to the registry and notifies Telegram.
* Competition rule: when several suppliers share a city name, the plain code (`vinnytsia`) goes to
  the main one — for water, the one whose name carries a waterworks marker (`is_waterworks()`); for
  heat, the only one whose quoted name contains the city root (`is_named_after_city()`). If there is
  no single winner, nobody gets the plain code and everybody gets a suffix.
* A supplier that disappeared from the source keeps its registry entry but drops out of the JSON,
  and Telegram gets a warning, because users holding that `city_code` lose their selection.

The registry **must be committed**; the CI workflow commits it together with the tariff files.
Starting from an empty registry would produce different codes and break existing installs.

---

## 5. Cross-source verification

`search_alternative_tariffs()` runs a Gemini Search Grounding query for newer official tariffs, and
`compare_and_validate()` compares the result with what was scraped: a discrepancy is reported when
the rate differs or the alternative source has a later `effective_date`
(`rate_discrepancy()`, `CITY_BLOCK_CHECKS`).

This path is **advisory only**. It cannot change a single number in the output; it produces a
Telegram table telling the maintainer to decide, and typically the answer is an entry in
`manual_override`.

---

## 6. Manual overrides

`apply_manual_overrides()` runs *after* scraping and *before* saving, so overrides win over scraped
values while everything not overridden keeps refreshing itself.

* `null` means "do not override this field" — to zero a tariff, write `0.0`.
* For city blocks, the key is the `city_code`. An existing city is patched field by field
  (`merge_city_overrides()`); a city absent from the scraped data is appended, but only if **all**
  fields listed in `MANUAL_CITY_REQUIRED_FIELDS` are present, otherwise the record is skipped and
  the missing fields are reported to Telegram.
* `"enabled": false` disables the whole block while keeping the drafts inside it.
* A city record may carry `periods` instead of flat values: a list of dated versions of the same
  tariff, each with `from` and an optional `to`. `resolve_periods()` collapses it to the version in
  force on the day of the run before anything else looks at the record, and `from` becomes the
  default `effective_date`. Everything downstream — patching, the completeness check, the registry —
  sees a plain flat record and cannot tell the difference.

  This exists because a regulator normally publishes the whole indexation schedule years ahead:
  Russia moved its indexation to 1 October 2026 and the values for that date were known in December
  2025. Entering them once means the monthly cron switches over on its own. When the last period has
  expired and no newer one was entered, the file **keeps the last known tariff** and a reminder goes
  to Telegram — stale data still beats dropping the city out of the app.

Full field-by-field reference with worked examples: README, section "Ручное переопределение тарифов".

---

## 7. Output and deployment

`build_root()` assembles the root object (`version`, `last_updated_at`, `country`, `country_names`,
`currency` plus the four blocks) from `config/countries.json`, and `save_country_json()` writes the
same content to both `docs/tariffs_ua.json` and `assets/tariffs_ua_default.json`. Both live in
`src/common/jsonio.py`, so every country produces an identically shaped file.

`.github/workflows/fetch_tariffs.yml` then, on the 25th of each month at 11:00 UTC (or on manual
dispatch, which accepts a list of country codes):

1. runs `python src/run_country.py` — every enabled country in turn, then the index;
2. commits the tariff files, both index copies and the registries, rebasing onto the branch before
   pushing so a concurrent push cannot fail the job;
3. uploads to the Cloudflare R2 bucket `kommeter`: the index at the bucket root and every country
   file under `<cc>/tariffs_<cc>.json`, with the list taken from the generated index rather than
   from the workflow file;
4. publishes `docs/` to GitHub Pages.

One job does all countries, so two runs can never push to the same branch or deploy Pages at the
same time.

---

## 8. Countries without a scrapable source

Every country except Ukraine has no page a parser can trust: the regulators publish decisions as
prose and PDFs. For them `config/<cc>/sources.json` → `manual_override` **is** the source, and
`src/common/manual_pipeline.py` is the whole pipeline. `src/countries/am/fetcher.py` and
`src/countries/az/fetcher.py` only name the country and delegate to it.

Order of work in `manual_pipeline.run()`:

1. `load_config()` — a country with no scraping stage must have `manual_override.enabled`, otherwise
   the run is aborted rather than publishing a stale file silently.
2. The previous published file becomes the base. With no previous file, `build_skeleton()` builds an
   empty one from config: zone schedule and coefficients from `electricity.zones`, source URLs from
   `reference_sources`, no rates.
3. `sync_zone_schedule()` copies the zone schedule from config over the file, so editing hours or a
   coefficient in config actually reaches the published file.
4. `apply_manual_overrides()` — the same shared function Ukraine uses.
5. A zero `base_rate` aborts the country: a file claiming free electricity is worse than yesterday's
   file.
6. `reconcile_cities()` records new suppliers in `config/<cc>/city_registry.json` and forces already
   registered codes onto the data.
7. `build_root()` + `save_country_json()`, exactly as for Ukraine.

Adding a scraping stage to such a country later means inserting it in front of step 4 in that
country's own `fetcher.py`; nothing downstream changes.

Two traps met while entering Russian tariffs, both of them general:

* **A supplier name is the registry key, so it must be unique inside a country.**
  `reconcile_cities()` matches on the normalized supplier name across the whole country, not per
  city. ПАО «Т Плюс» supplies heat in Samara and in Yekaterinburg alike, and the bare name would have
  dragged the Samara `city_code` onto the Yekaterinburg record. The city has to be part of the name:
  `ПАО "Т Плюс" (Екатеринбург)`.
* **Russian hot water is a two-component tariff** — roubles per m³ of carrier plus roubles per Gcal
  of heat — while `hot_water.cities[].rate` is a single price per m³. It is folded into one number
  as `carrier + energy × the regional norm for heating one m³` (Sverdlovsk oblast: 0.05131 Gcal/m³
  for a closed system), and the arithmetic is spelled out in `decree_info` so the published number
  can be traced back. The alternative — three new fields — is a change to the contract with the
  released app and has not been made.

---

## 8a. Countries read city by city

Ukraine has one page listing every city. Most countries have nothing of the kind: each city is
regulated separately, by its own commission, and publishes its own decree. For those the unit of
work is **one city and one service**, each with its own source URLs in `config/<cc>/sources.json`,
and the pipeline is `src/common/ai_pipeline.py`. Russia runs on it.

### Where the pieces live

| Module | Responsibility |
|---|---|
| `common/fetching.py` | Downloads one source. Returns text for markup, raw bytes for a PDF — including a scan with no text layer, which several regulators still publish. Flattens HTML to text while keeping table rows and cells, which cuts a 136 KB page to 7 KB without losing which number sits next to which label. |
| `common/llm.py` | The extraction model: which one to use, how a document is handed over, how a failure is reported. No model name is written in the code — `settings.gemini_model` is the floor and auto-selection only ever raises it to a newer plain `gemini-<version>-flash`. |
| `common/prompts.py` | What the model is asked. One template per block, filled from config. |
| `common/validation.py` | Whether the answer may be published. |
| `common/ai_pipeline.py` | The run: previous file → fetch → extract → validate → merge what passed → save. |

### One city, one service

1. `fetch_all()` downloads every URL declared for that city and block. A URL that fails is skipped;
   the others still go to the model. All of them go together, because a tariff is often split
   across documents — the water component on the utility's site, the heating norm on the
   regulator's.
2. `prompts.city_prompt()` builds the instruction: the service, the city, the supplier config
   expects, the currency, the unit, **today's date**, and the per-source `hint`.
3. `llm.extract()` returns JSON, or nothing.
4. `validation.validate_city()` decides whether it may be published.
5. On success the record is flattened by `resolve_periods()` to the values in force today and
   replaces that city in the block. On failure **nothing is replaced**: the city keeps the tariff
   it had, and the reason is logged and sent to Telegram.

### Why the prompt carries the date and a hint

Both exist because of mistakes that were made and caught, not as decoration.

* **The date.** A decree lists a decade of periods. A model with no idea what today is returns the
  ones from two years ago, and an old tariff extracted from a real document passes every structural
  check there is.
* **The hint.** One page usually prints several tariffs that are all real: before and after the heat
  substation, drinking and technical water, every price zone the regulator governs. Which one a
  household in this city pays is knowledge about the city, so it sits in config next to the URL.
  Without it the Moscow heating tariff came back as the "before the substation" figure — a genuine
  number from a genuine document, and the wrong one for a flat.

### What the validator refuses

`validation.py` drops a city whole rather than publish a doubtful field, because a partly wrong
record is worse than a stale one: it looks current.

* a zero, a negative, or a non-numeric rate — a standing charge on a single-rate heat tariff is the
  only value allowed to be zero;
* a rate above the block's ceiling in `validation` — a decimal point in the wrong place;
* water where `water_supply + sewage` does not match `total_rate`. The sum itself is computed by the
  code when the source does not print one: asking a model to add two numbers invites it to "fix" a
  total that does not add up, which is the mistake worth catching;
* hot water whose components do not multiply out to the stated price. Two-component tariffs are
  folded to one price per m³ **by `fold_hot_water()`, not by the model** — a number the code
  computed can be checked, a number the model computed cannot;
* a supplier the source does not name. Compared after dropping the legal form and any parenthesised
  qualifier, so «МУП "Водоканал г. Екатеринбурга"» matches «МУП «Водоканал»» while «АО "СИБЭКО"»
  does not match «ООО "Новосибирская теплосетевая компания"». Where the source uses an abbreviation
  that cannot be matched to its expansion, config lists it under `supplier_aka`;
* a period with no parsable start date, or two periods starting the same day;
* **a jump larger than `max_change_ratio` against what is already published.** This is the one that
  catches a confident, plausible, wrong extraction — the model read the industrial column, or
  another year, or another city. The number itself passes every other check; only its distance from
  last month's number gives it away.

### Retiring a city

A city with no readable source for any of its services is removed rather than kept. An entry nobody
can refresh is worse than a missing one: the app renders it as a current tariff, and its age is not
visible to the user.

`retired_cities` in config lists the codes to drop; `drop_retired_cities()` removes them from the
file on every run, and the city is deleted from `cities` as well because there is nothing left to
collect it from.

The `city_code` is **not** released. It stays in `city_registry.json` for good and is never handed to
another supplier, so a city that finds a usable source later comes back under the code its users
already saved. Until then the app simply shows no tariff for it, which it already handles.

### What a run reports

One Telegram message per country: how many cities were refreshed in each block, and every reason
something was not. A miss is a normal outcome — a regulator's site is down, a decree has not been
published yet — but it is never silent, and the file always keeps the previous value.

---

## 9. The country index

`src/build_index.py` renders `tariffs_index.json` — the list of countries whose tariffs are
published — once per publication target declared in `config/countries.json`. It runs at the end of
every `run_country.py` invocation, after the pipelines, so it always describes what is really on
disk.

* An entry is built from the country registry (code, names, currency, `enabled`, `min_app_version`)
  and from the country's own published file (`last_updated_at`).
* A country whose file is missing or unreadable is left out of the index, with a warning. It is not
  invented.
* If **no** country file could be read, nothing is written at all: an empty index would tell the app
  that nothing is published, and keeping yesterday's index is always better than that.
* Each host gets its own copy because the file layouts differ: `docs/tariffs_index.json` with flat
  paths for GitHub Pages, `dist/cloudflare/tariffs_index.json` with `<cc>/tariffs_<cc>.json` paths
  for R2. Both are rendered from the same registry, so they cannot disagree about which countries
  exist.

Format and the rules the app applies to it: [JSON_SPECIFICATION.md](JSON_SPECIFICATION.md),
section 6.

---

## 10. Running several countries

`src/run_country.py` takes country codes (`ua`, `am az`, `all`, or nothing for every enabled
country), runs them in the order of `config/countries.json`, and catches everything each one throws:
the failure is logged, reported to Telegram, and the next country still runs. The exit code is
non-zero if any country or the index failed, which is what turns the CI job red — while the
countries that did succeed are already published.

The output contract itself — every field, its type and meaning — is in
[JSON_SPECIFICATION.md](JSON_SPECIFICATION.md).
