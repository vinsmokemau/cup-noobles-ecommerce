"""`seed_demo`: the demo dataset of SPEC.md 15.A, its Release 1 rows (T15.1).

T15.1 has no Verify ID of its own: P15-V10 (T15.7) checks the dataset against the demo script and
P15-V11 (T15.3) the production guard.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from django.test import override_settings

from apps.accounts.models import Customer
from apps.catalog.availability import availability
from apps.catalog.models import Product, ProductType, Variant
from apps.catalog.seeds import LAUNCH_PRODUCT_TYPES
from apps.catalog.services import create_product
from apps.core import demo, providers
from apps.inventory.models import InventoryReservation, StockItem, StockLedger
from apps.invoicing.models import InvoiceRequest
from apps.notifications.models import EmailOutbox
from apps.orders.models import Order, OrderEvent
from apps.orders.numbering import next_order_number
from apps.payments.mapping import OXXO_GRACE
from apps.payments.models import Payment

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

# The Release 1 products of 15.A: name -> (type, price in centavos, {SKU: on_hand}).
VISIBLE = {
    "[DEMO] Caja de sobres TCG": ("tcg_sealed", 249900, {"DEMO-TCG": 3}),
    "[DEMO] Fundas para cartas": ("accessory", 19900, {"DEMO-FUNDAS": 20}),
    "[DEMO] Sudadera": (
        "apparel",
        74900,
        {
            "DEMO-SUD-S-NEG": 0,
            "DEMO-SUD-S-BLA": 5,
            "DEMO-SUD-M-NEG": 2,
            "DEMO-SUD-M-BLA": 5,
            "DEMO-SUD-L-NEG": 5,
            "DEMO-SUD-L-BLA": 5,
        },
    ),
    "[DEMO] Playera": (
        "apparel",
        34900,
        {"DEMO-PLA-S": 10, "DEMO-PLA-M": 10, "DEMO-PLA-L": 10},
    ),
    "[DEMO] Figura": ("figure", 129900, {"DEMO-FIG": 4}),
    "[DEMO] Artbook": ("artbook", 99900, {"DEMO-ARTBOOK": 2}),
}


def on_hand(sku):
    total = StockItem.objects.filter(variant__sku=sku).aggregate(n=Sum("on_hand"))["n"]
    return total or 0


def reserved(sku):
    total = StockItem.objects.filter(variant__sku=sku).aggregate(n=Sum("reserved"))["n"]
    return total or 0


def snapshot():
    """Everything 15.1 says is the same on every run: ids, slugs, SKUs, prices, and the orders."""
    return {
        "types": list(ProductType.objects.order_by("id").values_list("id", "code")),
        "products": list(
            Product.objects.order_by("id").values_list("id", "slug", "name", "status")
        ),
        "variants": list(
            Variant.objects.order_by("id").values_list("id", "sku", "price_cents")
        ),
        "stock": list(
            StockItem.objects.order_by("id").values_list(
                "id", "variant__sku", "on_hand", "reserved"
            )
        ),
        "orders": list(
            Order.objects.order_by("id").values_list(
                "id", "number", "email", "state", "total_cents"
            )
        ),
        "staff": list(
            Customer.objects.order_by("id").values_list("id", "email", "is_superuser")
        ),
    }


def row_counts():
    return {
        model.__name__: model.objects.count()
        for model in (
            Product,
            Variant,
            StockLedger,
            InventoryReservation,
            Order,
            OrderEvent,
            Payment,
            InvoiceRequest,
            EmailOutbox,
            Customer,
        )
    }


def files_in(folder):
    return sorted(
        str(path.relative_to(folder))
        for path in Path(folder).rglob("*")
        if path.is_file()
    )


def test_seed_demo_makes_the_15a_products_with_their_prices_and_stock():
    call_command("seed_demo")

    active = Product.objects.filter(status="active")
    assert {product.name for product in active} == set(VISIBLE)
    for name, (type_code, price_cents, stock) in VISIBLE.items():
        product = Product.objects.get(name=name)
        assert product.product_type.code == type_code
        assert product.franchise.name == "Franquicia Demo"
        assert product.published_at is not None
        variants = {variant.sku: variant for variant in product.variants.all()}
        assert set(variants) == set(stock)
        assert {variant.price_cents for variant in variants.values()} == {price_cents}
    for _name, (_type, _price, stock) in VISIBLE.items():
        for sku, units in stock.items():
            assert on_hand(sku) == units, sku


def test_seed_demo_sudadera_and_playera_variants():
    call_command("seed_demo")

    sudadera = Product.objects.get(name="[DEMO] Sudadera")
    assert {
        (variant.options["talla"], variant.options["color"])
        for variant in sudadera.variants.all()
    } == {(size, color) for size in "SML" for color in ("negro", "blanco")}
    # Demo step 3: S/negro is sold out, M/negro is down to its last units.
    assert availability(Variant.objects.get(sku="DEMO-SUD-S-NEG")) == {
        "status": "out_of_stock"
    }
    assert availability(Variant.objects.get(sku="DEMO-SUD-M-NEG")) == {
        "status": "low_stock"
    }
    playera = Product.objects.get(name="[DEMO] Playera")
    assert [variant.options for variant in playera.variants.order_by("position")] == [
        {"talla": "S"},
        {"talla": "M"},
        {"talla": "L"},
    ]


def test_seed_demo_adds_the_artbook_type_as_data():
    call_command("seed_demo")

    launch = {spec["code"] for spec in LAUNCH_PRODUCT_TYPES}
    assert set(ProductType.objects.values_list("code", flat=True)) == launch | {
        "artbook"
    }
    artbook = ProductType.objects.get(code="artbook")
    assert set(artbook.attribute_schema["properties"]) == {
        "ilustrador",
        "paginas",
        "idioma",
        "pasta_dura",
    }
    assert set(Product.objects.get(name="[DEMO] Artbook").attributes) == set(
        artbook.attribute_schema["properties"]
    )


def test_seed_demo_hides_one_draft_and_one_archived_product(client):
    call_command("seed_demo")

    hidden = Product.objects.exclude(status="active")
    assert sorted(hidden.values_list("status", flat=True)) == ["archived", "draft"]
    assert all(product.name.startswith("[DEMO]") for product in hidden)

    listed = client.get("/api/catalog/products/", {"page_size": 50}).json()["results"]
    assert {product["name"] for product in listed} == set(VISIBLE)
    for product in hidden:
        assert client.get(f"/api/catalog/products/{product.slug}/").status_code == 404


def test_seed_demo_features_the_visible_products_on_the_home_page(client):
    call_command("seed_demo")

    featured = client.get("/api/catalog/products/", {"featured": "true"}).json()
    assert [product["name"] for product in featured["results"]] == list(VISIBLE)


def test_seed_demo_staff_is_a_superuser_who_can_log_in(client):
    call_command("seed_demo")

    staff = Customer.objects.get(email="staff@cupnoobles.test")
    assert staff.is_staff and staff.is_superuser
    assert client.login(email="staff@cupnoobles.test", password=demo.DEV_PASSWORD)
    assert client.get("/admin/").status_code == 200


def test_seed_demo_guest_order_history(clock, settings):
    clock.travel(NOW)
    call_command("seed_demo")

    orders = list(Order.objects.order_by("id"))
    assert {order.email for order in orders} == {"demo@cupnoobles.test"}
    assert [order.state for order in orders] == ["completed", "pending_payment", "paid"]
    assert all(order.fulfillment_method == "delivery" for order in orders)
    assert all(order.customer_id is None for order in orders)
    completed, pending, paid = orders

    # Every order got where it is through the state machine, one event at a time.
    assert list(completed.events.order_by("id").values_list("event", "to_state")) == [
        ("checkout_submitted", "pending_payment"),
        ("payment_approved", "paid"),
        ("auto", "preparing"),
        ("shipment_created", "shipped"),
        ("marked_delivered", "delivered"),
        ("auto_after_7d", "completed"),
    ]
    shipment = completed.shipments.get()
    assert shipment.tracking_number == f"MOCK-{completed.number}-1"
    assert shipment.delivered_at == NOW
    assert completed.payments.filter(status="approved").count() == 1

    # The OXXO order: an active voucher, and the order waits for it plus the grace period. The
    # simulator's voucher lasts the OXXO window (G74, ADR-0074).
    voucher = pending.payments.get(status="pending")
    expiry = NOW + timedelta(hours=settings.RESERVATION_TTL_OXXO_HOURS)
    assert voucher.method == "oxxo"
    assert voucher.voucher_url.endswith(
        f"/dev/payments/voucher/{voucher.provider_payment_id}/"
    )
    assert voucher.voucher_expires_at == expiry
    assert pending.payment_deadline_at == expiry + OXXO_GRACE
    hold = InventoryReservation.objects.get(order=pending)
    assert (hold.state, hold.expires_at) == ("held", expiry + OXXO_GRACE)

    # The paid order asked for a CFDI, which nobody has issued yet.
    assert paid.paid_at == NOW
    assert paid.invoice_request.status == InvoiceRequest.Status.REQUESTED
    assert not InvoiceRequest.objects.exclude(order=paid).exists()


def test_seed_demo_order_history_keeps_the_15a_stock_and_a_clean_ledger():
    call_command("seed_demo")

    # Two units sold, one held by the OXXO order; the accessory still shows the 15.A count.
    assert (on_hand("DEMO-FUNDAS"), reserved("DEMO-FUNDAS")) == (20, 1)
    sold = StockLedger.objects.filter(reason="sale_online")
    assert [row.delta for row in sold] == [-1, -1]
    other = StockItem.objects.exclude(variant__sku="DEMO-FUNDAS")
    assert other.aggregate(n=Sum("reserved"))["n"] == 0
    call_command("check_stock_integrity")


def test_seed_demo_twice_changes_nothing(settings):
    call_command("seed_demo")
    before = (Product.objects.count(), Variant.objects.count())
    everything = (snapshot(), row_counts(), files_in(settings.MOCK_STORE_DIR))

    call_command("seed_demo")

    assert (Product.objects.count(), Variant.objects.count()) == before
    assert (snapshot(), row_counts(), files_in(settings.MOCK_STORE_DIR)) == everything


def test_seed_demo_refuses_without_dev_tools():
    with override_settings(DEV_TOOLS_ENABLED=False):
        with pytest.raises(CommandError):
            call_command("seed_demo")
    assert not Product.objects.exists()


@pytest.mark.parametrize("factory", ["payment_provider", "carrier"])
def test_seed_demo_refuses_without_the_mock_providers(monkeypatch, factory):
    monkeypatch.setattr(providers, factory, lambda: SimpleNamespace(code="real"))

    with pytest.raises(CommandError, match="mock"):
        call_command("seed_demo")
    assert not Product.objects.exists()


@pytest.fixture
def order_numbers_restart():
    """A test that commits leaves the year's order-number sequence behind; drop it afterwards."""
    yield
    demo._drop_order_number_sequences()


