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


class InvalidQuantity(ValueError):
    """A quantity that is not a positive whole number, or an adjustment of zero."""


class AdjustmentBelowReserved(Exception):
    """An adjustment would leave `on_hand` below the units already promised to orders."""

    def __init__(
        self, variant: Variant, delta: int, on_hand: int, reserved: int
    ) -> None:
        self.variant = variant
        self.delta = delta
        # Not named `on_hand`: only the services may write that name (CR-05).
        self.shelf_units = on_hand
        self.held_units = reserved
        super().__init__(
            f"Adjusting variant {variant.sku} by {delta} would leave on_hand "
            f"{on_hand + delta} below reserved {reserved}"
        )
