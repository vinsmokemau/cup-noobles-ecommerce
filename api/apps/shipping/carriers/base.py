"""Carrier interface (SPEC.md §4.3)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.orders.models import Order


@dataclass(frozen=True)
class ShipmentRef:
    carrier: str
    tracking_number: str
    tracking_url: str


class ShipmentStatus(StrEnum):
    UNKNOWN = "unknown"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"


class TrackingNumberRequired(Exception):
    """Raised by carriers that cannot generate a tracking number."""


class CarrierProvider(Protocol):
    code: str

    def create_shipment(
        self, order: Order, *, tracking_number: str | None = None
    ) -> ShipmentRef: ...

    def get_status(self, tracking_number: str) -> ShipmentStatus: ...
