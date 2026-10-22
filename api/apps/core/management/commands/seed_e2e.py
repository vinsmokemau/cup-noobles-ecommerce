"""Seed the data the end-to-end specs read (SPEC.md §4.6, T1.13b).

The command writes `var/e2e/manifest.json`, which the Playwright `seed` fixture reads so
specs never hard-code slugs, SKUs or emails. It is idempotent. Phase 1 has no models to
seed; each later phase adds its own data and T15.2 completes it.
"""

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand


def manifest_path() -> Path:
    return Path(settings.BASE_DIR) / "var" / "e2e" / "manifest.json"


class Command(BaseCommand):
    help = "Seed the end-to-end data and write var/e2e/manifest.json."

    def handle(self, *args: Any, **options: Any) -> None:
        manifest: dict[str, Any] = {}
        path = manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"seed_e2e: wrote {path}")
