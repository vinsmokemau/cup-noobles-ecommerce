"""P15-V12 (T15.8): `check_placeholders` fails while a `[DEMO]` row exists (SPEC.md §2.5, REQ-065).

The other placeholder kinds are P2-V18 (`tests/integration/schema/test_placeholders.py`).
"""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import demo, placeholders
from apps.orders.models import OrderLine
from tests.factories.catalog import ProductFactory
from tests.factories.orders import OrderLineFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def clean(settings, tmp_path, monkeypatch):
    """No placeholder of another kind remains, so a failure can only come from a `[DEMO]` row."""
    catalog = tmp_path / "cfdi_catalogs.json"
    catalog.write_text(json.dumps({"regimen_fiscal": [], "uso_cfdi": []}))
    monkeypatch.setattr(placeholders, "CFDI_CATALOG", catalog)
    settings.RESERVATION_TTL_SPEI_HOURS = 6
    settings.RESERVATION_TTL_OXXO_HOURS = 48
    settings.PAYMENT_INSTALLMENT_OPTIONS = [3, 6, 9]


def fails_naming(fragment: str) -> None:
    with pytest.raises(CommandError, match="check_placeholders") as raised:
        call_command("check_placeholders")
    assert fragment in str(raised.value)


def test_p15_v12_demo_rows_fail_placeholder_check(clean):
    call_command("check_placeholders")  # exits 0 with no `[DEMO]` row

    product = ProductFactory(name="[DEMO] Figura")
    fails_naming("product '[DEMO] Figura'")

    # A sold demo product leaves its name on the order line, which outlives a rename.
    line = OrderLineFactory(product_name=product.name)
    product.name = "Figura"
    product.save()
    fails_naming(f"order_line '[DEMO] Figura' of order {line.order.number}")

    line.order.delete()
    call_command("check_placeholders")


def test_p15_v12_the_seeded_demo_dataset_is_found():
    call_command("seed_demo")

    found = placeholders.demo_rows()
    assert [row for row in found if row.startswith("product ")] == [
        f"product {product.name!r}" for product in demo.DEMO_PRODUCTS
    ]
    history = OrderLine.objects.filter(order__email=demo.DEMO_EMAIL)
    assert history.count() == 3
    assert [row for row in found if row.startswith("order_line ")] == [
        f"order_line {line.product_name!r} of order {line.order.number}"
        for line in history.order_by("id")
    ]

    with pytest.raises(CommandError) as raised:
        call_command("check_placeholders")
    for row in found:
        assert row in str(raised.value)
