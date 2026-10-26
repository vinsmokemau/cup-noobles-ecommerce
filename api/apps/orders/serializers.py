"""Customer-facing order status (SPEC.md T6.7b) and the checkout body (T8.4). Nothing here
exposes costs or internal notes."""

from rest_framework import serializers

from apps.orders.models import Order, OrderLine, Shipment


class OrderLookupRequestSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=64, trim_whitespace=True)
    email = serializers.CharField(max_length=254, trim_whitespace=True)


class OrderStatusLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = [
            "sku",
            "product_name",
            "options_snapshot",
            "image_key",
            "quantity",
            "unit_price_cents",
            "line_total_cents",
            "is_preorder",
            "expected_release_date",
        ]


class OrderStatusShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = [
            "carrier",
            "tracking_number",
            "tracking_url",
            "shipped_at",
            "delivered_at",
        ]


class OrderStatusSerializer(serializers.ModelSerializer):
    lines = OrderStatusLineSerializer(many=True, read_only=True)
    shipments = OrderStatusShipmentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "number",
            "public_id",
            "state",
            "fulfillment_method",
            "shipping_rate_name",
            "subtotal_cents",
            "shipping_cents",
            "discount_cents",
            "total_cents",
            "tax_included_cents",
            "currency",
            "payment_deadline_at",
            "placed_at",
            "paid_at",
            "shipped_at",
            "completed_at",
            "cancelled_at",
            "lines",
            "shipments",
        ]


class CheckoutAddressSerializer(serializers.Serializer):
    """The delivery address given in the request, frozen into `order.shipping_address` (T8.2).
    The fields are the NOT NULL columns of `address` in `spec/schema.sql`."""

    recipient_name = serializers.CharField(max_length=200)
    street = serializers.CharField(max_length=200)
    ext_number = serializers.CharField(max_length=40)
    int_number = serializers.CharField(max_length=40, allow_blank=True, default="")
    neighborhood = serializers.CharField(max_length=200)
    municipality = serializers.CharField(max_length=200)
    state_code = serializers.CharField(max_length=3)
    postal_code = serializers.RegexField(r"^[0-9]{5}$", max_length=5)
    delivery_notes = serializers.CharField(max_length=500, allow_blank=True, default="")


class CheckoutRequestSerializer(serializers.Serializer):
    """`POST /api/checkout/` in Release 1: delivery only. A saved `address_id` and a
    `pickup_location_id` are Release 2 (T8.11)."""

    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=40, allow_blank=True, default="")
    # A plain field, not a ChoiceField: a one-value enum would collide with the order's own
    # `fulfillment_method` enum in the OpenAPI components.
    fulfillment_method = serializers.CharField(
        help_text="`delivery` is the only method in Release 1."
    )
    address_payload = CheckoutAddressSerializer()
    customer_note = serializers.CharField(max_length=1000, allow_blank=True, default="")

    def validate_fulfillment_method(self, value: str) -> str:
        if value != "delivery":
            raise serializers.ValidationError("Solo ofrecemos envío a domicilio.")
        return value


class CheckoutResponseSerializer(serializers.Serializer):
    order_number = serializers.CharField()
    order_public_id = serializers.UUIDField()
    checkout_url = serializers.CharField()


class CheckoutLineErrorSerializer(serializers.Serializer):
    variant_public_id = serializers.UUIDField()
    sku = serializers.CharField()
    code = serializers.ChoiceField(choices=["unavailable", "insufficient_stock"])
    requested = serializers.IntegerField()
    available = serializers.IntegerField(allow_null=True)


class CheckoutLinesUnavailableSerializer(serializers.Serializer):
    code = serializers.CharField()
    line_errors = CheckoutLineErrorSerializer(many=True)
