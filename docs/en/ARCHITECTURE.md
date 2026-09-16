# Architecture of the tariff pipeline

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/ARCHITECTURE.md](../ru/ARCHITECTURE.md). Both files must stay identical in meaning; see [DOCUMENTATION_RULES.md](DOCUMENTATION_RULES.md).

One entry point for everything: `src/run_country.py`. It is a batch job — it starts, runs the
pipeline of every requested country one after another, rebuilds the country index, notifies
Telegram, and exits. There is no server, no database, no state other than the generated JSON files
and the `config/<cc>/city_registry.json` registries.

Sections 2–6 describe the Ukrainian pipeline, which is the richest one and the reference for
everything else. Section 8 covers the config-declared pipeline, which five countries are still waiting to leave,
section 8a the per-city pipeline that collects Russia, Armenia, Azerbaijan, Moldova, Georgia and
Tajikistan, and section 9 the country index.

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

Read by the shared electricity module, `common/electricity.py`, exactly as for every other country
(section 8a, "Electricity"): `extract_electricity()` hands it `electricity.source` from
`config/ua/sources.json` and keeps the previous block when the reading is rejected. Ukraine prints
its zone prices next to the zone coefficients of the Cabinet decree, and electric heating by season.

### `water`

The heaviest path, `extract_water_tariffs()`:

1. `water_page_rows()` reads every supplier row off the flattened page text — one table row per
   line, cells split by `|` — without trusting the layout: the first cell is the supplier, the first
   three number cells are supply, sewage and total, whatever empty cells stand between them, and the
   period is the cell with a date. minfin has changed its markup before (an empty spacer cell before
   the total, in 2026), and a check that counted cells by position rejected a correct reading every
   time it did. `source_rows()` indexes the rows by their numeric triple.
2. The model receives the table — or the whole page text if minfin drops the table — and returns
   one record per city.
3. `validate_water_cities()` rejects the whole reading unless every condition holds:
   * each `water_supply / sewage / total_rate` triple stands on one row of the source **in that
     exact order**;
   * the number of returned rows equals the number of supplier rows on the page;
   * no source row is claimed twice;
   * `water_supply + sewage == total_rate` within `RATE_SUM_TOLERANCE`;
   * every component is below `MAX_WATER_RATE`.
4. `supplier` and the validity period are copied from the matched source row, overwriting whatever
   the model wrote. `decree_info` is composed from the period.
5. `resolve_city_identity()` assigns final `city_code` / `city_name` from the registry.

Since 2026 water tariffs are set by local authorities instead of NKREKP (Cabinet Resolution No. 716),
and minfin lists only the utilities whose new tariff it has picked up. So two more sources feed the
block, merged by supplier in `merge_water_cities()`:

* **A city's own page.** `cities.<code>.sources.water` in `config/ua/sources.json` — Kyiv, Kharkiv,
  Cherkasy, Uman — is read by the model through the shared per-city pipeline
  (`ai_pipeline.collect_block()`), with the same checks as any other country; it wins over minfin.
  `src/run_city.py ua <city> --block water` tests one (a dry run only: Ukraine is published whole).
* **What was published.** A utility minfin stops listing keeps its last published tariff instead of
  dropping out of the file — the maintainer's decision, because a city usually reappears on minfin
  once its new tariff is set.

A rejected minfin reading keeps the previous minfin cities and Telegram receives the list of
complaints; the cities with their own page are refreshed either way. The water tariffs of 2026 are two
to three times those of 2022, so `validation.water.max_change_ratio` is 3.0 for Ukraine.

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

### `gas`

`extract_gas_block()`, with no model call at all. `reference_sources.gas.url` is minfin's gas page;
its list "Ціни на газ по містах України" links one page per city (`gas_city_links()`), and each city
page carries three rigid tables:

* retail prices per supplier, a monthly and an annual column (`gas_supplier_rows()`) — every
  non-empty cell becomes a plan, `<supplier>_annual` or `<supplier>_monthly`;
* the delivery tariff of the city's network operator (`gas_distributor_rows()`) — one city record
  per operator, so Ternopil, with two, is published twice;
* the national consumption norms without a meter, Cabinet Resolution No. 143
  (`gas_norms()`), mapped to the published usage codes by `GAS_NORM_USAGES`.

