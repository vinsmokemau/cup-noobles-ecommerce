"""The SAT catalog codes offered at checkout (SPEC.md §4.4 "CFDI catalog codes", D16).

The codes come from `api/fixtures/cfdi_catalogs.json`. Until the accountant confirms the subset,
the file holds sample codes and the `[PLACEHOLDER]` comment (§2.5).
"""

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

CATALOG_PATH = Path(settings.BASE_DIR) / "fixtures" / "cfdi_catalogs.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def tax_regime_codes() -> set[str]:
    return {item["code"] for item in _load()["regimen_fiscal"]}


def cfdi_use_codes() -> set[str]:
    return {item["code"] for item in _load()["uso_cfdi"]}


def public_catalogs() -> dict[str, list[dict[str, str]]]:
    """The two lists the checkout offers, as `{code, name}` rows. The file's `$comment` and
    `title` stay server-side: they mark the sample as a placeholder (§2.5)."""
    data = _load()
    return {
        "regimen_fiscal": [
            {"code": item["code"], "name": item["name"]}
            for item in data["regimen_fiscal"]
        ],
        "uso_cfdi": [
            {"code": item["code"], "name": item["name"]} for item in data["uso_cfdi"]
        ],
    }
