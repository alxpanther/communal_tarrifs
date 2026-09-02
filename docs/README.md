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
| JSON specification / Спецификация JSON | [en/JSON_SPECIFICATION.md](en/JSON_SPECIFICATION.md) | [ru/JSON_SPECIFICATION.md](ru/JSON_SPECIFICATION.md) | The output contract: every field, Kotlin DTOs, billing formulas, country index |
| Adding a country / Добавление страны | [en/ADDING_A_COUNTRY.md](en/ADDING_A_COUNTRY.md) | [ru/ADDING_A_COUNTRY.md](ru/ADDING_A_COUNTRY.md) | Layout, output contract and checklist for a new country pipeline |
| Documentation rules / Правила документации | [en/DOCUMENTATION_RULES.md](en/DOCUMENTATION_RULES.md) | [ru/DOCUMENTATION_RULES.md](ru/DOCUMENTATION_RULES.md) | How docs and structure are maintained, bilingual parity, frozen contracts |
| Android brief / Задание для Android | [en/ANDROID_MIGRATION.md](en/ANDROID_MIGRATION.md) | [ru/ANDROID_MIGRATION.md](ru/ANDROID_MIGRATION.md) | Work brief for the app side: hot water and heating |
| Armenia tariffs / Тарифы Армении | [en/am/README.md](en/am/README.md) | [ru/am/README.md](ru/am/README.md) | Armenia tariff pipeline specification |
| Azerbaijan tariffs / Тарифы Азербайджана | [en/az/README.md](en/az/README.md) | [ru/az/README.md](ru/az/README.md) | Azerbaijan tariff pipeline specification |
| Moldova tariffs / Тарифы Молдовы | [en/md/README.md](en/md/README.md) | [ru/md/README.md](ru/md/README.md) | Moldova tariff pipeline specification |
| Uzbekistan tariffs / Тарифы Узбекистана | [en/uz/README.md](en/uz/README.md) | [ru/uz/README.md](ru/uz/README.md) | Uzbekistan tariff pipeline specification |
| Kazakhstan tariffs / Тарифы Казахстана | [en/kz/README.md](en/kz/README.md) | [ru/kz/README.md](ru/kz/README.md) | Kazakhstan tariff pipeline specification |
| Belarus tariffs / Тарифы Беларуси | [en/by/README.md](en/by/README.md) | [ru/by/README.md](ru/by/README.md) | Belarus tariff pipeline specification |

Other entry points / Остальные точки входа:

* [`../README.md`](../README.md) — setup and operation guide, Russian, for humans.
* [`../CLAUDE.md`](../CLAUDE.md) — what an AI agent must read before touching anything.
* [`tariffs_index.json`](tariffs_index.json) — the list of countries whose tariffs are published.
* [`tariffs_ua.json`](tariffs_ua.json), [`tariffs_am.json`](tariffs_am.json), [`tariffs_az.json`](tariffs_az.json), [`tariffs_md.json`](tariffs_md.json), [`tariffs_uz.json`](tariffs_uz.json), [`tariffs_kz.json`](tariffs_kz.json), [`tariffs_by.json`](tariffs_by.json) — the published data files themselves.
