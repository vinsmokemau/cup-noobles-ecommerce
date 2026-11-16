"""`seed_e2e`: `seed_demo` plus the data owned by individual specs (T15.2).

T15.2 has no Verify ID of its own: every journey uses the data (T15.6a, T15.6b) and P15-V11
(T15.3) checks the production guard. The tests of the scarce checkout product (G62) are in
`tests/api/test_routes.py`.
"""

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

# `load_postal_codes` fixes its sample path from settings.BASE_DIR when first imported. The tests
# below point BASE_DIR at a temporary folder, so import it here, before any test runs.
import apps.shipping.management.commands.load_postal_codes  # noqa: F401
from apps.accounts.models import Customer
from apps.catalog.models import Product, Variant
from apps.catalog.services import publish_product
from apps.core import demo
from apps.inventory import services
from apps.inventory.models import (
    InventoryReservation,
    Location,
    StockItem,
    StockLedger,
)
from apps.orders.models import Order, OrderEvent
from tests.factories.inventory import holding_order
from tests.factories.orders import order_in_state

pytestmark = pytest.mark.django_db

# Each journey's copy of the 15.A product it buys: SKU -> (type, price in centavos, on_hand).
TCG = ("tcg_sealed", 249900, 3)
FIGURA = ("figure", 129900, 4)
PLAYERA = ("apparel", 34900, 10)
JOURNEY_VARIANTS = {
    "E2E-J1-DESKTOP": TCG,
    "E2E-J1-MOBILE": TCG,
    "E2E-J3-DESKTOP": FIGURA,
    "E2E-J3-MOBILE": FIGURA,
    "E2E-J4-DESKTOP": FIGURA,
    "E2E-J4-MOBILE": FIGURA,
    "E2E-J8-DESKTOP": TCG,
    "E2E-J8-MOBILE": TCG,
    "E2E-J10-S": PLAYERA,
    "E2E-J10-M": PLAYERA,
    "E2E-J10-L": PLAYERA,
    "E2E-J11-S": PLAYERA,
    "E2E-J11-M": PLAYERA,
    "E2E-J11-L": PLAYERA,
}


@pytest.fixture
def seed_e2e(settings, tmp_path):
    """Run the command and return the manifest it wrote, in a folder of this test."""
    settings.BASE_DIR = tmp_path

    def run():
        call_command("seed_e2e")
        path = tmp_path / "var" / "e2e" / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return run


def stock(sku):
    item = StockItem.objects.get(variant__sku=sku)
    return item.on_hand, item.reserved


def row_counts():
    return {
        model.__name__: model.objects.count()
        for model in (
            Product,
            Variant,
            StockItem,
            StockLedger,
            InventoryReservation,
            Order,
            OrderEvent,
            Customer,
        )
    }


def test_seed_e2e_includes_the_demo_dataset(seed_e2e):
    seed_e2e()

    for product in demo.DEMO_PRODUCTS:
        seeded = Product.objects.get(name=product.name)
        assert seeded.status == product.status
        assert {variant.sku for variant in seeded.variants.all()} == {
            variant.sku for variant in product.variants
        }
        for variant in product.variants:
            # A variant that never had stock has no stock row.
            item = StockItem.objects.filter(variant__sku=variant.sku).first()
            assert (item.on_hand if item else 0) == variant.on_hand, variant.sku
    assert [order.state for order in demo.demo_orders()] == [
        "completed",
        "pending_payment",
        "paid",
    ]
    assert Customer.objects.get(email=demo.STAFF_EMAIL).is_superuser


