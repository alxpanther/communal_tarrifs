# Documentation and structure rules

> **Language:** English — canonical version. AI agents read this file, not the Russian one.
> Russian mirror: [../ru/DOCUMENTATION_RULES.md](../ru/DOCUMENTATION_RULES.md). Both files must stay identical in meaning.

These rules are binding for everyone touching the repository — the maintainer, external
contributors and AI agents alike. They exist so that a change to the code can never quietly
invalidate the documentation.

---

## 1. Two languages, one meaning

| | English (`docs/en/`) | Russian (`docs/ru/`) |
|---|---|---|
| Status | **Canonical** | Mirror |
| Audience | AI agents, external contributors | The maintainer |
| Read by an agent picking up a task | Yes, this is the only version to read | No |
| May contain information the other lacks | **No** | **No** |

Rules:

1. **Write the English page first**, then mirror it into Russian. The English wording is the one
   that gets referenced from code comments and from agent instructions.
2. **The two versions must be identical in meaning**, section by section, table by table, example by
   example. Same structure, same order, same numbers, same file names. Only the prose language
   differs.
3. **Never update one language only.** A change that lands in `docs/en/` without the matching change
   in `docs/ru/` is an incomplete change. The same holds in reverse.
4. Every page starts with the language header block used at the top of this file: which version is
   canonical, and a link to its counterpart.
5. Identifiers, field names, file paths, JSON snippets, code and CLI commands stay **untranslated**
   in both versions. Ukrainian company names, city names and quoted decrees are also kept verbatim —
   they are data, not prose.
6. `README.md` in the repository root stays Russian: it is the human landing page. It must link to
   `docs/en/` and `docs/ru/`, and its content must not contradict them.

## 2. What an AI agent reads before starting a task

In this order, and only the English versions:

1. [`CLAUDE.md`](../../CLAUDE.md) — the entry point.
2. [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) — where everything lives.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the pipeline works and which invariants hold.
4. The page for the task at hand: [`JSON_SPECIFICATION.md`](JSON_SPECIFICATION.md) for anything
   touching the output format, [`ADDING_A_COUNTRY.md`](ADDING_A_COUNTRY.md) for a new country.

Reading `docs/ru/` instead is a mistake: the Russian pages exist for the maintainer to read
comfortably, not as a second source of truth.

## 3. When documentation must be updated

Update the docs **in the same change** that touches the code, never as a follow-up:

| Change | Pages that must be updated |
|---|---|
| New or removed file / directory | `PROJECT_STRUCTURE.md` (both languages) |
| New pipeline stage, new validation, changed fallback behaviour | `ARCHITECTURE.md` |
| Any change to the output JSON — new field, new block, changed meaning | `JSON_SPECIFICATION.md`, plus `README.md`, plus a note for the Android side. **Requires the maintainer's agreement first**, see section 5 |
| New configuration key in `config/sources.json` | `README.md` and `ARCHITECTURE.md` |
| New country added | `ADDING_A_COUNTRY.md`, `PROJECT_STRUCTURE.md`, `docs/README.md` |
| New documentation page | `docs/README.md` index, both languages |

A pull request that changes behaviour without touching documentation is incomplete and should be
rejected.

## 4. Structure rules

1. **Configuration, not constants.** URLs, model names and timeouts belong in `config/`. A URL
   hardcoded in Python is a defect regardless of how well it works.
2. **Generated files are never hand-edited.** `docs/tariffs_ua.json` and
   `assets/tariffs_ua_default.json` are overwritten on every run; force values through
   `manual_override`.
3. **Temporary work goes to `tmp/`** in the repository root, and the folder is deleted when the task
   ends. Debug dumps, benchmark output and scratch scripts must not stay in `src/`, `docs/` or the
   repository root.
4. **One responsibility per module.** Telegram delivery lives in `telegram_notifier.py`, tariff
   logic in the country pipeline. Do not spread I/O side effects around.
5. **Code comments are English.** Regardless of the language used in chat or in the Russian docs.
6. **`docs/` is a web root.** Everything committed there is published by GitHub Pages. No secrets,
   no scratch files.

## 5. Frozen contracts

Two things in this repository are contracts with the Android application, and breaking either of
them breaks installed apps in the field:

**The output JSON schema.** Renaming, removing or re-typing an existing field is forbidden without
the maintainer's prior agreement. Adding a new field is allowed, but the maintainer must be told
explicitly, because the app side needs a matching change. Document every addition in
`JSON_SPECIFICATION.md` in the same change.

**The `city_code` values.** Once assigned, a code is permanent: the app stores it as the user's
saved selection. `config/city_registry.json` must be committed, and codes may only be edited
deliberately together with a migration on the app side.

## 6. Style of a documentation page

* Answer "what is this and what do I do with it", not "what does line 42 do".
* Prefer tables for field-by-field and file-by-file listings.
* Every claim about behaviour must be true of the code as it exists now. If you describe something
  that is planned rather than implemented, label it explicitly as planned.
* Refer to functions and files by name, not by line number — line numbers rot immediately.
* Keep worked examples: a real `manual_override` block or a real JSON fragment is worth a page of
  description.