The table caption "з 1.09.2026" is the date (`gas_page_date()`); an unchanged price keeps the date
and caption it was first published with, because minfin restamps the page every month.
`reference_sources.gas.default_supplier` names the default plan — Naftogaz, annual price. The
registry key is the network operator (section `gas_suppliers`): Naftogaz sells gas in every city,
the operator is what tells the cities apart.

A city page that does not open keeps its previous records. A page with no operator (occupied towns,
where minfin prints a supplier and nothing else) yields no record: a price without delivery would
understate the bill. The checks themselves live in `common/gas.py`, shared with every country.

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
* Gas is registered under the network operator where delivery is billed apart (section
  `gas_suppliers`), under the supplier elsewhere.
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
4. publishes `docs/` to GitHub Pages, with every country file also copied to its Cloudflare path
   (`<cc>/tariffs_<cc>.json`), so the mirror answers at both addresses.

One job does all countries, so two runs can never push to the same branch or deploy Pages at the
same time.

Four workflows share the repository:

| Workflow | Runs | Does |
|---|---|---|
| Fetch and Update Tariffs | on the 1st and the 25th, or by hand with country codes | collects, commits the files with `[skip ci]`, publishes to R2 and Pages |
| Publish Tariffs | on a push that changes a published file, or by hand | publishes the files already in the repository; no collection, no model call |
| Check Sources | by hand | downloads sources from a GitHub runner and reports which answer; no model call, nothing written |
| Collect Cities | by hand with a country, city codes, a service and "write" | runs `src/run_city.py` from a GitHub runner; a dry run by default, with "write" commits the named cities and starts Publish Tariffs. Countries read city by city only |

---

## 8. The deleted config-declared pipeline

Until September 2026 some countries had no collector at all: their numbers sat in
`config/<cc>/sources.json` → `manual_override` and `src/common/manual_pipeline.py` turned them into a
file. Every one of them has been moved to per-city collection (section 8a) and the module was
deleted. A country with no readable source is retired (section 8b), never typed in.

Two traps met while entering Russian tariffs, both of them general:

* **A supplier name is the registry key, so it must be unique inside a country.**
  `reconcile_cities()` matches on the normalized supplier name across the whole country, not per
  city. ПАО «Т Плюс» supplies heat in Samara and in Yekaterinburg alike, and the bare name would have
  dragged the Samara `city_code` onto the Yekaterinburg record. The city has to be part of the name:
  `ПАО "Т Плюс" (Екатеринбург)`.
