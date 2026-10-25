"""Cart request and response shapes (SPEC.md T7.1).

The cart stores no prices (CR-03). Live prices, availability, totals and the shipping quote join
the response in T7.3, T7.4 and T7.6.
"""

import re

from rest_framework import serializers

from apps.carts.models import Cart, CartLine
from apps.catalog.models import Variant

MAX_QUANTITY = 99
POSTAL_CODE = re.compile(r"[0-9]{5}")


class CartLineWriteSerializer(serializers.Serializer):
    variant_public_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)

    def validate_variant_public_id(self, value):
        if not Variant.objects.filter(public_id=value).exists():
            raise serializers.ValidationError("No encontramos ese producto.")
        return value


class CartLineQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)


class CartFulfillmentSerializer(serializers.Serializer):
    # R1 offers delivery only; "pickup" joins in R2 with `pickup_location_id` (OA-08).
    method = serializers.ChoiceField(choices=["delivery"])
    postal_code = serializers.RegexField(POSTAL_CODE, max_length=5)


class CartLineSerializer(serializers.ModelSerializer):
    variant_public_id = serializers.UUIDField(source="variant.public_id")

    class Meta:
        model = CartLine
        fields = ["id", "variant_public_id", "quantity"]


class CartSerializer(serializers.ModelSerializer):
    lines = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["fulfillment_method", "lines"]

    def get_lines(self, cart: Cart) -> list[dict]:
        rows = cart.lines.select_related("variant").order_by("added_at", "id")
        return CartLineSerializer(rows, many=True).data
