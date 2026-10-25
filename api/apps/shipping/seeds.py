"""Reference data for `mx_state` (SPEC.md §4.4, T2.7).

The 32 federal entities with their ISO 3166-2:MX codes. Idempotent: running it again changes nothing.
"""

from apps.shipping.models import (
    MxState,
    ShippingRate,
    ShippingZone,
    ShippingZoneState,
)

MX_STATES: tuple[tuple[str, str], ...] = (
    ("AGU", "Aguascalientes"),
    ("BCN", "Baja California"),
    ("BCS", "Baja California Sur"),
    ("CAM", "Campeche"),
    ("CHP", "Chiapas"),
    ("CHH", "Chihuahua"),
    ("CMX", "Ciudad de México"),
    ("COA", "Coahuila"),
    ("COL", "Colima"),
    ("DUR", "Durango"),
    ("GUA", "Guanajuato"),
    ("GRO", "Guerrero"),
    ("HID", "Hidalgo"),
    ("JAL", "Jalisco"),
    ("MEX", "Estado de México"),
    ("MIC", "Michoacán"),
    ("MOR", "Morelos"),
    ("NAY", "Nayarit"),
    ("NLE", "Nuevo León"),
    ("OAX", "Oaxaca"),
    ("PUE", "Puebla"),
    ("QUE", "Querétaro"),
    ("ROO", "Quintana Roo"),
    ("SLP", "San Luis Potosí"),
    ("SIN", "Sinaloa"),
    ("SON", "Sonora"),
    ("TAB", "Tabasco"),
    ("TAM", "Tamaulipas"),
    ("TLA", "Tlaxcala"),
    ("VER", "Veracruz"),
    ("YUC", "Yucatán"),
    ("ZAC", "Zacatecas"),
)


def seed_states() -> None:
    for code, name in MX_STATES:
        MxState.objects.update_or_create(code=code, defaults={"name": name})


# D5 stand-in (SPEC.md §2.5, T7.7). `check_placeholders` fails while the marker remains.
# A rate applies from `min_subtotal_cents` (inclusive) up to `max_subtotal_cents` (exclusive).
LOCAL_STATES = ("CMX", "MEX")
FREE_SHIPPING_FROM_CENTS = 150_000
RATE_NAME = "[PLACEHOLDER] Envío estándar"

# (code, name, position, price below the threshold in centavos, ETA min days, ETA max days)
SHIPPING_ZONES: tuple[tuple[str, str, int, int, int, int], ...] = (
    ("local", "[PLACEHOLDER] Local", 0, 9_900, 1, 3),
    ("nacional", "[PLACEHOLDER] Nacional", 1, 17_900, 3, 7),
)


def seed_shipping() -> None:
    """Seed zones, the state → zone map and the rates. Run `seed_states` first."""
    for code, name, position, price_cents, eta_min, eta_max in SHIPPING_ZONES:
        zone, _ = ShippingZone.objects.update_or_create(
            code=code, defaults={"name": name, "position": position}
        )
        for min_cents, max_cents, price in (
            (0, FREE_SHIPPING_FROM_CENTS, price_cents),
            (FREE_SHIPPING_FROM_CENTS, None, 0),
        ):
            ShippingRate.objects.update_or_create(
                zone=zone,
                min_subtotal_cents=min_cents,
                defaults={
                    "name": RATE_NAME,
                    "max_subtotal_cents": max_cents,
                    "price_cents": price,
                    "eta_min_days": eta_min,
                    "eta_max_days": eta_max,
                    "is_active": True,
                },
            )

    local = ShippingZone.objects.get(code="local")
    nacional = ShippingZone.objects.get(code="nacional")
    for state in MxState.objects.all():
        zone = local if state.code in LOCAL_STATES else nacional
        ShippingZoneState.objects.update_or_create(state=state, defaults={"zone": zone})
