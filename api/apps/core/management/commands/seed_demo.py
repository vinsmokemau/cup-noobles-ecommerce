"""`manage.py seed_demo [--reset]`: the demo dataset of SPEC.md 15.A (T15.1).

Without `--reset` it creates what is missing and leaves the rest alone. With `--reset` it first
empties the database and the file stores (`MOCK_STORE_DIR`, `EMAIL_FILE_DIR`, `MEDIA_ROOT`), so the
dataset comes back exactly as seeded. Refuses to run unless `DEV_TOOLS_ENABLED`.
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.core import demo, providers


class Command(BaseCommand):
    help = "Seed the [DEMO] dataset of SPEC.md 15.A (development and tests only)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Empty the database and the mock, email and media folders first.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ENABLED:
            raise CommandError("seed_demo runs only where DEV_TOOLS_ENABLED is on")
        # The seeded orders are paid at the mock provider and shipped by the mock carrier.
        if providers.payment_provider().code != "mock":
            raise CommandError("seed_demo needs PAYMENT_PROVIDER=mock")
        if providers.carrier().code != "mock":
            raise CommandError("seed_demo needs CARRIER_PROVIDER=mock")

        if options["reset"]:
            demo.reset()
        with transaction.atomic():
            summary = demo.seed_demo()

        self.stdout.write(
            f"seed_demo: {summary.products_created} product(s) and "
            f"{summary.orders_created} order(s) created"
        )
        self.stdout.write(f"Staff: {demo.STAFF_EMAIL} / {demo.DEV_PASSWORD}")
        orders = ", ".join(
            f"{order.number} ({order.state})" for order in demo.demo_orders()
        )
        self.stdout.write(f"Guest orders of {demo.DEMO_EMAIL}: {orders}")