* **Russian hot water is a two-component tariff** — roubles per m³ of carrier plus roubles per Gcal
  of heat — while `hot_water.cities[].rate` is a single price per m³. It is folded into one number
  as `carrier + energy × the regional norm for heating one m³` (Sverdlovsk oblast: 0.05131 Gcal/m³
  for a closed system). Since September 2026 the three numbers are published next to `rate`
  (`component_water`, `component_energy`, `heat_norm`), and a source marked `read_heat_norms` also
  publishes the region's norm for every kind of building (`heat_norms`).

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
| `common/electricity.py` | Electricity: every household tariff a source prints, validated and published as `plans`, with the older `base_rate` and `zones` taken from the default plan. Serves the country-wide tariff and a city's own. |
| `common/gas.py` | Gas: the checks and the published shape shared by every country, and the reading of a city's gas source by the model. |
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
Cloud Model Studio (Russia, Belarus, Kazakhstan, Armenia and Uzbekistan, today), OpenRouter, GLM, a local server.

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
python src/run_city.py ru kazan --block electricity      # a city's own electricity tariff
python src/run_city.py ru yekaterinburg --write          # publish just this city
python src/run_city.py am --block electricity --llm-from ru   # read with Russia's provider
```

`--llm-from` borrows `settings.llm` of another country for the run. Debugging a source on a cheap
provider and leaving the country on the one it runs in production on is the reason it exists; the
country's config is not touched.

By default it is a dry run: it fetches, extracts and validates, prints what would be published and
every reason something would not, and writes nothing — no file, no registry entry, no Telegram
message. `--write` publishes the selected cities into the country file, keeps every other city as
published, and rebuilds the index. It refuses to run without a city, except for the country-wide
electricity block, so it cannot collect a whole country by accident. It also refuses `--write` for a
country read from aggregate pages (`reference_sources` in config, i.e. Ukraine), which is published
only whole.

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
city — goes to `retired_cities`; that is how Moscow and Saint Petersburg left the Russian file until
pages updated in place were found for them.

Text is decoded before anything else looks at it. UTF-8 wins whenever the bytes decode as UTF-8,
and the encoding the response declares is used only when they do not: a single-byte decoder accepts
any bytes at all and turns real UTF-8 into mojibake, while the reverse practically never happens.
Judging the result by how much Cyrillic it contains — the earlier rule — is what broke Azerbaijani
and Armenian pages, which carry none: a correct decode looked like a failure and the page reached
the model as "tariflЙ™r".

Certificates are not checked, for any source — the owner's decision. What is read is a public
tariff page, and utility sites fail certificate checks in every possible way: expired, signed with a
key OpenSSL 3 refuses, missing an intermediate, issued for another name. Each of those used to cost a
country its data or put a certificate file into the repository that went stale within weeks. So
`common/fetching.py` verifies neither the chain nor the hostname and lowers the cipher security level;
a site that fails now fails for a real reason — it is down, blocks the request, or is gone.

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
* **A tariff published as a scan (`read_images`).** Tajikistan's ministry of energy posts the
  government's tariff decision as a photograph of its pages, so the page itself has nothing to read.
  With this set, the large images of every page fetched are downloaded too and handed to the vision
  model; the small ones — logos, banners, a magazine cover — are left alone, which is what the size
  threshold in `fetching.py` is for. Config keeps the stable page address, so next year's decision
  arrives on its own instead of the link rotting with the file name of this year's scan.
* **A tariff attached to a list page (`read_documents`).** Kyrgyzstan's fuel and energy regulator
  lists its tariff orders on one page and attaches each as a PDF; Belarus's energy association and
  the Gomel водоканал do the same, and Bishkek's city council gives every resolution a page of its
  own in one list. With this set, the documents every fetched page links to are downloaded too and
  handed to the model, which picks the decision in force by its date — which end of a list
  is the newest differs from site to site, so no position is trusted. `true` takes every PDF; a
  string takes only the links whose address or caption contains it — PDFs or pages alike — because a utility's tariff
  page also links application forms and decrees from 2009, and each PDF sent is paid for. When more
  links match than the cap in `fetching.py`, the cut is logged, and
  `{"match": ..., "from_end": true}` keeps the last ones instead of the first — Aktobe's water
  utility lists its decisions oldest first. `"count"` lowers the cap: the Chelyabinsk electricity
  supplier links a decree for every year since 2019, newest first, and only the first is read. A source with no `<a>` tags at all, such as a JSON feed
  (Veolia Energy Tashkent's news, Uzsuvtaminot's tariff API), yields its bare addresses as links. As with
  `read_images`, config keeps the stable page and the file name of this year's decision never
  enters it. `read_images` also understands a table pasted into the page as a `data:` image, as
  Bishkekteploset's is: such an image has no width or height to judge, so its decoded size is used.
* **The unit of a source (`unit`).** Hot water is priced per m³ almost everywhere, and that is the
  default. Belarus bills it as the heat used to warm the water, per Gcal, and publishes no price per
  cubic metre at all, so its sources say `"unit": "Gcal"` instead of making anyone convert.
* **Heat norms (`read_heat_norms`).** A region prints its norm for heating one m³ of hot water for
  every kind of building. Only a source marked with this option is asked for that table: few pages
  carry it, and every extra field asked of a page that has no answer is one more chance for the
  model to fill something from the wrong table.
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

### Electricity

A source rarely prints one electricity price. Armenia prices a flat by its monthly consumption and by
day and night; Belarus prices a flat with an electric stove apart from one with a gas stove, each for
one-, two- and three-zone meters; Azerbaijan adds a fixed monthly charge; Kazakhstan sets the bands
per resident; Ukraine prices electric heating by season. `common/electricity.py` reads all of it:

* **Config names the groups, the document gives the numbers.** `electricity.source.plans` (or
  `cities.<code>.sources.electricity.plans`) lists the groups of consumers to read, each with a
  stable code, a Russian name, a hint saying which rows of the document are its, and one of them
  marked `"default": true`. Config holds no coefficient, no zone schedule and no band limit: an
  earlier version kept zone coefficients there and derived zone prices from them, which is a
  typed-in tariff under another name.
* **The model returns every printed price as a row** — meter, zone, hours, band number and limits,
  season, price — and only what the page states: `tier_basis` and `tiers_per_resident` stay `null`
  unless the document says in so many words how bands apply.
* **The code does the arithmetic.** Prices printed in subunits (tetri, bani, qəpik, dirams, tyiyn)
  are flagged by the model as `prices_in_subunits` and divided by the code; `vat_percent` is added
  by the code. A monthly charge is printed in whole units and only gets the tax.
* **The older fields follow the default plan.** `base_rate` and `zones` are that plan's first band,
  in today's season; a meter kind the source does not price gets the base rate. When the plans of
  one source change on different dates the periods are split at every date, so the date published
  next to `base_rate` is walked back to the day that price actually started.
* **A city's own tariff.** A city whose electricity is priced by its region declares
  `sources.electricity` like any other service and is published in `electricity_cities`; its
  registry section is `electricity_suppliers`. Retiring it is `"<code>.electricity"` in
  `retired_cities`.

The electricity reading is rejected whole when a row has a meter and zone that do not go together,
a non-positive price or one above `validation.electricity.max_rate`, band limits that do not make
sense, a band without a number, a malformed season, a group not declared in config, the same price
twice, no prices of the default group, or no single-rate or day price to take `base_rate` from. The
guards every city block has apply to `base_rate` too: a change above `max_change_ratio`, and a new
number for a period already published.

A band's limits are the easiest number to misread without any check noticing: Krasnodar's decree
sets them per building type and per heating season, and the model returned two different sets on
two runs. Where that is so, the hint tells the model to leave the limits empty and fill only the
band number.

### Gas

Gas prices take more shapes than any other service, so `common/gas.py` publishes them as plans with
rates, the way electricity is, next to the plain `supplier` + `rate` + `distribution_rate` every city
carries. A city declares `sources.gas` like any other service:

* `plans` — code, Russian `name`, `hint`, one `"default": true`; optionally the plan's own
  `supplier`, `contract`, `usage` and `metered`, which come from config and never from the model;
* `separate_distribution: true` where delivery is priced apart — the model is then asked for the
  operator and its tariff, and a missing one rejects the reading; otherwise `distribution_rate` is
  `0.0`;
* `read_norms: true` where the source prints consumption norms without a meter.

The model returns every printed price with `price_per` — `"m3"` or `"thousand_m3"`; the code divides
by a thousand and adds `vat_percent`. A reading is rejected whole for a non-positive price or one
above `validation.gas.max_rate` per m³, nonsensical band limits, a band without a number, a
malformed season, a plan not declared in config, the same price twice, a norm that does not parse,
no price of the default plan, or a jump of the default price beyond `max_change_ratio`. The
registry section is `gas_suppliers`; retiring is `"<code>.gas"` in `retired_cities`; testing one
city is `src/run_city.py <cc> <city> --block gas`.

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
  last month's number gives it away. A block may set its own ratio next to its limits —
  `validation.water.max_change_ratio` — where a real change is larger: Ukraine's water tariffs grew
  two- to threefold in 2026 when local authorities took them over from NKREKP, so Ukraine allows 3.0
  for water.

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

## 8b. Retiring a country

`retired: true` in `config/countries.json` says nobody can refresh a country's tariffs any more.
It is stronger than `enabled: false`, which only hides a country inside the app while its file
stays published. A retired country is not collected — `run_country.py` skips it even when asked for
by name, because collecting it would recreate the file — it is left out of both index copies, and
`build_index.drop_retired()` deletes `docs/tariffs_<cc>.json` and
`assets/tariffs_<cc>_default.json`. Pages then stops serving it by itself, since it serves `docs/`
from the repository; the object in R2 is deleted by the workflow, the only place holding the
credentials for the bucket.

Turkmenistan is the first: its tariffs are set by presidential decree and published nowhere at all
— not by the ministry, not by the Ashgabat city hall, not in the state press, not in a legal
database. What was published for it were round numbers nobody could check, which is exactly what
this repository exists not to publish. The app side of a country disappearing is in
ANDROID_MIGRATION.md, section 2a.

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
