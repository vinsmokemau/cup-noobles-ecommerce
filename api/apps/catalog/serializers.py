"""Catalog serializers. The write path of T2.5, the public availability of T5.3 and the public
catalog payloads of T5.1."""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.availability import (
    IN_STOCK,
    LOW_STOCK,
    OUT_OF_STOCK,
    availability,
)
from apps.catalog.images import derivative_urls
from apps.catalog.models import (
    Category,
    Product,
    ProductImage,
    ProductType,
    Variant,
)
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


# T5.1: the public catalog. Money is integer centavos (CR-01); there is no cost, barcode or raw
# stock count in any payload (D10).

STATUS_ORDER = (IN_STOCK, LOW_STOCK, OUT_OF_STOCK)


class ReferenceSerializer(serializers.Serializer):
    """A brand, franchise or category, by slug."""

    slug = serializers.CharField()
    name = serializers.CharField()


class ProductTypeReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = ["code", "name"]


class ImageSourceSerializer(serializers.Serializer):
    width = serializers.IntegerField()
    url = serializers.CharField()


class PublicImageSerializer(serializers.ModelSerializer):
    """A product image as its derivatives; the original is never given out (T3.5)."""

    sources = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["alt", "width", "height", "sources"]

    @extend_schema_field(ImageSourceSerializer(many=True))
    def get_sources(self, image: ProductImage) -> list[dict[str, object]]:
        return [
            {"width": width, "url": url}
            for width, url in sorted(derivative_urls(image).items())
        ]


class DetailImageSerializer(PublicImageSerializer):
    variant = serializers.SlugRelatedField(
        slug_field="public_id", read_only=True, allow_null=True
    )

    class Meta(PublicImageSerializer.Meta):
        fields = [*PublicImageSerializer.Meta.fields, "variant"]


class PublicVariantSerializer(serializers.ModelSerializer):
    availability = serializers.SerializerMethodField()

    class Meta:
        model = Variant
        fields = [
            "public_id",
            "sku",
            "options",
            "price_cents",
            "compare_at_cents",
            "availability",
        ]

    @extend_schema_field(AvailabilitySerializer)
    def get_availability(self, variant: Variant) -> dict[str, str]:
        return availability(variant)


def product_availability(variants: list[Variant]) -> dict[str, str]:
    """The best status among the sellable variants; a product with none is out of stock."""
    statuses = [availability(variant)["status"] for variant in variants]
    best = min(statuses, key=STATUS_ORDER.index, default=OUT_OF_STOCK)
    return {"status": best}


class ProductCardSerializer(serializers.ModelSerializer):
    """The list entry. Read `public_variants` and `images`, which the view prefetches."""

    product_type = serializers.CharField(source="product_type.code")
    brand = ReferenceSerializer(allow_null=True)
    franchise = ReferenceSerializer(allow_null=True)
    price_cents = serializers.SerializerMethodField()
    compare_at_cents = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "public_id",
            "slug",
            "name",
            "subtitle",
            "product_type",
            "brand",
            "franchise",
            "price_cents",
            "compare_at_cents",
            "availability",
            "image",
        ]

    @staticmethod
    def _cheapest(product: Product) -> Variant | None:
        return min(
            product.public_variants,  # type: ignore[attr-defined]
            key=lambda v: (v.price_cents, v.position, v.pk),
            default=None,
        )

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_price_cents(self, product: Product) -> int | None:
        cheapest = self._cheapest(product)
        return cheapest.price_cents if cheapest else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_compare_at_cents(self, product: Product) -> int | None:
        cheapest = self._cheapest(product)
        return cheapest.compare_at_cents if cheapest else None

    @extend_schema_field(AvailabilitySerializer)
    def get_availability(self, product: Product) -> dict[str, str]:
        return product_availability(product.public_variants)  # type: ignore[attr-defined]

    @extend_schema_field(PublicImageSerializer(allow_null=True))
    def get_image(self, product: Product) -> dict | None:
        images = list(product.images.all())
        return PublicImageSerializer(images[0]).data if images else None


class ProductDetailSerializer(ProductCardSerializer):
    categories = ReferenceSerializer(many=True, source="public_categories")
    variants = PublicVariantSerializer(many=True, source="public_variants")
    images = DetailImageSerializer(many=True)
    related = serializers.SerializerMethodField()

    class Meta(ProductCardSerializer.Meta):
        fields = [
            *ProductCardSerializer.Meta.fields,
            "description_md",
            "attributes",
            "categories",
            "variants",
            "images",
            "related",
        ]

    @extend_schema_field(ProductCardSerializer(many=True))
    def get_related(self, product: Product) -> list[dict]:
        related = getattr(product, "related_products", [])
        return ProductCardSerializer(related, many=True, context=self.context).data


class CategoryNodeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["slug", "name", "description", "children"]

    def get_children(self, category: Category) -> list[dict]:
        return CategoryNodeSerializer(
            getattr(category, "active_children", []), many=True
        ).data


# The schema of a tree node names the node itself, which only exists once the class does.
CategoryNodeSerializer.get_children = extend_schema_field(  # type: ignore[method-assign]
    CategoryNodeSerializer(many=True)
)(CategoryNodeSerializer.get_children)
