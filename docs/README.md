# Documentation index / Индекс документации

Documentation is kept in two languages. **English is canonical** — AI agents read `docs/en/` and
only `docs/en/`. Russian is a mirror for the human maintainer. Both versions must always be
identical in meaning.

Документация ведётся на двух языках. **Английская версия каноническая** — AI-агенты читают
`docs/en/` и только его. Русская — зеркало для владельца проекта. Обе версии обязаны всегда
совпадать по смыслу.

| Page / Страница | English (canonical) | Русский (зеркало) | About / О чём |
|---|---|---|---|
| Project structure / Структура проекта | [en/PROJECT_STRUCTURE.md](en/PROJECT_STRUCTURE.md) | [ru/PROJECT_STRUCTURE.md](ru/PROJECT_STRUCTURE.md) | Directory map, responsibilities, environment variables, where to put new things |
| Architecture / Архитектура | [en/ARCHITECTURE.md](en/ARCHITECTURE.md) | [ru/ARCHITECTURE.md](ru/ARCHITECTURE.md) | Pipeline stages, validation, `city_code` registry, manual overrides, deployment |
| JSON specification / Спецификация JSON | [en/JSON_SPECIFICATION.md](en/JSON_SPECIFICATION.md) | [ru/JSON_SPECIFICATION.md](ru/JSON_SPECIFICATION.md) | The output contract: every field, Kotlin DTOs, billing formulas |
| Adding a country / Добавление страны | [en/ADDING_A_COUNTRY.md](en/ADDING_A_COUNTRY.md) | [ru/ADDING_A_COUNTRY.md](ru/ADDING_A_COUNTRY.md) | Target layout, output contract and checklist for a new country pipeline |
| Documentation rules / Правила документации | [en/DOCUMENTATION_RULES.md](en/DOCUMENTATION_RULES.md) | [ru/DOCUMENTATION_RULES.md](ru/DOCUMENTATION_RULES.md) | How docs and structure are maintained, bilingual parity, frozen contracts |
| Android brief / Задание для Android | [en/ANDROID_MIGRATION.md](en/ANDROID_MIGRATION.md) | [ru/ANDROID_MIGRATION.md](ru/ANDROID_MIGRATION.md) | Work brief for the app side: hot water and heating |

Other entry points / Остальные точки входа:

* [`../README.md`](../README.md) — setup and operation guide, Russian, for humans.
* [`../CLAUDE.md`](../CLAUDE.md) — what an AI agent must read before touching anything.
* [`tariffs_ua.json`](tariffs_ua.json) — the published data file itself.
