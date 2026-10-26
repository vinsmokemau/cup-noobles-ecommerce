"""Customer-facing order status (SPEC.md T6.7b) and the checkout body (T8.4). Nothing here
exposes costs or internal notes."""

from rest_framework import serializers

from apps.invoicing import catalogs
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


class CheckoutInvoiceSerializer(serializers.Serializer):
    """The customer's fiscal data for a manual CFDI (T8.7, A8). The RFC format is checked here,
    not in the schema; the codes must be in `api/fixtures/cfdi_catalogs.json`."""

    rfc = serializers.RegexField(
        r"^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$",
        max_length=13,
        error_messages={"invalid": "El RFC no tiene un formato válido."},
    )
    legal_name = serializers.CharField(max_length=300)
    fiscal_postal_code = serializers.RegexField(
        r"^[0-9]{5}$",
        max_length=5,
        error_messages={"invalid": "El código postal fiscal debe tener 5 dígitos."},
    )
    tax_regime = serializers.CharField(max_length=10)
    cfdi_use = serializers.CharField(max_length=10)

    def to_internal_value(self, data):
        # RFCs are uppercase; accept what the customer typed in any case.
        if isinstance(data, dict) and isinstance(data.get("rfc"), str):
            data = {**data, "rfc": data["rfc"].strip().upper()}
        return super().to_internal_value(data)

    def validate_tax_regime(self, value: str) -> str:
        if value not in catalogs.tax_regime_codes():
            raise serializers.ValidationError("Elige un régimen fiscal de la lista.")
        return value

    def validate_cfdi_use(self, value: str) -> str:
        if value not in catalogs.cfdi_use_codes():
            raise serializers.ValidationError("Elige un uso de CFDI de la lista.")
        return value


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
    invoice = CheckoutInvoiceSerializer(
        required=False,
        help_text="Fiscal data to request a CFDI. Without it no request is created.",
    )
    expected_total_cents = serializers.IntegerField(
        min_value=0,
        required=False,
        help_text="The total the customer last saw. A different fresh total returns 409 "
        "`total_changed`; without it nothing is compared.",
    )

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


class CheckoutTotalsSerializer(serializers.Serializer):
    subtotal_cents = serializers.IntegerField()
    shipping_cents = serializers.IntegerField()
    discount_cents = serializers.IntegerField()
    total_cents = serializers.IntegerField()
    tax_included_cents = serializers.IntegerField()


class CheckoutTotalChangedSerializer(serializers.Serializer):
    code = serializers.CharField()
    totals = CheckoutTotalsSerializer()
