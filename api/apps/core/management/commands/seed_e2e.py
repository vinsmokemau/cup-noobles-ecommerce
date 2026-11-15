"""Seed the data the end-to-end specs read (SPEC.md §4.6, T1.13b, T15.2).

`seed_e2e` is `seed_demo` (the 15.A dataset) plus the data owned by individual specs: the
journey products (`apps/core/e2e_journeys.py`) and the catalog of the Phase 12 and 13 specs
(`apps/catalog/e2e_seed.py`). It writes `var/e2e/manifest.json`, which the Playwright `seed`
fixture reads so specs never hard-code slugs, SKUs, emails or order numbers. It is idempotent,
and refuses to run unless `DEV_TOOLS_ENABLED`.
"""

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Customer
from apps.catalog.e2e_seed import seed_catalog
from apps.catalog.models import Product
from apps.core import demo
from apps.core.e2e_journeys import product_manifest, seed_journeys

# A fictional staff account for the specs that need a staff session (T12.15). It exists only where
# dev tools are on, so a production database never holds a known password.
STAFF_EMAIL = "staff-e2e@example.com"
STAFF_PASSWORD = "e2e-staff-not-a-secret"

# The manifest's names for the 15.A products.
DEMO_PRODUCT_KEYS = {
    "tcg": f"{demo.DEMO_PREFIX} Caja de sobres TCG",
    "fundas": f"{demo.DEMO_PREFIX} Fundas para cartas",
    "sudadera": f"{demo.DEMO_PREFIX} Sudadera",
    "playera": f"{demo.DEMO_PREFIX} Playera",
    "figura": f"{demo.DEMO_PREFIX} Figura",
    "artbook": f"{demo.DEMO_PREFIX} Artbook",
}
DEMO_HIDDEN_KEYS = {
    "draft": f"{demo.DEMO_PREFIX} Accesorio en borrador",
    "archived": f"{demo.DEMO_PREFIX} Accesorio archivado",
}
# The guest order history, in the order `seed_demo` creates it (15.A).
DEMO_ORDER_KEYS = ("completed", "oxxo", "cfdi")


def seed_staff() -> dict[str, str]:
    staff, _ = Customer.objects.get_or_create(
        email=STAFF_EMAIL, defaults={"is_staff": True, "is_superuser": True}
    )
    staff.is_staff = staff.is_superuser = staff.is_active = True
    staff.set_password(STAFF_PASSWORD)
    staff.save()
    return {"email": STAFF_EMAIL, "password": STAFF_PASSWORD}


def demo_manifest() -> dict[str, Any]:
    """The 15.A rows a spec may need: slugs, SKUs, emails, the dev password and order numbers."""

    def products(keys: dict[str, str]) -> dict[str, Any]:
        return {
            key: product_manifest(Product.objects.get(name=name))
            for key, name in keys.items()
        }

    orders = demo.demo_orders()[: len(DEMO_ORDER_KEYS)]
    return {
        "staff": {"email": demo.STAFF_EMAIL, "password": demo.DEV_PASSWORD},
        "guest": {"email": demo.DEMO_EMAIL},
        "products": products(DEMO_PRODUCT_KEYS),
        "hidden": products(DEMO_HIDDEN_KEYS),
        "orders": {
            key: order.number
            for key, order in zip(DEMO_ORDER_KEYS, orders, strict=True)
        },
    }


def manifest_path() -> Path:
    return Path(settings.BASE_DIR) / "var" / "e2e" / "manifest.json"


class Command(BaseCommand):
    help = "Seed the demo dataset and the end-to-end data, and write var/e2e/manifest.json."

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ENABLED:
            raise CommandError("seed_e2e runs only where DEV_TOOLS_ENABLED is on")
        # The 15.A dataset, with the states, the warehouse, the shipping rates and the postal
        # codes the checkout needs. It also checks that the payment and carrier mocks are on.
        call_command("seed_demo", stdout=self.stdout)
        # The journeys before the catalog: the catalog lists the newest products first, so on a
        # new database the products the Phase 12 specs look for stay on its first page.
        manifest: dict[str, Any] = {
            "demo": demo_manifest(),
            "journeys": seed_journeys(),
            "catalog": seed_catalog(),
            "staff": seed_staff(),
        }
        path = manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"seed_e2e: wrote {path}")
