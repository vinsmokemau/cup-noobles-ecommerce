import pytest
from django.urls import reverse

from apps.catalog.models import Product, Variant
from apps.catalog.services import add_variant, publish_product
from apps.inventory.models import StockItem, StockLedger
from tests.factories.catalog import ProductFactory, ProductTypeFactory

pytestmark = pytest.mark.django_db

CHANGELIST = "admin:catalog_product_changelist"


def run_action(admin_client, action, products):
    return admin_client.post(
        reverse(CHANGELIST),
        {"action": action, "_selected_action": [p.pk for p in products]},
        follow=True,
    )


def test_p3_v08_duplicate_product_action(admin_client):
    product = ProductFactory(
        name="Nendoroid Miku",
        product_type=ProductTypeFactory(variant_axes=["talla"]),
        attributes={},
    )
    for size in ("S", "M"):
        add_variant(
            product, {"talla": size}, 59900, f"MIKU-{size}", barcode=f"750{size}"
        )
    publish_product(product)

    response = run_action(admin_client, "duplicate", [product])

    assert response.status_code == 200
    copy = Product.objects.exclude(pk=product.pk).get()
    assert copy.slug != product.slug
    assert copy.status == "draft"
    assert copy.published_at is None
    assert copy.product_type_id == product.product_type_id
    assert sorted(copy.variants.values_list("options", flat=True), key=str) == [
        {"talla": "M"},
        {"talla": "S"},
    ]
    originals = set(product.variants.values_list("sku", flat=True))
    copies = set(copy.variants.values_list("sku", flat=True))
    assert len(copies) == 2 and not copies & originals
    assert set(copy.variants.values_list("price_cents", flat=True)) == {59900}
    assert not StockItem.objects.filter(variant__product=copy).exists()
    assert not StockLedger.objects.filter(stock_item__variant__product=copy).exists()
    assert Variant.objects.filter(product=product).count() == 2

    # Duplicating again takes the next free slug and SKUs.
    run_action(admin_client, "duplicate", [product])
    assert Product.objects.count() == 3
    assert Variant.objects.count() == 6


def test_publish_and_archive_actions_use_the_services(admin_client):
    product = ProductFactory()

    run_action(admin_client, "publish", [product])
    product.refresh_from_db()
    assert product.status == "active" and product.published_at is not None

    run_action(admin_client, "archive", [product])
    product.refresh_from_db()
    assert product.status == "archived" and product.published_at is not None


def test_changelist_shows_variants_stock_and_price_range(admin_client):
    from apps.inventory.models import Location

    product = ProductFactory(
        name="Hoodie", product_type=ProductTypeFactory(variant_axes=["talla"])
    )
    small = add_variant(product, {"talla": "S"}, 59900, "HOO-S")
    add_variant(product, {"talla": "M"}, 69900, "HOO-M")
    location = Location.objects.create(
        code="almacen-t", name="Almacén", kind="warehouse"
    )
    StockItem.objects.create(
        variant=small, location=location, on_hand=10, reserved=2, safety_stock=1
    )

    response = admin_client.get(reverse(CHANGELIST), {"q": "HOO-M"})

    html = response.content.decode()
    assert response.status_code == 200
    assert "Hoodie" in html
    assert "$599.00 – $699.00" in html
    assert 'class="field-available_stock">7<' in html
    assert 'class="field-variant_count">2<' in html
