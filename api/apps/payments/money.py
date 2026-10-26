"""The only conversion between the database's centavos and a provider's pesos (SPEC.md 9.2, CR-01).

Sub-centavo values are rejected, never rounded: a provider amount that is not a whole number of
centavos is a bug to surface, not a difference to absorb.
"""

from decimal import Decimal, InvalidOperation


def cents_to_pesos(cents: int) -> Decimal:
    """Integer centavos to a two-decimal peso amount: `116000` becomes `Decimal("1160.00")`."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError(f"cents must be an int, got {type(cents).__name__}")
    if cents < 0:
        raise ValueError("cents must not be negative")
    return Decimal(cents).scaleb(-2)


def pesos_to_cents(pesos: Decimal | str) -> int:
    """A peso amount to integer centavos. `Decimal` and `str` only: a float is already inexact."""
    if isinstance(pesos, str):
        try:
            pesos = Decimal(pesos)
        except InvalidOperation:
            raise ValueError(f"not a peso amount: {pesos!r}") from None
    elif not isinstance(pesos, Decimal):
        raise TypeError(f"pesos must be a Decimal or str, got {type(pesos).__name__}")
    if not pesos.is_finite():
        raise ValueError("pesos must be finite")
    if pesos < 0:
        raise ValueError("pesos must not be negative")
    centavos = pesos.scaleb(2)  # exact: it moves the exponent and never rounds
    if centavos != centavos.to_integral_value():
        raise ValueError(f"sub-centavo amount: {pesos}")
    return int(centavos)
