"""Reference data for `mx_state` (SPEC.md §4.4, T2.7).

The 32 federal entities with their ISO 3166-2:MX codes. Idempotent: running it again changes nothing.
"""

from apps.shipping.models import MxState

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
