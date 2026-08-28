"""Filesystem layout of the repository.

Every path used by any country pipeline is derived here, so a country code is the only
thing a pipeline needs to know about where its files live.
"""

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CONFIG_DIR = os.path.join(REPO_ROOT, "config")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
DIST_DIR = os.path.join(REPO_ROOT, "dist")

# Registry of every published country, shared by all pipelines and by the index builder.
COUNTRIES_PATH = os.path.join(CONFIG_DIR, "countries.json")


def country_config_dir(code: str) -> str:
    """config/<cc>/ — hand-edited input of one country."""
    return os.path.join(CONFIG_DIR, code.lower())


def sources_path(code: str) -> str:
    return os.path.join(country_config_dir(code), "sources.json")


def registry_path(code: str) -> str:
    return os.path.join(country_config_dir(code), "city_registry.json")


def docs_output_path(code: str) -> str:
    """docs/tariffs_<cc>.json — the published file, flat at the web root.

    The layout is dictated by the Android app: with no explicit `path` in the index it
    looks for exactly this name at the root of GitHub Pages.
    """
    return os.path.join(DOCS_DIR, f"tariffs_{code.lower()}.json")


def assets_output_path(code: str) -> str:
    """assets/tariffs_<cc>_default.json — offline fallback bundled into the app."""
    return os.path.join(ASSETS_DIR, f"tariffs_{code.lower()}_default.json")
