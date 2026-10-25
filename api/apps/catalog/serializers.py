"""Catalog serializers. The write path of T2.5 and the public availability of T5.3."""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.availability import availability
from apps.catalog.models import Product, Variant
from apps.catalog.validation import ATTRIBUTES_FIELD, validate_attributes


class ProductWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["product_type", "slug", "name", ATTRIBUTES_FIELD]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        product_type = attrs.get("product_type") or getattr(
            self.instance, "product_type", None
        )
        if product_type is not None and (
            ATTRIBUTES_FIELD in attrs or "product_type" in attrs
        ):
            attributes = (
                attrs[ATTRIBUTES_FIELD]
                if ATTRIBUTES_FIELD in attrs
                else getattr(self.instance, ATTRIBUTES_FIELD, {})
            )
            try:
                validate_attributes(attributes, product_type.attribute_schema)
            except DjangoValidationError as error:
                raise serializers.ValidationError(
                    {ATTRIBUTES_FIELD: error.message_dict[ATTRIBUTES_FIELD]}
                ) from error
        return attrs


class AvailabilitySerializer(serializers.Serializer):
    """`{"status": "in_stock" | "low_stock" | "out_of_stock"}`; no raw counts (D10 stand-in)."""

    status = serializers.ChoiceField(choices=["in_stock", "low_stock", "out_of_stock"])


class VariantAvailabilitySerializer(serializers.ModelSerializer):
    """The availability block the variant payload of T5.1 carries."""

    availability = serializers.SerializerMethodField()

    class Meta:
        model = Variant
        fields = ["public_id", "availability"]

    @extend_schema_field(AvailabilitySerializer)
    def get_availability(self, variant: Variant) -> dict[str, str]:
        return availability(variant)
