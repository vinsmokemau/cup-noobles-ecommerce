"""Dev tooling for the mock carrier (SPEC.md 10.12). Refuses to run in production.

`advance` is the command-line equivalent of the buttons on the mock tracking page (10.10).
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core import providers
from apps.orders.models import Shipment
from apps.shipping.carriers.base import ShipmentStatus
from apps.shipping.management.commands.sync_shipments import sync_shipments

# `--to` value -> the status the carrier will report.
TARGETS = {
    "in_transit": ShipmentStatus.IN_TRANSIT,
    "delivered": ShipmentStatus.DELIVERED,
    "exception": ShipmentStatus.EXCEPTION,
}


class Command(BaseCommand):
    help = "Drive the mock carrier (SPEC.md 10.12)."

    def add_arguments(self, parser: CommandParser) -> None:
        actions = parser.add_subparsers(dest="action", required=True)
        advance = actions.add_parser(
            "advance", help="Change what the carrier reports for a shipment."
        )
        advance.add_argument("tracking_number")
        advance.add_argument("--to", required=True, choices=sorted(TARGETS))
        advance.add_argument(
            "--sync",
            action="store_true",
            help="Then run sync_shipments for that shipment, as the page buttons do.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ENABLED:
            raise CommandError("mock_carrier runs only where DEV_TOOLS_ENABLED is on")
        carrier: Any = providers.carrier()
        if carrier.code != "mock":
            raise CommandError("mock_carrier needs CARRIER_PROVIDER=mock")
        number = options["tracking_number"]
        try:
            carrier.record_status(number, TARGETS[options["to"]])
        except KeyError:
            raise CommandError(f"The mock carrier has no shipment {number}") from None
        self.stdout.write(f"mock_carrier: {number} is now {options['to']}")
        if options["sync"]:
            ids = list(
                Shipment.objects.filter(tracking_number=number).values_list(
                    "pk", flat=True
                )
            )
            result = sync_shipments(ids)
            self.stdout.write(
                f"mock_carrier: sync_shipments checked {result.checked}, "
                f"delivered {result.delivered}"
            )
