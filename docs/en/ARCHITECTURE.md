# Architecture of the tariff pipeline

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ARCHITECTURE.md](../ru/ARCHITECTURE.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

One entry point for everything: `src/run_country.py`. It is a batch job — it starts, runs the
pipeline of every requested country one after another, rebuilds the country index, notifies
Telegram, and exits. There is no server, no database, no state other than the generated JSON files
and the `config/<cc>/city_registry.json` registries.

Sections 2–6 describe the Ukrainian pipeline, which is the richest one and the reference for
everything else. Section 8 covers the config-driven pipeline used by Armenia and Azerbaijan, and
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
| 4 | Apply overrides | `apply_manual_overrides()` | Incomplete override records are skipped and reported to Telegram |
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

Armenia and Azerbaijan have no page a parser can trust: the regulators publish decisions as prose
and PDFs. For them `config/<cc>/sources.json` → `manual_override` **is** the source, and
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
