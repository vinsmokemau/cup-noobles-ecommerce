"""The delivery shipping quote (SPEC.md T7.6).

A postal code names a state, the state names a zone (`shipping_zone_state`), and the zone's rate
whose half-open `[min_subtotal_cents, max_subtotal_cents)` bracket holds the subtotal gives the
price. A quote is never a silent zero: a missing code or rate raises.
"""

from dataclasses import dataclass

from django.db.models import Q

from apps.core import providers
from apps.shipping.models import ShippingRate, ShippingZoneState


class QuoteError(Exception):
    """A delivery quote cannot be given; the message is shown to the customer (es-MX)."""


class UnknownPostalCode(QuoteError):
    pass


class NoShippingRate(QuoteError):
    pass


@dataclass(frozen=True)
class ShippingQuote:
    price_cents: int
    eta_min_days: int
    eta_max_days: int
    name: str
    zone: str


def quote(postal_code: str, subtotal_cents: int) -> ShippingQuote:
    info = providers.postal_code_lookup().lookup(postal_code)
    if info is None:
        raise UnknownPostalCode("No encontramos ese código postal.")

    link = (
        ShippingZoneState.objects.select_related("zone")
        .filter(state_id=info.state_code)
        .first()
    )
    if link is None:
        raise NoShippingRate("Todavía no enviamos a ese estado.")

    rate = (
        ShippingRate.objects.filter(zone=link.zone, is_active=True)
        .filter(min_subtotal_cents__lte=subtotal_cents)
        .filter(
            Q(max_subtotal_cents__isnull=True)
            | Q(max_subtotal_cents__gt=subtotal_cents)
        )
        .order_by("-min_subtotal_cents")
        .first()
    )
    if rate is None:
        raise NoShippingRate("No pudimos calcular el envío para ese código postal.")

    return ShippingQuote(
        price_cents=rate.price_cents,
        eta_min_days=rate.eta_min_days,
        eta_max_days=rate.eta_max_days,
        name=rate.name,
        zone=link.zone.code,
    )
