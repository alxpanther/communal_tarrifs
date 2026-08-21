# Architecture of the tariff pipeline

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ARCHITECTURE.md](../ru/ARCHITECTURE.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

One entry point, `src/tariffs_fetcher.py`, run by `main()`. It is a batch job: it starts, produces
one JSON file, notifies Telegram, and exits. There is no server, no database, no state other than
the two generated JSON files and `config/city_registry.json`.

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
   in `config/city_registry.json`. It never changes, whatever the model or the source returns,
   because the Android app persists it as the user's choice.
5. **No hardcoded URLs.** Everything the pipeline fetches is declared in `config/sources.json`.
6. **Notifications must never break the run.** `TelegramNotifier` swallows its own errors.

---

## 2. Execution order (`main()`)

| # | Step | Function | Failure behaviour |
|---|---|---|---|
| 1 | Load config | `load_config()` | Missing file or missing `electricity`/`water` source → fatal: Telegram alert, process exits without writing anything |
| 2 | Resolve model | `resolve_latest_gemini_model()` | `GEMINI_MODEL` env → auto-selected newest Flash model via `client.models.list()` → `settings.gemini_model` as the last fallback |
| 3 | Scrape and parse | `extract_reference_tariffs()` | Per-block fallback to the previous JSON, see section 3 |
| 4 | Apply overrides | `apply_manual_overrides()` | Incomplete override records are skipped and reported to Telegram |
| 5 | Cross-check | `search_alternative_tariffs()` + `compare_and_validate()` | Purely advisory, see section 5 |
| 6 | Write output | `build_final_json()` + `save_json()` | Writes `docs/tariffs_ua.json` and `assets/tariffs_ua_default.json` |
| 7 | Report | `TelegramNotifier.send_discrepancy_report()` | Only when discrepancies were found |

The order matters: **the file is always saved**, and discrepancies only produce a message. A
disagreeing third-party source never blocks an update.

---

## 3. Stage 3 in detail: building the four blocks

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

`build_final_json()` assembles the root object (`version`, `last_updated_at`, `country`, `currency`
plus the four blocks) and `save_json()` writes the same content to both `docs/tariffs_ua.json` and
`assets/tariffs_ua_default.json`.

`.github/workflows/fetch_tariffs.yml` then, on the 25th of each month at 11:00 UTC (or on manual
dispatch): runs the pipeline, commits the two JSON files **and the registry**, uploads the file to
the Cloudflare R2 bucket `kommeter` as `ua/tariffs_ua.json`, and publishes `docs/` to GitHub Pages.

The output contract itself — every field, its type and meaning — is in
[JSON_SPECIFICATION.md](JSON_SPECIFICATION.md).
