"""The one place order totals are computed (CR-02). Money is integer centavos (CR-01)."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

IVA_NUMERATOR = 16
IVA_DENOMINATOR = 116


class PricedLine(Protocol):
    unit_price_cents: int
    quantity: int


@dataclass(frozen=True)
class Totals:
    subtotal_cents: int
    shipping_cents: int
    discount_cents: int
    total_cents: int
    tax_included_cents: int


def compute_totals(
    lines: Iterable[PricedLine], shipping_cents: int, discount_cents: int
) -> Totals:
    """Prices are IVA-included (A2): tax is decomposed from the total, never added to it."""
    if shipping_cents < 0 or discount_cents < 0:
        raise ValueError("shipping and discount cannot be negative")
    subtotal = 0
    for line in lines:
        if line.unit_price_cents < 0 or line.quantity < 0:
            raise ValueError("unit price and quantity cannot be negative")
        subtotal += line.unit_price_cents * line.quantity
    total = subtotal + shipping_cents - discount_cents
    if total < 0:
        raise ValueError("discount exceeds subtotal plus shipping")
    return Totals(
        subtotal_cents=subtotal,
        shipping_cents=shipping_cents,
        discount_cents=discount_cents,
        total_cents=total,
        tax_included_cents=_tax_included(total),
    )


def _tax_included(total_cents: int) -> int:
    """round(total * 16 / 116) in integers. A tie is impossible (16 * total * 2 is never an odd
    multiple of 116), so half-up and Python's round() agree."""
    return (2 * total_cents * IVA_NUMERATOR + IVA_DENOMINATOR) // (2 * IVA_DENOMINATOR)