def test_seed_e2e_manifest_names_the_demo_rows(seed_e2e, client):
    manifest = seed_e2e()["demo"]

    assert manifest["staff"] == {
        "email": "staff@cupnoobles.test",
        "password": demo.DEV_PASSWORD,
    }
    assert client.login(**manifest["staff"])
    assert manifest["guest"] == {"email": "demo@cupnoobles.test"}

    assert set(manifest["products"]) == {
        "tcg",
        "fundas",
        "sudadera",
        "playera",
        "figura",
        "artbook",
    }
    for entry in manifest["products"].values():
        product = Product.objects.get(slug=entry["slug"])
        assert (product.name, product.status) == (entry["name"], "active")
    assert manifest["products"]["tcg"]["name"] == "[DEMO] Caja de sobres TCG"
    assert manifest["products"]["tcg"]["variants"] == [
        {"sku": "DEMO-TCG", "options": {}}
    ]
    assert manifest["products"]["playera"]["variants"] == [
        {"sku": "DEMO-PLA-S", "options": {"talla": "S"}},
        {"sku": "DEMO-PLA-M", "options": {"talla": "M"}},
        {"sku": "DEMO-PLA-L", "options": {"talla": "L"}},
    ]
    assert len(manifest["products"]["sudadera"]["variants"]) == 6
    assert {
        key: Product.objects.get(slug=entry["slug"]).status
        for key, entry in manifest["hidden"].items()
    } == {"draft": "draft", "archived": "archived"}

    # The order numbers of the guest history, by what each order is for.
    states = {
        key: Order.objects.get(number=number, email="demo@cupnoobles.test").state
        for key, number in manifest["orders"].items()
    }
    assert states == {
        "completed": "completed",
        "oxxo": "pending_payment",
        "cfdi": "paid",
    }
    cfdi = Order.objects.get(number=manifest["orders"]["cfdi"])
    assert cfdi.invoice_request is not None


def test_seed_e2e_gives_each_journey_its_own_variants(seed_e2e, client):
    manifest = seed_e2e()["journeys"]

    owned = Variant.objects.filter(sku__startswith="E2E-J")
    assert {variant.sku for variant in owned} == set(JOURNEY_VARIANTS)
    for variant in owned.select_related("product__product_type", "product__franchise"):
        type_code, price_cents, on_hand = JOURNEY_VARIANTS[variant.sku]
        product = variant.product
        assert product.product_type.code == type_code, variant.sku
        assert variant.price_cents == price_cents, variant.sku
        assert stock(variant.sku) == (on_hand, 0), variant.sku
        # Fictional and labelled like the rest of the dataset, on sale, and not on the home page.
        assert product.name.startswith("[DEMO] "), variant.sku
        assert product.franchise.name == "Franquicia Demo"
        assert (product.status, product.is_featured) == ("active", False)

    # A journey that asserts stock has one product per Playwright project; J10 and J11 have one.
    for key in ("j1", "j3", "j4", "j8"):
        assert set(manifest[key]) == {"desktop", "mobile"}
        for project in ("desktop", "mobile"):
            entry = manifest[key][project]
            sku = f"E2E-{key}-{project}".upper()
            assert entry["variants"] == [{"sku": sku, "options": {}}]
            assert Variant.objects.get(sku=sku).product.slug == entry["slug"]
            assert (
                client.get(f"/api/catalog/products/{entry['slug']}/").status_code == 200
            )
        assert manifest[key]["desktop"]["slug"] != manifest[key]["mobile"]["slug"]
    for key in ("j10", "j11"):
        assert manifest[key]["variants"] == [
            {"sku": f"E2E-{key.upper()}-{size}", "options": {"talla": size}}
            for size in ("S", "M", "L")
        ]
        slug = manifest[key]["slug"]
        assert client.get(f"/api/catalog/products/{slug}/").status_code == 200

    # No journey shares a product with another journey or with the demo.
    slugs = [manifest[key][project]["slug"] for key in ("j1", "j3", "j4", "j8") for project in ("desktop", "mobile")]  # fmt: skip
    slugs += [manifest[key]["slug"] for key in ("j10", "j11")]
    assert len(set(slugs)) == 10
    assert not Product.objects.filter(
        slug__in=slugs, name__in=[product.name for product in demo.DEMO_PRODUCTS]
    ).exists()


