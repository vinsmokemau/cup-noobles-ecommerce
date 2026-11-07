"""Catalog data the Phase 12 end-to-end specs read (SPEC.md T12.16, §4.6).

Everything is fictional and shares the `E2E` marker. The products go through the catalog and
inventory services, so they pass the same validation and leave a ledger row for every unit.
Idempotent: a product whose name already exists is left alone.
"""

from io import BytesIO
from typing import Any

from django.core.files.base import ContentFile
from PIL import Image

from apps.catalog.images import add_product_image
from apps.catalog.models import (
    Category,
    Franchise,
    Product,
    ProductCategory,
    ProductType,
)
from apps.catalog.seeds import seed_product_types
from apps.catalog.services import (
    add_variant,
    archive_product,
    create_product,
    publish_product,
)
from apps.inventory.models import Location, StockItem
from apps.inventory.services import receive_stock

FRANCHISE_SLUG = "franquicia-e2e"
CATEGORY_SLUG = "figuras-e2e"
HOODIE = "Sudadera Nube E2E"
# Test data for the meta description (G55); not catalog copy.
HOODIE_DESCRIPTION = "Sudadera de prueba para las pruebas de extremo a extremo.\n\nNo es un producto real."
DRAFT = "Figura Borrador E2E"
ARCHIVED = "Figura Archivada E2E"
# (name, linea, featured position or None)
FIGURES = (
    ("Figura Aurora E2E", "Nendoroid", 1),
    ("Figura Brisa E2E", "Nendoroid", 2),
    ("Figura Cobalto E2E", "Figma", None),
)
# (options, price in centavos, units on hand): M + blanco is sold out and L costs more.
HOODIE_VARIANTS = (
    ({"talla": "M", "color": "negro"}, 74900, 20),
    ({"talla": "M", "color": "blanco"}, 74900, 0),
    ({"talla": "L", "color": "negro"}, 79900, 20),
    ({"talla": "L", "color": "blanco"}, 79900, 20),
)


def _stock(variant: Any, units: int) -> None:
    location, _ = Location.objects.get_or_create(
        code="almacen",
        defaults={"name": "Almacén", "kind": Location.Kind.WAREHOUSE},
    )
    StockItem.objects.get_or_create(variant=variant, location=location)
    if units:
        receive_stock(variant, location, units, note="seed_e2e")


# The checkout specs (Phase 13) buy this variant (L + blanco) and reserve stock each time they run,
# so a re-run of `seed_e2e` tops it up to a level no run exhausts. Other specs never buy it.
CHECKOUT_VARIANT_SKU = "E2E-HOODIE-L-BLA"
CHECKOUT_VARIANT_STOCK = 500


def _keep_checkout_stock(hoodie: Product) -> None:
    variant = hoodie.variants.get(sku=CHECKOUT_VARIANT_SKU)
    location = Location.objects.get(code="almacen")
    item, _ = StockItem.objects.get_or_create(variant=variant, location=location)
    missing = CHECKOUT_VARIANT_STOCK - (item.on_hand - item.reserved)
    if missing > 0:
        receive_stock(variant, location, missing, note="seed_e2e")


# P13-V18 (stock lost between cart and pay) needs a product whose last units a spec can buy
# without touching the products other specs read. Each run of `seed_e2e` puts it back to two units
# and one price: a re-run is what resets it after a local run of the specs.
# (name, sku, price in centavos, units available)
CHECKOUT_SCARCE = (
    "Figura Escasa E2E",
    "E2E-CHECKOUT-SCARCE",
    45900,
    2,
)


# P13-V24 (purchase limit) needs a variant with a per-customer limit. The limit and the stock are
# test values, not catalog data; a spec asks for more than the limit, so no order is ever created
# and the product keeps its stock. The window is set for the E2E stack in docker-compose.e2e.yml.
# (name, sku, price in centavos, units available, purchase limit)
CHECKOUT_LIMITED = (
    "Figura Limitada E2E",
    "E2E-CHECKOUT-LIMITED",
    45900,
    50,
    2,
)


def _checkout_error_product(
    name: str, sku: str, price: int, units: int, purchase_limit: int | None = None
) -> Product:
    product = Product.objects.filter(name=name).first()
    if product is None:
        product = create_product("figure", name, {"linea": "Figma"})
        add_variant(product, {}, price, sku)
        publish_product(product)
    variant = product.variants.get(sku=sku)
    if variant.price_cents != price:
        variant.price_cents = price
        variant.save(update_fields=["price_cents"])
    if variant.purchase_limit != purchase_limit:
        variant.purchase_limit = purchase_limit
        variant.save(update_fields=["purchase_limit"])
    location, _ = Location.objects.get_or_create(
        code="almacen",
        defaults={"name": "Almacén", "kind": Location.Kind.WAREHOUSE},
    )
    item, _ = StockItem.objects.get_or_create(variant=variant, location=location)
    missing = units - (item.on_hand - item.reserved)
    if missing > 0:
        receive_stock(variant, location, missing, note="seed_e2e")
    return product


