"""The carrier contract suite's driver (SPEC.md 10.13, §4.3 Carrier, §4.6 "Contract — providers").

Scenarios are written once, against `CarrierDriver`. `MockDriver` plays the carrier's side by
moving the mock store; `ManualDriver` arrives in Phase 19. Everything past the carrier (the
shipment rows, `sync_shipments`, the state machine) is the code production runs.
"""

from typing import Protocol

from apps.core import providers
from apps.orders.models import Order
from apps.shipping.carriers.base import ShipmentRef, ShipmentStatus
from apps.shipping.carriers.mock import MockCarrier
from apps.shipping.management.commands.sync_shipments import (
    SyncResult,
    sync_shipments,
)


class CarrierDriver(Protocol):
    name: str

    def supports(self, scenario: str) -> bool | str:
        """True, or why the scenario can't be driven."""
        ...

    def create_shipment(
        self, order: Order, tracking_number: str | None = None
    ) -> ShipmentRef:
        """Ask the active carrier for a shipment, as the admin does."""
        ...

    def status(self, tracking_number: str) -> ShipmentStatus:
        """The active carrier's answer for a tracking number."""
        ...

    def report(self, tracking_number: str, status: ShipmentStatus) -> None:
        """The carrier's side: from now on it reports `status` for this shipment."""
        ...

    def sync(self) -> SyncResult:
        """Run `sync_shipments`, the code production runs every 30 minutes."""
        ...


class MockDriver:
    name = "mock"

    def supports(self, scenario: str) -> bool | str:
        return True

    def create_shipment(
        self, order: Order, tracking_number: str | None = None
    ) -> ShipmentRef:
        return providers.carrier().create_shipment(
            order, tracking_number=tracking_number
        )

    def status(self, tracking_number: str) -> ShipmentStatus:
        return providers.carrier().get_status(tracking_number)

    def report(self, tracking_number: str, status: ShipmentStatus) -> None:
        MockCarrier().record_status(tracking_number, status)

    def sync(self) -> SyncResult:
        return sync_shipments()
