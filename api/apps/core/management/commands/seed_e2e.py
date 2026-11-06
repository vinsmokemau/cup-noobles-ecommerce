"""Seed the data the end-to-end specs read (SPEC.md §4.6, T1.13b).

The command writes `var/e2e/manifest.json`, which the Playwright `seed` fixture reads so
specs never hard-code slugs, SKUs or emails. It is idempotent. Each phase adds its own
data (Phase 12: the catalog) and T15.2 completes it.
"""

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Customer
from apps.catalog.e2e_seed import seed_catalog
from apps.shipping.seeds import seed_shipping, seed_states

# A fictional staff account for the specs that need a staff session (T12.15). It exists only where
# dev tools are on, so a production database never holds a known password.
STAFF_EMAIL = "staff-e2e@example.com"
STAFF_PASSWORD = "e2e-staff-not-a-secret"


def seed_staff() -> dict[str, str]:
    if not settings.DEV_TOOLS_ENABLED:
        raise CommandError("seed_e2e runs only where DEV_TOOLS_ENABLED is on")
    staff, _ = Customer.objects.get_or_create(
        email=STAFF_EMAIL, defaults={"is_staff": True, "is_superuser": True}
    )
    staff.is_staff = staff.is_superuser = staff.is_active = True
    staff.set_password(STAFF_PASSWORD)
    staff.save()
    return {"email": STAFF_EMAIL, "password": STAFF_PASSWORD}


def manifest_path() -> Path:
    return Path(settings.BASE_DIR) / "var" / "e2e" / "manifest.json"


class Command(BaseCommand):
    help = "Seed the end-to-end data and write var/e2e/manifest.json."

    def handle(self, *args: Any, **options: Any) -> None:
        # The checkout specs (Phase 13) quote shipping and look up postal codes.
        seed_states()
        seed_shipping()
        call_command("load_postal_codes", verbosity=0)
        manifest: dict[str, Any] = {"catalog": seed_catalog(), "staff": seed_staff()}
        path = manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"seed_e2e: wrote {path}")
