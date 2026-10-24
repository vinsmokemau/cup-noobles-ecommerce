import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import placeholders
from apps.inventory.models import Location
from apps.shipping.models import ShippingRate, ShippingZone
from tests.factories.catalog import ProductTypeFactory

pytestmark = pytest.mark.django_db

CLEAN_SCHEMA = {"type": "object"}


@pytest.fixture
def clean(settings, tmp_path, monkeypatch):
    """No placeholder of any kind remains: the database is empty, the settings are decided."""
    catalog = tmp_path / "cfdi_catalogs.json"
    catalog.write_text(json.dumps({"regimen_fiscal": [], "uso_cfdi": []}))
    monkeypatch.setattr(placeholders, "CFDI_CATALOG", catalog)
    settings.RESERVATION_TTL_SPEI_HOURS = 6
    settings.RESERVATION_TTL_OXXO_HOURS = 48
    settings.PAYMENT_INSTALLMENT_OPTIONS = [3, 6, 9]
    return catalog


def fails_naming(fragment: str) -> None:
    with pytest.raises(CommandError, match="check_placeholders") as raised:
        call_command("check_placeholders")
    assert fragment in str(raised.value)


def test_p2_v18_check_placeholders_kinds(clean, settings):
    call_command("check_placeholders")  # exits 0 when none remain

    location = Location.objects.create(
        code="almacen", name="[PLACEHOLDER] Almacén", kind="warehouse"
    )
    fails_naming("location")
    location.delete()
    call_command("check_placeholders")

    zone = ShippingZone.objects.create(code="local", name="[PLACEHOLDER] Local")
    fails_naming("shipping_zone")
    zone.name = "Local"
    zone.save()
    call_command("check_placeholders")

    rate = ShippingRate.objects.create(
        zone=zone, name="[PLACEHOLDER] Envío estándar", price_cents=1
    )
    fails_naming("shipping_rate")
    rate.delete()
    call_command("check_placeholders")

    product_type = ProductTypeFactory(
        attribute_schema={"$comment": "[PLACEHOLDER]", "type": "object"}
    )
    fails_naming("product_type")
    product_type.attribute_schema = CLEAN_SCHEMA
    product_type.save()
    call_command("check_placeholders")

    clean.write_text(json.dumps({"$comment": "[PLACEHOLDER]"}))
    fails_naming("cfdi_catalogs.json")
    clean.write_text(json.dumps({}))
    call_command("check_placeholders")

    for name, default in placeholders.SETTING_DEV_DEFAULTS.items():
        decided = getattr(settings, name)
        setattr(settings, name, default)
        fails_naming(name)
        setattr(settings, name, decided)
        call_command("check_placeholders")


def test_p2_v18_seeded_dev_defaults_all_fail():
    call_command("seed_dev_defaults")
    with pytest.raises(CommandError) as raised:
        call_command("check_placeholders")
    message = str(raised.value)
    assert "location" in message
    assert "product_type" in message
    assert "cfdi_catalogs.json" in message
    assert "RESERVATION_TTL_OXXO_HOURS" in message


def test_p2_v18_shipped_cfdi_sample_is_marked():
    catalog = json.loads(placeholders.CFDI_CATALOG.read_text(encoding="utf-8"))
    assert catalog["$comment"] == "[PLACEHOLDER]"
    assert catalog["title"] == "SAMPLE — not authoritative"
    assert catalog["regimen_fiscal"] and catalog["uso_cfdi"]
