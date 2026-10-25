"""`manage.py seed_demo`: the minimal demo catalog, one product per launch type (SPEC.md T3.7).

For local development and the test suite. Idempotent. T15.1 expands it into the full demo dataset
and adds `--reset`.
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.demo import seed_demo_products


class Command(BaseCommand):
    help = "Seed one [DEMO] product per launch type (development and tests only)."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ENABLED:
            raise CommandError("seed_demo runs only where DEV_TOOLS_ENABLED is on")
        created = seed_demo_products()
        self.stdout.write(f"seed_demo: {len(created)} product(s) created")
