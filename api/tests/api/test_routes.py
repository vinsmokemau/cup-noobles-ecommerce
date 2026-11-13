"""T1.13b: the routes the end-to-end stack check reads through the proxy (P1-V01, P1-V02)."""

import json

import pytest
from django.core.management import call_command

# `load_postal_codes` fixes its sample path from settings.BASE_DIR when first imported. The seed
# tests below point BASE_DIR at a temporary folder, so import it here, before any test runs,
# whatever order pytest-randomly picks.
import apps.shipping.management.commands.load_postal_codes  # noqa: E402, F401


@pytest.mark.django_db
def test_schema_endpoint_serves_openapi(api_client):
    response = api_client.get(
        "/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json"
    )

    assert response.status_code == 200
    assert json.loads(response.content)["openapi"].startswith("3.1")


@pytest.mark.django_db
def test_admin_login_page_renders(api_client):
    response = api_client.get("/admin/login/")

    assert response.status_code == 200
    assert b'name="username"' in response.content


@pytest.mark.django_db
def test_seed_e2e_writes_manifest(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    path = tmp_path / "var" / "e2e" / "manifest.json"

    call_command("seed_e2e")
    first = json.loads(path.read_text())
    call_command("seed_e2e")

    # Idempotent, and each phase adds its own part (Phase 12: the catalog and, for T12.15, a staff
    # account).
    assert json.loads(path.read_text()) == first
    assert set(first) == {"catalog", "staff"}


@pytest.mark.django_db
def test_seed_e2e_resets_the_scarce_product_to_two_units(settings, tmp_path):
    """G62, ADR-0071: a re-run lowers a surplus through a count_correction row, and only that."""
    from apps.inventory.models import StockItem, StockLedger
    from apps.inventory.services import receive_stock

    settings.BASE_DIR = tmp_path
    call_command("seed_e2e")
    item = StockItem.objects.get(variant__sku="E2E-CHECKOUT-SCARCE")
    assert (item.on_hand, item.reserved) == (2, 0)

    receive_stock(item.variant, item.location, 9, note="drift")
    call_command("seed_e2e")

    item.refresh_from_db()
    assert (item.on_hand, item.reserved) == (2, 0)
    row = StockLedger.objects.filter(stock_item=item).latest("id")
    assert (row.delta, row.reason) == (-9, "count_correction")

    call_command("seed_e2e")
    assert StockLedger.objects.filter(stock_item=item).latest("id").id == row.id


@pytest.mark.django_db
def test_seed_e2e_gives_back_the_units_that_earlier_orders_hold(settings, tmp_path):
    """G62, ADR-0072: a re-run settles the holds of earlier runs, so none lapses mid-run."""
    from datetime import timedelta

    from apps.inventory import services
    from apps.inventory.models import InventoryReservation, StockItem
    from apps.orders.models import Order
    from tests.factories.inventory import holding_order
    from tests.factories.orders import order_in_state

    settings.BASE_DIR = tmp_path
    call_command("seed_e2e")
    item = StockItem.objects.get(variant__sku="E2E-CHECKOUT-SCARCE")
    draft = holding_order(item.variant, 1)
    pending = order_in_state("pending_payment")
    services.reserve(pending, [(item.variant, 1)], ttl=timedelta(hours=1))
    item.refresh_from_db()
    assert item.reserved == 2

    call_command("seed_e2e")

    item.refresh_from_db()
    assert (item.on_hand - item.reserved, item.reserved) == (2, 0)
    assert not InventoryReservation.objects.filter(state="held").exists()
    assert Order.objects.get(pk=pending.pk).state == "cancelled"
    assert Order.objects.get(pk=draft.pk).state == "draft"


@pytest.mark.django_db
def test_seed_e2e_leaves_the_hold_of_an_order_in_another_state(settings, tmp_path):
    """G62, ADR-0072: only pending and draft orders are settled; any other state is left alone."""
    from datetime import timedelta

    from apps.inventory import services
    from apps.inventory.models import InventoryReservation, StockItem
    from apps.orders.models import Order
    from tests.factories.orders import order_in_state

    settings.BASE_DIR = tmp_path
    call_command("seed_e2e")
    item = StockItem.objects.get(variant__sku="E2E-CHECKOUT-SCARCE")
    other = order_in_state("paid")
    services.reserve(other, [(item.variant, 1)], ttl=timedelta(hours=1))

    call_command("seed_e2e")

    assert Order.objects.get(pk=other.pk).state == "paid"
    assert InventoryReservation.objects.filter(order_id=other.pk, state="held").exists()
