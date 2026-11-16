"""The demo dataset: the Release 1 rows of SPEC.md 15.A (T15.1).

Everything is fictional and labelled: product names start with `[DEMO]`, the franchise is
"Franquicia Demo" and every email uses the reserved `.test` domain. Prices and stock are the 15.A
figures; the warehouse, the shipping zones and the launch product types are the §2.5 stand-ins.

Nothing is inserted in a state the store could not reach. Products go through the catalog
services and stock through `receive_stock`. Each order is a real checkout, paid at the mock
provider and moved by `apply_event`, the way the storefront, the simulator and the admin do it.

`seed_demo()` creates what is missing and leaves the rest alone, so a second run changes nothing.
`reset()` empties the database and the file stores first, so the next seed gives the same ids,
slugs, SKUs, prices and order numbers. Public ids (UUIDs) and timestamps are new on every reset.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.db import connection

from apps.accounts.models import Customer
from apps.carts.models import Cart, CartLine
from apps.catalog.models import Franchise, Product, ProductType, Variant
from apps.catalog.seeds import LAUNCH_PRODUCT_TYPES, seed_product_types
from apps.catalog.services import (
    add_variant,
    archive_product,
    create_product,
    publish_product,
)
from apps.core import providers
from apps.inventory.models import Location
from apps.inventory.seeds import WAREHOUSE_CODE, seed_warehouse
from apps.inventory.services import receive_stock
from apps.orders.models import Order, Shipment
from apps.orders.serializers import CheckoutRequestSerializer
from apps.orders.services import create_order_from_cart
from apps.orders.state_machine import apply_event
from apps.payments.devtools import outcomes
from apps.payments.webhooks import process_provider_payment
from apps.shipping.carriers.base import ShipmentStatus
from apps.shipping.management.commands.sync_shipments import sync_shipments
from apps.shipping.seeds import seed_shipping, seed_states

DEMO_PREFIX = "[DEMO]"
FRANCHISE_SLUG = "franquicia-demo"
FRANCHISE_NAME = "Franquicia Demo"
NOTE = "seed_demo"

STAFF_EMAIL = "staff@cupnoobles.test"
DEMO_EMAIL = "demo@cupnoobles.test"
# The fixed dev password of 15.A. The account exists only where dev tools are on, so a production
# database never holds a known password.
DEV_PASSWORD = "demo-not-a-secret"

# A new category made of data alone (15.A): no code knows this type.
ARTBOOK_TYPE: dict[str, Any] = {
    "code": "artbook",
    "name": "Artbook",
    "attribute_schema": {
        "type": "object",
        "properties": {
            "ilustrador": {"type": "string", "title": "Ilustrador"},
            "paginas": {"type": "integer", "title": "Páginas"},
            "idioma": {"type": "string", "title": "Idioma"},
            "pasta_dura": {"type": "boolean", "title": "Pasta dura"},
        },
        "additionalProperties": False,
    },
    "variant_axes": [],
    "filterable_keys": ["idioma"],
}

ACTIVE, DRAFT, ARCHIVED = "active", "draft", "archived"


@dataclass(frozen=True)
class DemoVariant:
    sku: str
    on_hand: int
    options: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DemoProduct:
    type_code: str
    name: str
    attributes: dict[str, Any]
    price_cents: int
    variants: tuple[DemoVariant, ...]
    variant_axes: tuple[str, ...] | None = None
    status: str = ACTIVE


def _sudadera_stock(size: str, color: str) -> int:
    """15.A: S/negro has none, M/negro has 2, the rest have 5."""
    return {("S", "negro"): 0, ("M", "negro"): 2}.get((size, color), 5)


SIZES = ("S", "M", "L")
ACCESSORY_SKU = "DEMO-FUNDAS"
ACCESSORY_PRICE_CENTS = 19900

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
        (DemoVariant("DEMO-TCG", 3),),
    ),
    DemoProduct(
        "accessory",
        f"{DEMO_PREFIX} Fundas para cartas",
        {},
        ACCESSORY_PRICE_CENTS,
        (DemoVariant(ACCESSORY_SKU, 20),),
    ),
    DemoProduct(
        "apparel",
        f"{DEMO_PREFIX} Sudadera",
        {"material": "Algodón", "corte": "Regular"},
        74900,
        tuple(
            DemoVariant(
                f"DEMO-SUD-{size}-{color[:3].upper()}",
                _sudadera_stock(size, color),
                (("talla", size), ("color", color)),
            )
            for size in SIZES
            for color in ("negro", "blanco")
        ),
    ),
    DemoProduct(
        "apparel",
        f"{DEMO_PREFIX} Playera",
        {"material": "Algodón", "corte": "Regular"},
        34900,
        tuple(
            DemoVariant(f"DEMO-PLA-{size}", 10, (("talla", size),)) for size in SIZES
        ),
        variant_axes=("talla",),
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
        (DemoVariant("DEMO-FIG", 4),),
    ),
    DemoProduct(
        "artbook",
        f"{DEMO_PREFIX} Artbook",
        {
            "ilustrador": "Ilustrador Demo",
            "paginas": 160,
            "idioma": "Español",
            "pasta_dura": True,
        },
        99900,
        (DemoVariant("DEMO-ARTBOOK", 2),),
    ),
    # Hidden products (15.A): never on the storefront. No stock; the price is the accessory's.
    DemoProduct(
        "accessory",
        f"{DEMO_PREFIX} Accesorio en borrador",
        {},
        ACCESSORY_PRICE_CENTS,
        (DemoVariant("DEMO-BORRADOR", 0),),
        status=DRAFT,
    ),
    DemoProduct(
        "accessory",
        f"{DEMO_PREFIX} Accesorio archivado",
        {},
        ACCESSORY_PRICE_CENTS,
        (DemoVariant("DEMO-ARCHIVADO", 0),),
        status=ARCHIVED,
    ),
)

# The guest order history of 15.A buys one unit of this SKU per order. No journey asserts its
# stock, and the seed receives the units the paid orders take, so its `on_hand` stays the 15.A one.
HISTORY_SKU = ACCESSORY_SKU
HISTORY_PAID_ORDERS = 2

# The delivery address of the seeded orders: fictional, in a postal code of the committed sample.
DEMO_ADDRESS = {
    "recipient_name": "Cliente Demo",
    "street": "Calle Ejemplo",
    "ext_number": "123",
    "neighborhood": "Roma Norte",
    "municipality": "Cuauhtémoc",
    "state_code": "CMX",
    "postal_code": "06700",
}
# Sample fiscal data, not a real taxpayer: the generic RFC and codes of the stand-in catalog
# (`api/fixtures/cfdi_catalogs.json`, D16).
DEMO_INVOICE = {
    "rfc": "XAXX010101000",
    "legal_name": "Cliente Demo",
    "fiscal_postal_code": "06700",
    "tax_regime": "616",
    "cfdi_use": "S01",
}


@dataclass(frozen=True)
class Summary:
    products_created: int
    orders_created: int


def seed_demo() -> Summary:
    """Create the missing rows of the dataset. Run it inside one transaction."""
    seed_states()
    seed_warehouse()
    seed_product_types()
    _seed_artbook_type()
    seed_shipping()
    # The checkout quotes shipping from the postal code, here and in the demo.
    call_command("load_postal_codes", verbosity=0)

    staff = _seed_staff()
    franchise, _ = Franchise.objects.get_or_create(
        slug=FRANCHISE_SLUG, defaults={"name": FRANCHISE_NAME}
    )
    location = Location.objects.get(code=WAREHOUSE_CODE)
    visible = [demo for demo in DEMO_PRODUCTS if demo.status == ACTIVE]
    created = 0
    for demo in DEMO_PRODUCTS:
        # The home page lists the visible products, in the 15.A order (G28).
        featured = visible.index(demo) + 1 if demo in visible else None
        created += _seed_product(demo, franchise, location, featured)
    orders = _seed_order_history(staff, location)
    return Summary(products_created=created, orders_created=len(orders))


def demo_orders() -> list[Order]:
    """The guest order history, oldest first."""
    return list(Order.objects.filter(email=DEMO_EMAIL).order_by("id"))


def _seed_artbook_type() -> None:
    ProductType.objects.get_or_create(
        code=ARTBOOK_TYPE["code"],
        defaults={
            "name": ARTBOOK_TYPE["name"],
            "attribute_schema": ARTBOOK_TYPE["attribute_schema"],
            "variant_axes": ARTBOOK_TYPE["variant_axes"],
            "filterable_keys": ARTBOOK_TYPE["filterable_keys"],
            "position": len(LAUNCH_PRODUCT_TYPES),
        },
    )


def _seed_staff() -> Customer:
    staff = Customer.objects.filter(email=STAFF_EMAIL).first()
    if staff is None:
        staff = Customer.objects.create_superuser(STAFF_EMAIL, DEV_PASSWORD)
    return staff


def _seed_product(
    demo: DemoProduct, franchise: Franchise, location: Location, featured: int | None
) -> bool:
    """Create the product with its variants and stock. False when it already exists."""
    if Product.objects.filter(name=demo.name).exists():
        return False
    fields: dict[str, Any] = {"franchise": franchise}
    if demo.variant_axes is not None:
        fields["variant_axes"] = list(demo.variant_axes)
    if featured is not None:
        fields.update(is_featured=True, featured_position=featured)
    product = create_product(demo.type_code, demo.name, demo.attributes, **fields)
    for position, spec in enumerate(demo.variants):
        variant = add_variant(
            product, dict(spec.options), demo.price_cents, spec.sku, position=position
        )
        if spec.on_hand:
            receive_stock(variant, location, spec.on_hand, note=NOTE)
    if demo.status != DRAFT:
        publish_product(product)
    if demo.status == ARCHIVED:
        archive_product(product)
    return True


# --- the guest order history ------------------------------------------------------------------


def _seed_order_history(staff: Customer, location: Location) -> list[Order]:
    """15.A: one `completed` delivery, one `pending_payment` OXXO order with an active voucher,
    and one `paid` delivery with a CFDI `requested`. Nothing is made when the email has orders."""
    if Order.objects.filter(email=DEMO_EMAIL).exists():
        return []
    variant = Variant.objects.get(sku=HISTORY_SKU)
    receive_stock(
        variant, location, HISTORY_PAID_ORDERS, note=f"{NOTE}: the guest order history"
    )
    actor = f"staff:{staff.pk}"

    completed = _checkout(variant)
    _pay_at_simulator(completed, "card")
    _ship_and_deliver(completed, actor)
    apply_event(completed.pk, "auto_after_7d", actor=actor)

    pending = _checkout(variant)
    _pay_at_simulator(pending, "oxxo")

    paid = _checkout(variant, invoice=DEMO_INVOICE)
    _pay_at_simulator(paid, "card")

    orders = [completed, pending, paid]
    for order, state in zip(
        orders, ("completed", "pending_payment", "paid"), strict=True
    ):
        order.refresh_from_db()
        if order.state != state:
            raise RuntimeError(
                f"seed_demo: order {order.number} is {order.state}, expected {state}"
            )
    return orders


def _checkout(variant: Variant, *, invoice: dict[str, str] | None = None) -> Order:
    """One unit of `variant` through the checkout: the request is validated as the endpoint
    validates it, then the cart becomes a `pending_payment` order (T1)."""
    body: dict[str, Any] = {
        "email": DEMO_EMAIL,
        "fulfillment_method": "delivery",
        "address_payload": DEMO_ADDRESS,
    }
    if invoice is not None:
        body["invoice"] = invoice
    request = CheckoutRequestSerializer(data=body)
    request.is_valid(raise_exception=True)
    data = request.validated_data
    cart = Cart.objects.create(fulfillment_method=data["fulfillment_method"])
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    return create_order_from_cart(
        cart,
        email=data["email"],
        fulfillment_method=data["fulfillment_method"],
        address_or_location=data["address_payload"],
        phone=data["phone"],
        customer_note=data["customer_note"],
        invoice=data.get("invoice"),
    )


def _pay_at_simulator(order: Order, outcome: str) -> None:
    """Press a simulator button for the order's checkout, then hand the payment to the store.

    No notification is queued: the seed passes the payment on itself, as the reconciliation job
    does (9.7). `card` is "Aprobar con tarjeta": the order is `paid` and its units leave the stock
    (T2). `oxxo` is "Pagar en OXXO": the order stays `pending_payment` with a voucher, and its
    deadline and holds move to the voucher's expiry plus the grace period (9.5). The voucher
    lasts the OXXO window from its creation (G74, ADR-0074).
    """
    provider: Any = providers.payment_provider()
    preference = provider.find_preferences(str(order.public_id))[-1]
    payment_id = outcomes.record_outcome(provider, preference, outcome, notify=False)
    process_provider_payment(provider.code, provider.fetch_payment(payment_id))


def _ship_and_deliver(order: Order, actor: str) -> None:
    """`paid` to `delivered`, as staff and the mock carrier do it: "Pasar a preparación" (T7), a
    shipment with a blank tracking number (T10), then "Entregado" on the tracking page (T11)."""
    apply_event(order.pk, "auto", actor=actor)
    carrier: Any = providers.carrier()
    ref = carrier.create_shipment(order)
    shipment = Shipment.objects.create(
        order=order,
        carrier=ref.carrier,
        tracking_number=ref.tracking_number,
        tracking_url=ref.tracking_url,
    )
    apply_event(order.pk, "shipment_created", actor=actor)
    carrier.record_status(ref.tracking_number, ShipmentStatus.DELIVERED)
    sync_shipments([shipment.pk])


# --- reset ------------------------------------------------------------------------------------


def reset() -> None:
    """Empty every table, the order-number sequences and the three file stores (`MOCK_STORE_DIR`,
    `EMAIL_FILE_DIR`, `MEDIA_ROOT`). The tables' own id sequences restart with the flush."""
    call_command("flush", interactive=False, verbosity=0)
    _drop_order_number_sequences()
    for folder in (
        settings.MOCK_STORE_DIR,
        settings.EMAIL_FILE_DIR,
        settings.MEDIA_ROOT,
    ):
        _empty(Path(folder))


def _drop_order_number_sequences() -> None:
    """Order numbers come from one sequence per year, created on first use and unknown to the
    flush (`apps/orders/numbering.py`). Dropped, so the first order is `CN-<year>-000001` again."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT sequencename FROM pg_sequences "
            "WHERE schemaname = current_schema() "
            "AND sequencename ~ '^order_number_seq_[0-9]+$'"
        )
        for (name,) in cursor.fetchall():
            cursor.execute(f"DROP SEQUENCE {connection.ops.quote_name(name)}")


def _empty(folder: Path) -> None:
    """Remove what the folder holds and keep the folder, which may be a mount point."""
    if not folder.is_dir():
        return
    for child in folder.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
