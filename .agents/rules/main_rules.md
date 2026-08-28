---
trigger: always_on
---

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

- Run assemblies for testing only with the --debug switch, no need to --release the version yourself.
- When debugging or testing an application for assembly, never create a release version.

## Translation

- Never make inscriptions hard-coded into the application. Use translation files in arb format.

## Communication

1. If you are unsure about the requirements or direction of development, ask specific questions.
2. When proposing multiple implementation options, clearly explain the advantages and disadvantages of each.

## Comments in code

CRITICAL! Write all code comments on English.

## JSON file with tarrifs

CRITICALLY INPORTANT! Change the structure of the application file with tariffs and the description of this file as a last resort, since it determines how the Android application will process this file.
If you want to change something in the structure, then first agree with me. You can add new fields, but you still need to inform me about this additionally, since corrections will need to be made to the Android application.

## Documentation and project structure

CRITICAL! Documentation is part of the deliverable, not a follow-up task.

- Before starting a task in this repository, read `CLAUDE.md` in the root, then
  `docs/en/PROJECT_STRUCTURE.md`, `docs/en/ARCHITECTURE.md` and `docs/en/DOCUMENTATION_RULES.md`.
  Read the page relevant to the task after that.
- Documentation exists in two languages. `docs/en/` is CANONICAL and is the ONLY version an agent
  reads. `docs/ru/` is a mirror for the human maintainer. Never use the Russian pages as a source of
  truth; if the two versions disagree, report it instead of choosing one.
- Both language versions must stay identical in meaning — same sections, same tables, same examples,
  same numbers. Write or edit the English page first, then mirror it into Russian. Changing only one
  language is an incomplete change.
- Any change that affects behaviour, structure or configuration updates the documentation in the
  SAME change: new or removed file → `PROJECT_STRUCTURE.md`; new pipeline stage, validation or
  fallback → `ARCHITECTURE.md`; new config key → `README.md` and `ARCHITECTURE.md`; new page → the
  `docs/README.md` index. Both languages, every time.
- `README.md` in the root stays Russian and must not contradict `docs/`.
- Keep the structure rules: URLs, model names, timeouts, tariff values and country names live in
  `config/`, never hardcoded in Python; generated files (`docs/tariffs_<cc>.json`,
  `assets/tariffs_<cc>_default.json`, both copies of `tariffs_index.json`) are never hand-edited —
  force values through `manual_override`; one responsibility per module; anything two countries do
  the same way lives in `src/common/`, not copied.
- An assigned `city_code` in `config/<cc>/city_registry.json` is permanent and must never be
  rewritten: the Android application stores it as the user's saved selection.
- When adding support for another country, follow `docs/en/ADDING_A_COUNTRY.md` and do not deviate
  from the layout and the output contract described there without agreeing it with me first.
