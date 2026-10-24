"""Warehouse location, D4 stand-in (SPEC.md §2.5, T2.7).

`check_placeholders` (T2.9) fails while the `[PLACEHOLDER]` marker remains. The location is a
warehouse, never presented as a store (CR-47).
"""

from apps.inventory.models import Location

WAREHOUSE_CODE = "almacen"


def seed_warehouse() -> None:
    Location.objects.update_or_create(
        code=WAREHOUSE_CODE,
        defaults={
            "name": "[PLACEHOLDER] Almacén Cup Noobles",
            "kind": Location.Kind.WAREHOUSE,
            "is_pickup_point": False,
            "address_line": "[PLACEHOLDER] Calle Ejemplo 123, Col. Centro",
            "municipality": "Cuauhtémoc",
            "state_code": "CMX",
            "postal_code": "06000",
        },
    )
