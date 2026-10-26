"""Order creation (SPEC.md T8.2, REQ-010, REQ-020).

`create_order_from_cart` turns a cart into a `pending_payment` order in one transaction: it locks
the stock, re-validates every line, freezes what the customer was shown, and hands the draft to
`apply_event("checkout_submitted")` (T1), which reserves the units and opens the payment. Any
failure rolls the whole thing back, so a refused checkout leaves no order and no reservation.
"""

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.carts.models import Cart
from apps.carts.serializers import is_sellable
from apps.catalog.models import ProductImage
from apps.inventory import services as inventory
from apps.orders.models import Order, OrderLine
from apps.orders.numbering import next_order_number
from apps.orders.pricing import compute_totals
from apps.orders.state_machine import apply_event
from apps.shipping.services import QuoteError, quote

UNAVAILABLE = "unavailable"
INSUFFICIENT_STOCK = "insufficient_stock"


@dataclass(frozen=True)
class LineError:
    """Why one cart line cannot be bought. `available` is set for `insufficient_stock`."""

    variant_public_id: str
    sku: str
    code: str
    requested: int
    available: int | None = None


class CheckoutError(Exception):
    """The checkout was refused and nothing was created."""


class EmptyCart(CheckoutError):
    pass


class LinesUnavailable(CheckoutError):
    """One or more lines failed; `line_errors` lists every one of them (the 409 body of T8.4)."""

    def __init__(self, line_errors: list[LineError]) -> None:
        self.line_errors = line_errors
        super().__init__(f"{len(line_errors)} cart line(s) cannot be bought")


class ShippingUnavailable(CheckoutError):
    """No shipping price exists for the address; the message is shown to the customer."""


class UnsupportedFulfillment(CheckoutError):
    """Release 1 takes delivery only; pickup is Release 2 (OA-08)."""


def _image_key(line) -> str:
    images = ProductImage.objects.filter(product_id=line.variant.product_id)
    own = images.filter(variant_id=line.variant_id).order_by("position", "pk").first()
    image = (
        own or images.filter(variant__isnull=True).order_by("position", "pk").first()
    )
    return image.storage_key if image else ""


@transaction.atomic
def create_order_from_cart(
    cart: Cart,
    *,
    email: str,
    fulfillment_method: str,
    address_or_location: dict[str, Any],
    customer=None,
    phone: str = "",
    customer_note: str = "",
    idempotency_key: str | None = None,
    idempotency_fingerprint: str | None = None,
) -> Order:
    """Create the order for `cart` and move it to `pending_payment`.

    Release 1: `fulfillment_method` is `delivery` and `address_or_location` is the address
    given in the request, with its `postal_code`. A saved address and a pickup location are
    Release 2. Raises `EmptyCart`, `LinesUnavailable` (every failing line at once),
    `ShippingUnavailable` or `UnsupportedFulfillment`; each leaves the database as it was.
    """
    if fulfillment_method != Order.FulfillmentMethod.DELIVERY:
        raise UnsupportedFulfillment("Solo ofrecemos envío a domicilio.")

    # Sorted by variant, so crossed carts take their locks in the same order (P8-V11).
    cart_lines = list(
        cart.lines.select_related("variant__product").order_by("variant_id")
    )
    if not cart_lines:
        raise EmptyCart("El carrito está vacío.")
    inventory.lock_variants(line.variant_id for line in cart_lines)

    errors = _line_errors(cart_lines)
    if errors:
        raise LinesUnavailable(errors)

    subtotal = compute_totals(
        [_Priced(line.variant.price_cents, line.quantity) for line in cart_lines], 0, 0
    ).subtotal_cents
    try:
        shipping = quote(str(address_or_location.get("postal_code", "")), subtotal)
    except QuoteError as error:
        raise ShippingUnavailable(str(error)) from error
    totals = compute_totals(
        [_Priced(line.variant.price_cents, line.quantity) for line in cart_lines],
        shipping.price_cents,
        0,
    )

    order = Order.objects.create(
        number=next_order_number(),
        customer=customer,
        email=email,
        phone=phone,
        state="draft",
        fulfillment_method=fulfillment_method,
        shipping_address=address_or_location,
        shipping_rate_name=shipping.name,
        subtotal_cents=totals.subtotal_cents,
        shipping_cents=totals.shipping_cents,
        discount_cents=totals.discount_cents,
        total_cents=totals.total_cents,
        tax_included_cents=totals.tax_included_cents,
        has_preorder_items=False,
        earliest_release_date=None,
        customer_note=customer_note,
        cart_token=cart.token,
        idempotency_key=idempotency_key,
        idempotency_fingerprint=idempotency_fingerprint,
    )
    OrderLine.objects.bulk_create(
        OrderLine(
            order=order,
            variant=line.variant,
            sku=line.variant.sku,
            product_name=line.variant.product.name,
            options_snapshot=line.variant.options,
            image_key=_image_key(line),
            quantity=line.quantity,
            unit_price_cents=line.variant.price_cents,
            line_total_cents=line.variant.price_cents * line.quantity,
        )
        for line in cart_lines
    )
    return apply_event(order.pk, "checkout_submitted", actor="customer")


@dataclass
class _Priced:
    unit_price_cents: int
    quantity: int


def _line_errors(cart_lines) -> list[LineError]:
    """Every line that cannot be bought: unsellable first, then the stock shortfalls."""
    errors = []
    sellable = []
    for line in cart_lines:
        if is_sellable(line.variant):
            sellable.append(line)
        else:
            errors.append(
                LineError(
                    str(line.variant.public_id),
                    line.variant.sku,
                    UNAVAILABLE,
                    line.quantity,
                )
            )
    for variant, requested, available in inventory.shortfalls(
        [(line.variant, line.quantity) for line in sellable]
    ):
        errors.append(
            LineError(
                str(variant.public_id),
                variant.sku,
                INSUFFICIENT_STOCK,
                requested,
                available,
            )
        )
    return errors
