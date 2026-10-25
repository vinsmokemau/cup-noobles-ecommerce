"""Cart request and response shapes (SPEC.md T7.1).

The cart stores no prices (CR-03): each read takes `variant.price_cents` as it is now (T7.3).
Each line reports its availability (T7.4) and never changes its quantity; the shipping quote
joins the response in T7.6.

A cart stores no postal code (`spec/schema.sql`), so the quote is computed for the code the request
carries: the fulfillment `POST` body or the `postal_code` query parameter of `GET /api/cart/`.
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.carts.models import Cart, CartLine
from apps.catalog.availability import ANNOTATION, with_available_units
from apps.catalog.models import Product, Variant
from apps.orders.pricing import compute_totals
from apps.shipping.services import QuoteError, ShippingQuote, quote

MAX_QUANTITY = 99
POSTAL_CODE = re.compile(r"[0-9]{5}")

# Per-line availability (T7.4). Release 2 adds `preorder`.
OK = "ok"
REDUCED = "reduced"
UNAVAILABLE = "unavailable"


def is_sellable(variant: Variant) -> bool:
    """An inactive variant, or one of an archived product, cannot be bought (P7-V11)."""
    return variant.is_active and variant.product.status != Product.Status.ARCHIVED


def line_availability(line: CartLine, available: int) -> tuple[str, int | None]:
    """The status and `max_available` of a line; the stored quantity is never touched."""
    if not is_sellable(line.variant) or available <= 0:
        return UNAVAILABLE, None
    if available < line.quantity:
        return REDUCED, available
    return OK, None


class CartLineWriteSerializer(serializers.Serializer):
    variant_public_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)

    def validate_variant_public_id(self, value):
        variant = (
            Variant.objects.select_related("product").filter(public_id=value).first()
        )
        if variant is None or not is_sellable(variant):
            raise serializers.ValidationError("No encontramos ese producto.")
        return value


class CartLineQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)


class CartFulfillmentSerializer(serializers.Serializer):
    # R1 offers delivery only; "pickup" joins in R2 with `pickup_location_id` (OA-08).
    method = serializers.ChoiceField(choices=["delivery"])
    postal_code = serializers.RegexField(POSTAL_CODE, max_length=5)


class ShippingQuoteSerializer(serializers.Serializer):
    price_cents = serializers.IntegerField()
    eta_min_days = serializers.IntegerField()
    eta_max_days = serializers.IntegerField()
    name = serializers.CharField()
    zone = serializers.CharField()


class CartLineSerializer(serializers.ModelSerializer):
    variant_public_id = serializers.UUIDField(source="variant.public_id")
    unit_price_cents = serializers.IntegerField(source="variant.price_cents")
    line_total_cents = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    max_available = serializers.SerializerMethodField()

    class Meta:
        model = CartLine
        fields = [
            "id",
            "variant_public_id",
            "quantity",
            "unit_price_cents",
            "line_total_cents",
            "availability",
            "max_available",
        ]

    def get_line_total_cents(self, line: CartLine) -> int:
        return line.variant.price_cents * line.quantity

    def _availability(self, line: CartLine) -> tuple[str, int | None]:
        return line_availability(line, self.context["available"][line.variant_id])

    @extend_schema_field(serializers.ChoiceField(choices=[OK, REDUCED, UNAVAILABLE]))
    def get_availability(self, line: CartLine) -> str:
        return self._availability(line)[0]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_max_available(self, line: CartLine) -> int | None:
        """Set only on `reduced`: how many units the customer can still have."""
        return self._availability(line)[1]


class CartTotalsSerializer(serializers.Serializer):
    subtotal_cents = serializers.IntegerField()
    shipping_cents = serializers.IntegerField()
    discount_cents = serializers.IntegerField()
    total_cents = serializers.IntegerField()
    tax_included_cents = serializers.IntegerField()


def cart_totals(lines: list, shipping_cents: int = 0) -> dict[str, int]:
    """Shipping is 0 until a quote exists (T7.6); discounts do not exist yet."""
    totals = compute_totals(
        [_PricedLine(line.variant.price_cents, line.quantity) for line in lines],
        shipping_cents=shipping_cents,
        discount_cents=0,
    )
    return asdict(totals)


@dataclass
class _PricedLine:
    unit_price_cents: int
    quantity: int


class CartSerializer(serializers.ModelSerializer):
    """Reads the lines once and builds both `lines` and `totals` from them."""

    fulfillment_method = serializers.CharField(allow_null=True)
    lines = CartLineSerializer(many=True)
    shipping_quote = ShippingQuoteSerializer(allow_null=True)
    totals = CartTotalsSerializer()

    class Meta:
        model = Cart
        fields = ["fulfillment_method", "lines", "shipping_quote", "totals"]

    def to_representation(self, instance: Cart) -> dict[str, Any]:
        rows = list(
            instance.lines.select_related("variant__product").order_by("added_at", "id")
        )
        available = dict(
            with_available_units(
                Variant.objects.filter(pk__in=[row.variant_id for row in rows])
            ).values_list("pk", ANNOTATION)
        )
        subtotal = cart_totals(rows)["subtotal_cents"]
        shipping_quote = self._quote(instance, subtotal)
        return {
            "fulfillment_method": instance.fulfillment_method,
            "lines": CartLineSerializer(
                rows, many=True, context={"available": available}
            ).data,
            "shipping_quote": None
            if shipping_quote is None
            else asdict(shipping_quote),
            "totals": cart_totals(
                rows, shipping_quote.price_cents if shipping_quote else 0
            ),
        }

    def _quote(self, cart: Cart, subtotal_cents: int) -> ShippingQuote | None:
        """A quote exists only for a delivery cart and a postal code; a bad code is a 400."""
        postal_code = self.context.get("postal_code")
        if cart.fulfillment_method != "delivery" or not postal_code:
            return None
        try:
            return quote(postal_code, subtotal_cents)
        except QuoteError as error:
            raise serializers.ValidationError({"postal_code": [str(error)]}) from error
