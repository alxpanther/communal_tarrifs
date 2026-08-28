# Agent instructions

See [`CLAUDE.md`](CLAUDE.md) — it is the single entry point for every AI agent working in this
repository, regardless of the tool. Read it before the first tool call.

Short version: the English documentation in [`docs/en/`](docs/en/) is canonical and is the only
version an agent reads; [`docs/ru/`](docs/ru/) is a Russian mirror for the human maintainer and must
stay identical in meaning. The output JSON schema and the assigned `city_code` values are frozen
contracts with the Android application. The generator publishes several countries: one file per
country plus a country index, driven by [`config/countries.json`](config/countries.json).
