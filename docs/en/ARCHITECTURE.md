# Architecture of the tariff pipeline

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ARCHITECTURE.md](../ru/ARCHITECTURE.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

One entry point for everything: `src/run_country.py`. It is a batch job — it starts, runs the
pipeline of every requested country one after another, rebuilds the country index, notifies
Telegram, and exits. There is no server, no database, no state other than the generated JSON files
and the `config/<cc>/city_registry.json` registries.

Sections 2–6 describe the Ukrainian pipeline, which is the richest one and the reference for
everything else. Section 8 covers the config-declared pipeline, which six countries are still waiting to leave,
section 8a the per-city pipeline that collects Russia, Armenia, Azerbaijan, Moldova and Georgia, and
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

Three workflows share the repository:

| Workflow | Runs | Does |
|---|---|---|
| Fetch and Update Tariffs | on the 1st and the 25th, or by hand with country codes | collects, commits the files with `[skip ci]`, publishes to R2 and Pages |
| Publish Tariffs | on a push that changes a published file, or by hand | publishes the files already in the repository; no collection, no model call |
| Check Sources | by hand | downloads sources from a GitHub runner and reports which answer; no model call, nothing written |

---

## 8. Countries without a scrapable source

Six countries are still here — BY, KG, KZ, TJ, TM, UZ — and none of them should stay.
For them `config/<cc>/sources.json` → `manual_override` **is** the source, and
`src/common/manual_pipeline.py` is the whole pipeline. `src/countries/by/fetcher.py` and
`src/countries/ge/fetcher.py` only name the country and delegate to it.

Russia, Armenia, Azerbaijan, Moldova and Georgia have left this pipeline for per-city collection (section 8a), and
that is the direction for the rest: a country is moved by finding its sources, not by refreshing
its numbers here. Armenia shows how little it takes — the regulator's tariff decision and the
utility's own FAQ page were enough, even though its fetcher had claimed for a year that no readable
source existed.

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
| `common/llm/` | The extraction model behind one interface, `Extractor`: `base.py`, plus one module per provider — `gemini.py`, `openai_compatible.py`. Which provider and model a country uses is `settings.llm` in its config; no model name or endpoint is written in the code. |
| `common/pdf.py` | A PDF for a provider that cannot read one: its text layer, or rendered page images when it is a scan. |
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
3. The country's `Extractor` (`common/llm/`) returns JSON, or nothing.
4. `validation.validate_city()` decides whether it may be published.
5. On success the record is flattened by `resolve_periods()` to the values in force today and
   replaces that city in the block. On failure **nothing is replaced**: the city keeps the tariff
   it had, and the reason is logged and sent to Telegram.

### Which model reads the sources

The model is chosen per country, by `settings.llm` in its config. The pipeline talks to an
`Extractor` from `common/llm/` and never learns which provider is behind it, so moving a country
to another provider is a config edit.

| `provider` | Module | Reads a PDF | Web search |
|---|---|---|---|
| `gemini` | `common/llm/gemini.py` | as bytes, scans included | yes |
| `openai_compatible` | `common/llm/openai_compatible.py` | the text layer via `common/pdf.py`, tables written out row by row, every cell covered by a merge — across or down — given the text of the cell covering it; a scan is rendered to page images and sent to `vision_model` | no |

`openai_compatible` covers every API speaking the OpenAI chat-completions format: Qwen on Alibaba
Cloud Model Studio (Russia, today), OpenRouter, GLM, a local server.

| Field | Meaning |
|---|---|
| `model` | The text model. |
| `vision_model` | The model for scans and images. Without it a scanned source fails with a clear reason. |
| `api_key_env` | Name of the env variable holding the key. The key itself is never in config. |
| `base_url_env`, `base_url` | The endpoint. The env variable wins, so an account-specific address stays out of this public repository; `base_url` is the fallback. |
| `json_mode` | Ask for a JSON object. Text requests only. |
| `timeout_seconds` | Per call. A large decree takes minutes to read, far longer than fetching a page. |
| `extra_params` | Put into the request as is — e.g. `enable_thinking: false` for Qwen, which keeps reasoning tokens off the bill. |

A source may override `model`, `json_mode` and `extra_params` of `settings.llm` next to its URLs.
The country's settings are chosen for the price of reading every city; a source too dense for them
gets a stronger setup of its own rather than moving the whole country to the expensive one.

Moscow's tariff menu was the case in point while Moscow was collected: eighteen columns. `qwen3-max`
read its hot water row correctly as it was. Its heat row came back wrong three times — from the text with the default model,
from the text with `qwen3-max`, from page images with the vision model — and right only with
reasoning switched on: `extra_params: {"enable_thinking": true, "thinking_budget": 8000}` together
with `json_mode: false`, because Qwen does not answer when both reasoning and JSON mode are on.
Reasoning is paid output — that call cost 8.7k output tokens against about 0.5k without it — so it
belongs to the one source that needs it, and `thinking_budget` caps it. A model override applies to
text requests; a scan always goes to `vision_model`.

A config without `settings.llm` is read the old way: Gemini, `settings.gemini_model`. Every provider
a country uses needs its key as a GitHub secret, passed to the job in
`.github/workflows/fetch_tariffs.yml`.

Every call is logged with its token count and a run ends with a total, which also goes into the
Telegram report: a source that suddenly costs ten times more shows up there, not on the invoice.

### Testing one city

A model call is paid for, and collecting a whole country to check a fix in one city is how a
month's credits disappear in a day. `src/run_city.py` runs part of a country:

```bash
python src/run_city.py ru yekaterinburg                  # every service of one city
python src/run_city.py ru yekaterinburg --block water    # one service
python src/run_city.py ru --block electricity            # the country-wide tariff
python src/run_city.py ru yekaterinburg --write          # publish just this city
```

By default it is a dry run: it fetches, extracts and validates, prints what would be published and
every reason something would not, and writes nothing — no file, no registry entry, no Telegram
message. `--write` publishes the selected cities into the country file, keeps every other city as
published, and rebuilds the index. It refuses to run without a city, except for the country-wide
electricity block, so it cannot collect a whole country by accident.

The order of work is fixed: make every fix first, then test the cities it touches, then — only with
the maintainer's agreement — collect the whole country.

### Proving a source from GitHub

A source is proven only from the machine the pipeline runs on. Several Russian sites answer one
machine and time out for a GitHub runner — the Yekaterinburg водоканал and gov.spb.ru opened from a
developer's machine and not from GitHub. The pipeline runs in GitHub Actions and nowhere else, with
no other infrastructure, so a source GitHub cannot reach is replaced, or its city is retired.

`src/check_sources.py` downloads sources and calls no model, so it costs nothing:

```bash
python src/check_sources.py ru                               # every URL in config/ru/sources.json
python src/check_sources.py --url https://example.org/page   # a candidate, before it goes into config
```

The **Check Sources** workflow runs the same from a GitHub runner: Actions → Check Sources → Run
workflow, with a country code or candidate URLs. For every URL it prints whether it answered, its
type and size, how many price-like numbers it carries, and it warns when a page reads like a "page
not found" served with status 200.

**No URL goes into config without having been downloaded and read first.** Guessed addresses were
tried once — three of them on domains that do not exist, one a disguised 404 — and each was a wasted
run.

**A source is a page that is updated in place.** The supplier's, the settlement centre's or the
regulator's tariff page, which will carry next year's figures at the same address. A document tied
to a date is not a source, however good its numbers are today: a decree PDF, a tariff menu "for
2026–2028", a news article about "new tariffs from 1 October". It stops being current on a known
day and never learns the next tariff. The file needs only the tariff in force; a page that shows a
change in advance is welcome, but chasing announced future values is not a reason to add a URL.
The same goes for hints: a hint that names this year's decree or dates stops matching the page once
it is updated. When removing dated sources leaves a service with none, the service — or the whole
city — goes to `retired_cities`; that is how Moscow and Saint Petersburg left the Russian file.

Text is decoded before anything else looks at it. UTF-8 wins whenever the bytes decode as UTF-8,
and the encoding the response declares is used only when they do not: a single-byte decoder accepts
any bytes at all and turns real UTF-8 into mojibake, while the reverse practically never happens.
Judging the result by how much Cyrillic it contains — the earlier rule — is what broke Azerbaijani
and Armenian pages, which carry none: a correct decode looked like a failure and the page reached
the model as "tariflЙ™r".

Some sites send their certificate without the intermediate one that links it to a trusted root. A
browser fetches the missing link by itself, Python does not, and the site fails with "unable to get
local issuer certificate". `config/certs/` keeps such intermediates, each downloaded from the
address the site's own certificate names for its issuer, and `common/fetching.py` trusts them in
addition to the standard roots. Verification is not weakened: every chain still has to end at a
standard root. The Kazan водоканал is read this way.

### Captions and the report

* A decree reference is normalised — spacing, case, stray escaping — and when the tariff is the one
  already published, same period and same number, the published caption is kept. A page often lists
  several decrees and the model names a different one on each run; the caption should change when
  the tariff does, not whenever the page is read again.
* Where one city has several suppliers listed separately, the report names the supplier too, so a
  failure can be traced to one of Yekaterinburg's three heat companies.
* A service declared for a city with an empty list of URLs is reported on every run as having no
  source, instead of silently keeping a stale tariff.

### Renaming a supplier

`city_registry.json` never loses a code, but a supplier's name can change: Nizhny Novgorod's
водоканал and heat company merged into АО «ОКО» in November 2025. With the maintainer's agreement the
registry key is renamed and the code kept, and config names the new supplier. Users keep their saved
selection; only the name shown next to it changes.

### Why the prompt carries the date and a hint

Both exist because of mistakes that were made and caught, not as decoration.

* **The date.** A decree lists a decade of periods. A model with no idea what today is returns the
  ones from two years ago, and an old tariff extracted from a real document passes every structural
  check there is.
* **Supplier aliases.** When `supplier_aka` is set, the instruction tells the model the other names
  the company goes by. Without it a name the model was not told about reads as "the tariff is not
  here": the Novosibirsk heat company is published as АО «СИБЭКО» and printed as НТСК, and two
  models in turn returned an empty answer.
* **The block's `source_url`.** It is filled from config on every run: the single page, when every
  city of the block reads the same one, and an empty string otherwise. Nothing used to write it, so
  the published file went on naming pages that had been dropped from config — Russia still claimed
  `mosvodokanal.ru` months after Moscow was retired.
* **Tax the source leaves out (`vat_percent`).** Some regulators print the net tariff and the
  household pays it with VAT added: GNERC publishes Georgian electricity "including VAT" and
  Georgian water "excluding VAT" on neighbouring pages. The model returns the figure as printed and
  the code multiplies, because arithmetic asked of a model is arithmetic nobody can check. It is set
  per source, never per country — and it stays absent wherever the printed price is already final,
  as in Moldova, where household utilities are VAT-exempt.
* **A component that is legitimately zero (`zero_allowed`).** Bălți charges water and sewerage as
  one figure, so its `sewage` comes back as zero and the validator would otherwise reject the city:
  a tariff of nothing is the usual shape of a failed extraction. Listing the field in config says
  the zero is the truth for this city and nowhere else.
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
* a two-rate heat tariff's standing charge in the wrong unit. The schema carries it in currency per
  Gcal/hour, decrees often print it in thousands; the model reports which (`rate_gcal_hour_in_thousands`)
  and the code multiplies, so Nizhny Novgorod's 420.91 thousand is published as 420910;
* hot water whose components do not multiply out to the stated price. Two-component tariffs are
  folded to one price per m³ **by `fold_hot_water()`, not by the model** — a number the code
  computed can be checked, a number the model computed cannot;
* a supplier the source does not name. Compared after dropping the legal form and any parenthesised
  qualifier, so «МУП "Водоканал г. Екатеринбурга"» matches «МУП «Водоканал»» while «АО "СИБЭКО"»
  does not match «ООО "Новосибирская теплосетевая компания"». Where the source uses an abbreviation
  that cannot be matched to its expansion, config lists it under `supplier_aka`;
* a period with no parsable start date, or two periods starting the same day;
* a period starting on a day the country's regulators never start one — `period_starts` in
  `validation`, for Russia 1 January, 1 July, 1 October and 1 December. Reading Yekaterinburg's
  water from a settlement centre's page, the model returned a period "from 1 September" with the
  October numbers: the page has no such date. Every other check passed it — no published period
  to compare with, a plausible 10% rise, a start already in the past;
* a source with only future periods. It has no tariff in force today, and publishing its first
  period now would show an October tariff in September; the city keeps its value until then;
* **an already published period that comes back with a different number**, beyond
  `same_period_tolerance`. A regulator does not reprice a period it has set, so a new number for
  the same dates means the model read another column — the tariff without VAT, another year,
  another consumer group. It is caught by nothing else: the wrong number is a real tariff from
  a real document, usually within a few percent of the right one. This is how the Moscow heat
  tariff came back without VAT when Russia was first read through a text-only model. A genuine
  correction by the regulator is accepted by hand: `src/run_city.py … --accept-period-changes`;
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

An entry `<code>.<block>` retires one service of a city whose other services are still collected,
and that block is removed from the city's `sources`. Kazan's heating went this way: no source
reachable from GitHub carries the tariff in force, and the file held a made-up 2024 figure, while
Kazan's water keeps being read from the водоканал.

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
