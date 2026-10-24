from apps.inventory.models import Location
from apps.orders.models import Order


def test_location_label_is_its_name():
    assert str(Location(code="almacen", name="Almacén")) == "Almacén"


def test_order_label_is_its_number():
    assert str(Order(number="CN-2026-000001")) == "CN-2026-000001"
