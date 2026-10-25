"""Inventory errors. The checkout API turns these into the per-line customer message."""

from apps.catalog.models import Variant


class InsufficientStock(Exception):
    """A line asked for more units than are available (CR-04)."""

    def __init__(self, variant: Variant, requested: int, available: int) -> None:
        self.variant = variant
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for variant {variant.sku}: "
            f"requested {requested}, available {available}"
        )