def _test_picture() -> ContentFile:
    """A plain grey rectangle: test data, so the product page has a picture to share (P12-V23)."""
    buffer = BytesIO()
    Image.new("RGB", (1200, 900), (128, 128, 128)).save(buffer, "PNG")
    return ContentFile(buffer.getvalue(), name="e2e.png")


def _manifest(product: Product) -> dict[str, str]:
    return {"slug": product.slug, "name": product.name}


def _make_linea_filterable() -> None:
    """The facet sidebar needs a filterable key: `linea` on figures, titled "Línea"."""
    figure = ProductType.objects.get(code="figure")
    schema = figure.attribute_schema
    schema["properties"]["linea"]["title"] = "Línea"
    figure.filterable_keys = ["linea"]
    figure.save(update_fields=["attribute_schema", "filterable_keys"])


def seed_catalog() -> dict[str, Any]:
    """Create the missing products and return the catalog part of the E2E manifest."""
    seed_product_types()
    _make_linea_filterable()
    franchise, _ = Franchise.objects.get_or_create(
        slug=FRANCHISE_SLUG, defaults={"name": "Franquicia E2E"}
    )
    category, _ = Category.objects.get_or_create(
        slug=CATEGORY_SLUG, defaults={"name": "Figuras E2E"}
    )

    figures: list[tuple[Product, str]] = []
    for sequence, (name, linea, position) in enumerate(FIGURES, start=1):
        product = Product.objects.filter(name=name).first()
        if product is None:
            product = create_product(
                "figure", name, {"linea": linea}, franchise=franchise
            )
            variant = add_variant(
                product, {}, 59900 + sequence * 1000, f"E2E-FIG-{sequence}"
            )
            _stock(variant, 10)
            ProductCategory.objects.create(product=product, category=category)
            if position is not None:
                product.is_featured, product.featured_position = True, position
                product.save(update_fields=["is_featured", "featured_position"])
            publish_product(product)
        figures.append((product, linea))

    hoodie = Product.objects.filter(name=HOODIE).first()
    if hoodie is None:
        hoodie = create_product(
            "apparel",
            HOODIE,
            {"material": "Algodón"},
            description_md=HOODIE_DESCRIPTION,
        )
        for position, (options, price, units) in enumerate(HOODIE_VARIANTS):
            sku = f"E2E-HOODIE-{options['talla']}-{options['color'][:3].upper()}"
            _stock(add_variant(hoodie, options, price, sku, position=position), units)
        publish_product(hoodie)

    _keep_checkout_stock(hoodie)
    scarce = _checkout_error_product(*CHECKOUT_SCARCE)
    limited = _checkout_error_product(*CHECKOUT_LIMITED)

    if not hoodie.description_md:
        hoodie.description_md = HOODIE_DESCRIPTION
        hoodie.save(update_fields=["description_md"])

    if not hoodie.images.exists():
        add_product_image(hoodie, _test_picture())

    hidden: dict[str, dict[str, str]] = {}
    for key, name in (("draft", DRAFT), ("archived", ARCHIVED)):
        product = Product.objects.filter(name=name).first()
        if product is None:
            product = create_product("figure", name, {"linea": "Figma"})
            _stock(add_variant(product, {}, 52900, f"E2E-{key.upper()}"), 3)
            if key == "archived":
                archive_product(publish_product(product))
        hidden[key] = _manifest(product)

    return {
        "hidden": hidden,
        "featured": [_manifest(p) for p, _ in figures if p.is_featured],
        "linea": {
            "key": "linea",
            "value": "Nendoroid",
            "matching": [_manifest(p) for p, linea in figures if linea == "Nendoroid"],
            "other": [_manifest(p) for p, linea in figures if linea != "Nendoroid"],
        },
        "category": {
            "slug": category.slug,
            "products": [_manifest(p) for p, _ in figures],
            "outside": _manifest(hoodie),
        },
        "hoodie": {
            **_manifest(hoodie),
            "variants": [
                {"options": options, "price_cents": price, "in_stock": units > 0}
                for options, price, units in HOODIE_VARIANTS
            ],
        },
        "checkoutErrors": {
            "scarce": {**_manifest(scarce), "sku": CHECKOUT_SCARCE[1]},
            "limited": {**_manifest(limited), "limit": CHECKOUT_LIMITED[4]},
        },
        "search": {"query": "Aurora", "typo": "Auroa", **_manifest(figures[0][0])},
    }