def test_seed_e2e_gives_j11_a_product_to_publish(seed_e2e, client):
    """J11 has staff publish the catalog (P15-V16): one product per device that is not on sale."""
    launch = seed_e2e()["journeys"]["j11Launch"]

    def on_sale(project):
        slug = launch[project]["slug"]
        return client.get(f"/api/catalog/products/{slug}/").status_code == 200

    def statuses():
        return {
            project: Product.objects.get(slug=entry["slug"]).status
            for project, entry in launch.items()
        }

    assert set(launch) == {"desktop", "mobile"}
    assert launch["desktop"]["slug"] != launch["mobile"]["slug"]
    for project, entry in launch.items():
        product = Product.objects.get(slug=entry["slug"])
        assert entry["name"] == product.name
        assert product.name.startswith("[DEMO] ")
        assert product.franchise.name == "Franquicia Demo"
        assert entry["variants"] == [
            {"sku": f"E2E-LANZAMIENTO-{project.upper()}", "options": {}}
        ]
        # Nobody buys it: it has no stock.
        assert not StockItem.objects.filter(variant__product=product).exists()
        assert not on_sale(project)
    assert statuses() == {"desktop": "draft", "mobile": "draft"}

    # A run published one. The next seed takes it off sale again, and it can be published again.
    desktop = Product.objects.get(slug=launch["desktop"]["slug"])
    publish_product(desktop)
    assert on_sale("desktop")

    assert seed_e2e()["journeys"]["j11Launch"] == launch
    assert statuses() == {"desktop": "archived", "mobile": "draft"}
    assert not on_sale("desktop")

    desktop.refresh_from_db()
    publish_product(desktop)
    assert on_sale("desktop")


def test_seed_e2e_puts_the_journey_stock_back(seed_e2e):
    """A re-run settles what an earlier run left: units sold, units held, and a surplus."""
    seed_e2e()
    sku = "E2E-J3-DESKTOP"
    variant = Variant.objects.get(sku=sku)
    location = Location.objects.get(code="almacen")
    assert stock(sku) == (4, 0)

    # One unit gone, one held by an order waiting for payment and one by a draft.
    services.adjust_stock(
        variant, location, -1, reason="count_correction", actor=None, note="a sale"
    )
    pending = order_in_state("pending_payment")
    services.reserve(pending, [(variant, 1)], ttl=timedelta(hours=1))
    draft = holding_order(variant, 1)
    assert stock(sku) == (3, 2)

    seed_e2e()

    assert stock(sku) == (4, 0)
    assert not InventoryReservation.objects.filter(
        variant=variant, state="held"
    ).exists()
    assert Order.objects.get(pk=pending.pk).state == "cancelled"
    assert Order.objects.get(pk=draft.pk).state == "draft"

    # A surplus is removed through the inventory service, with a ledger row.
    services.receive_stock(variant, location, 5, note="drift")
    seed_e2e()

    assert stock(sku) == (4, 0)
    row = StockLedger.objects.filter(stock_item__variant=variant).latest("id")
    assert (row.delta, row.reason) == (-5, "count_correction")
    call_command("check_stock_integrity")


def test_seed_e2e_twice_changes_nothing(seed_e2e):
    first = seed_e2e()
    counts = row_counts()

    assert seed_e2e() == first
    assert row_counts() == counts


def test_seed_e2e_keeps_the_products_of_the_phase_12_specs_in_view(seed_e2e, client):
    """The demo and journey products join the catalog; the pages the earlier specs read still
    show their products: the home page lists 8 featured products and the catalog 24 per page."""
    catalog = seed_e2e()["catalog"]

    home = client.get("/api/catalog/products/", {"featured": "true", "page_size": 8})
    featured = {product["slug"] for product in home.json()["results"]}
    assert {product["slug"] for product in catalog["featured"]} <= featured

    first_page = client.get("/api/catalog/products/").json()["results"]
    listed = {product["slug"] for product in first_page}
    assert {product["slug"] for product in catalog["category"]["products"]} <= listed
    assert catalog["hoodie"]["slug"] in listed


def test_seed_e2e_refuses_without_dev_tools(settings, tmp_path):
    settings.BASE_DIR = tmp_path

    with override_settings(DEV_TOOLS_ENABLED=False):
        with pytest.raises(CommandError, match="DEV_TOOLS_ENABLED"):
            call_command("seed_e2e")

    # The guard comes first: nothing was seeded and no manifest was written.
    assert not Product.objects.exists()
    assert not Customer.objects.exists()
    assert not (tmp_path / "var" / "e2e" / "manifest.json").exists()
