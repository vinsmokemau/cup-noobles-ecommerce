"""Minimal demo seed, one product per launch type (SPEC.md T3.7, §2.5, 15.A).

Everything is fictional and labelled: names start with `[DEMO]` and the franchise is "Franquicia Demo".
Prices are the 15.A figures. The products go through the catalog services, so they pass the same
validation as the admin. No stock and no images are made here: stock belongs to the inventory
services (Phase 4), and imagery comes from the Design System. T15.1 replaces this with the full dataset.

Idempotent: a product whose name already exists is left alone.
"""

from dataclasses import dataclass, field
from typing import Any

from apps.catalog.models import Franchise, Product
from apps.catalog.seeds import seed_product_types
from apps.catalog.services import add_variant, create_product, publish_product

DEMO_PREFIX = "[DEMO]"
FRANCHISE_SLUG = "franquicia-demo"
FRANCHISE_NAME = "Franquicia Demo"


@dataclass(frozen=True)
class DemoProduct:
    type_code: str
    name: str
    attributes: dict[str, Any]
    price_cents: int
    sku: str
    variants: tuple[tuple[dict[str, str], str], ...] = field(default=())


DEMO_PRODUCTS: tuple[DemoProduct, ...] = (
    DemoProduct(
        "tcg_sealed",
        f"{DEMO_PREFIX} Caja de sobres TCG",
        {
            "juego": "Juego Demo",
            "set": "Set Demo",
            "idioma": "Español",
            "sobres_por_caja": 36,
        },
        249900,
        "DEMO-TCG",
    ),
    DemoProduct("board_game", f"{DEMO_PREFIX} Juego de mesa", {}, 89900, "DEMO-MESA"),
    DemoProduct(
        "apparel",
        f"{DEMO_PREFIX} Sudadera",
        {"material": "Algodón", "corte": "Regular"},
        74900,
        "DEMO-SUD",
        tuple(
            ({"talla": size, "color": color}, f"DEMO-SUD-{size}-{color[:3].upper()}")
            for size in ("S", "M", "L")
            for color in ("negro", "blanco")
        ),
    ),
    DemoProduct(
        "figure",
        f"{DEMO_PREFIX} Figura",
        {
            "linea": "Línea Demo",
            "numero": 1,
            "escala": "1/7",
            "altura_mm": 180,
            "fabricante": "Fabricante Demo",
        },
        129900,
        "DEMO-FIG",
    ),
    DemoProduct(
        "accessory", f"{DEMO_PREFIX} Fundas para cartas", {}, 19900, "DEMO-FUNDAS"
    ),
)


def seed_demo_products() -> list[Product]:
    """Create the missing demo products, published. Returns the ones created this run."""
    seed_product_types()
    franchise, _ = Franchise.objects.get_or_create(
        slug=FRANCHISE_SLUG, defaults={"name": FRANCHISE_NAME}
    )
    created: list[Product] = []
    for demo in DEMO_PRODUCTS:
        if Product.objects.filter(name=demo.name).exists():
            continue
        product = create_product(
            demo.type_code, demo.name, demo.attributes, franchise=franchise
        )
        for position, (options, sku) in enumerate(demo.variants or (({}, demo.sku),)):
            add_variant(product, options, demo.price_cents, sku, position=position)
        publish_product(product)
        created.append(product)
    return created
