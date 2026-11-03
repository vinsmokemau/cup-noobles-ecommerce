"""Catalog data the Phase 12 end-to-end specs read (SPEC.md T12.16, §4.6).

Everything is fictional and shares the `E2E` marker. The products go through the catalog and
inventory services, so they pass the same validation and leave a ledger row for every unit.
Idempotent: a product whose name already exists is left alone.
"""

from typing import Any

from apps.catalog.models import (
    Category,
    Franchise,
    Product,
    ProductCategory,
    ProductType,
)
from apps.catalog.seeds import seed_product_types
from apps.catalog.services import add_variant, create_product, publish_product
from apps.inventory.models import Location, StockItem
from apps.inventory.services import receive_stock

FRANCHISE_SLUG = "franquicia-e2e"
CATEGORY_SLUG = "figuras-e2e"
HOODIE = "Sudadera Nube E2E"
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
        hoodie = create_product("apparel", HOODIE, {"material": "Algodón"})
        for position, (options, price, units) in enumerate(HOODIE_VARIANTS):
            sku = f"E2E-HOODIE-{options['talla']}-{options['color'][:3].upper()}"
            _stock(add_variant(hoodie, options, price, sku, position=position), units)
        publish_product(hoodie)

    return {
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
        "search": {"query": "Aurora", "typo": "Auroa", **_manifest(figures[0][0])},
    }