@pytest.mark.django_db(transaction=True)
def test_seed_demo_reset_gives_the_same_dataset_again(settings, order_numbers_restart):
    stores = (settings.MOCK_STORE_DIR, settings.EMAIL_FILE_DIR, settings.MEDIA_ROOT)
    call_command("seed_demo", "--reset")
    first = snapshot()
    assert [number[-6:] for _, number, *_ in first["orders"]] == [
        "000001",
        "000002",
        "000003",
    ]

    # What a demo leaves behind: a product, a used order number, and files in the three stores.
    create_product("accessory", "Producto de un demo anterior")
    next_order_number()
    for store in stores:
        leftover = Path(store) / "demo-anterior"
        leftover.mkdir(parents=True, exist_ok=True)
        (leftover / "sobra.txt").write_text("x", encoding="utf-8")
        (Path(store) / "sobra.txt").write_text("x", encoding="utf-8")

    call_command("seed_demo", "--reset")

    assert snapshot() == first
    assert not Product.objects.filter(name="Producto de un demo anterior").exists()
    for store in stores:
        assert Path(store).is_dir()
        assert not [name for name in files_in(store) if "sobra" in name]
    # The mock store holds the reseeded orders' records and nothing older.
    records = files_in(Path(settings.MOCK_STORE_DIR) / "payments")
    assert len([name for name in records if name.startswith("mock_pref_")]) == 3
    assert len([name for name in records if name.startswith("mock_pay_")]) == 3
