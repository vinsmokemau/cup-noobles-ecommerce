"""Products owned by the Release 1 journey specs (SPEC.md T15.2, §4.6, 15.A).

A spec that changes stock buys variants seeded for it alone, with the SKU prefix `E2E-<spec>`.
Each journey gets a copy of the 15.A product it buys: same type, attributes, price, variants and
stock, under its own name and SKUs, so a journey never moves the stock another spec reads.

J1, J3, J4 and J8 assert stock counts and run on the `desktop` and `mobile` Playwright projects at
the same time, so each has one copy per project. J10 and J11 assert no stock count and share one.

Every run of `seed_e2e` puts each journey variant back to its 15.A count and settles the holds
earlier runs left (the mechanism of ADR-0071 and ADR-0072), so a journey starts from known stock.
"""

from dataclasses import dataclass
from typing import Any

from apps.catalog.e2e_seed import set_available
from apps.catalog.models import Franchise, Product
from apps.catalog.services import add_variant, create_product, publish_product
from apps.core import demo

PROJECTS = ("desktop", "mobile")


@dataclass(frozen=True)
class Journey:
    key: str
    # The 15.A product the journey buys ("Used by" column).
    demo_name: str
    # True when the journey asserts stock counts: one copy per Playwright project.
    per_project: bool


JOURNEYS: tuple[Journey, ...] = (
    Journey("j1", f"{demo.DEMO_PREFIX} Caja de sobres TCG", True),
    Journey("j3", f"{demo.DEMO_PREFIX} Figura", True),
    Journey("j4", f"{demo.DEMO_PREFIX} Figura", True),
    Journey("j8", f"{demo.DEMO_PREFIX} Caja de sobres TCG", True),
    Journey("j10", f"{demo.DEMO_PREFIX} Playera", False),
    Journey("j11", f"{demo.DEMO_PREFIX} Playera", False),
)


def product_manifest(product: Product) -> dict[str, Any]:
    """What a spec needs to find a product and its variants."""
    return {
        "slug": product.slug,
        "name": product.name,
        "variants": [
            {"sku": variant.sku, "options": variant.options}
            for variant in product.variants.order_by("position", "id")
        ],
    }


def _sku(owner: str, options: tuple[tuple[str, str], ...]) -> str:
    """`E2E-J1-DESKTOP`, or `E2E-J10-S` for the variant with talla S."""
    return "-".join(["E2E", owner, *(value for _, value in options)]).upper()


def _seed_copy(source: demo.DemoProduct, owner: str, franchise: Franchise) -> Product:
    """The journey's copy of `source`, created once; its stock is reset on every run."""
    name = f"{source.name} ({owner})"
    product = Product.objects.filter(name=name).first()
    if product is None:
        fields: dict[str, Any] = {"franchise": franchise}
        if source.variant_axes is not None:
            fields["variant_axes"] = list(source.variant_axes)
        product = create_product(source.type_code, name, source.attributes, **fields)
        for position, spec in enumerate(source.variants):
            add_variant(
                product,
                dict(spec.options),
                source.price_cents,
                _sku(owner.replace(" ", "-"), spec.options),
                position=position,
            )
        publish_product(product)
    stock = {tuple(sorted(spec.options)): spec.on_hand for spec in source.variants}
    for variant in product.variants.all():
        set_available(variant, stock[tuple(sorted(variant.options.items()))])
    return product


def seed_journeys() -> dict[str, Any]:
    """Create the missing journey products, reset their stock, and return the manifest part.

    Needs `seed_demo` first: the product types, the warehouse and the demo franchise are its.
    """
    sources = {source.name: source for source in demo.DEMO_PRODUCTS}
    franchise = Franchise.objects.get(slug=demo.FRANCHISE_SLUG)
    manifest: dict[str, Any] = {}
    for journey in JOURNEYS:
        source = sources[journey.demo_name]
        label = journey.key.upper()
        if journey.per_project:
            manifest[journey.key] = {
                project: product_manifest(
                    _seed_copy(source, f"{label} {project}", franchise)
                )
                for project in PROJECTS
            }
        else:
            manifest[journey.key] = product_manifest(
                _seed_copy(source, label, franchise)
            )
    return manifest
