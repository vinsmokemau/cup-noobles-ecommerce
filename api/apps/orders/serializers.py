"""Customer-facing order status (SPEC.md T6.7b). Nothing here exposes costs or internal notes."""

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
