"""Catalog serializers. Only the write path T2.5 needs; the public read API arrives with Phase 3."""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.catalog.models import Product
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
