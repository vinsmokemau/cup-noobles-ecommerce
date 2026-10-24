"""Seed the Part A stand-ins of SPEC.md §2.5.

Idempotent. T2.7 seeds the states and the D4 warehouse, T2.8 the D14 product types; later tasks
add the D5 shipping zones and rates. Every `[PLACEHOLDER]` row must be replaced before production.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.seeds import seed_product_types
from apps.inventory.seeds import seed_warehouse
from apps.shipping.seeds import seed_states


class Command(BaseCommand):
    help = "Seed the states, the placeholder warehouse and the launch product types (SPEC.md §2.5)."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        seed_states()
        seed_warehouse()
        seed_product_types()
        self.stdout.write(
            "seed_dev_defaults: states, warehouse and product types seeded"
        )
