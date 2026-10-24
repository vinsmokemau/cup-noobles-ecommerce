"""Catalog tables (§4.4, `spec/schema.sql` CATALOG).

Defaults are also set in the database (`db_default`), so a raw INSERT gets them. Foreign keys
carry no automatic index: the schema names the ones it wants. The `jsonb_typeof` checks, the
generated `search_tsv` column and `product_image_variant_fk` live in the migration's `RunSQL`.
"""

import uuid
from typing import Any

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import F, Q, Value
from django.utils import timezone

from apps.catalog.validation import validate_attributes
from apps.core.db import GEN_RANDOM_UUID, NOW
from apps.core.fields import CITextField

DEFAULT_ATTRIBUTE_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def default_attribute_schema() -> dict:
    return {**DEFAULT_ATTRIBUTE_SCHEMA, "properties": {}}


def json_default(value: object) -> Value:
    return Value(value, output_field=models.JSONField())


class ProductType(models.Model):
    code = CITextField(unique=True)
    name = models.TextField()
    attribute_schema = models.JSONField(
        default=default_attribute_schema,
        db_default=json_default(DEFAULT_ATTRIBUTE_SCHEMA),
    )
    variant_axes = models.JSONField(default=list, db_default=json_default([]))
    filterable_keys = models.JSONField(default=list, db_default=json_default([]))
    position = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "product_type"

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        db_index=False,
    )
    slug = CITextField(unique=True)
    name = models.TextField()
    description = models.TextField(default="", db_default="", blank=True)
    position = models.IntegerField(default=0, db_default=0)
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "category"
        indexes = [models.Index(fields=["parent"], name="category_parent_idx")]

    def __str__(self) -> str:
        return self.name


class Franchise(models.Model):
    """The IP: Pokémon, One Piece, Zelda."""

    slug = CITextField(unique=True)
    name = models.TextField()
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "franchise"

    def __str__(self) -> str:
        return self.name


class Brand(models.Model):
    """The maker: Good Smile Company, Bandai, Konami."""

    slug = CITextField(unique=True)
    name = models.TextField()
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "brand"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        ARCHIVED = "archived"

    public_id = models.UUIDField(
        default=uuid.uuid4, db_default=GEN_RANDOM_UUID, unique=True, editable=False
    )
    product_type = models.ForeignKey(
        ProductType, on_delete=models.PROTECT, db_index=False
    )
    brand = models.ForeignKey(
        Brand, null=True, blank=True, on_delete=models.SET_NULL, db_index=False
    )
    franchise = models.ForeignKey(
        Franchise, null=True, blank=True, on_delete=models.SET_NULL, db_index=False
    )
    slug = CITextField(unique=True)
    name = models.TextField()
    subtitle = models.TextField(default="", db_default="", blank=True)
    description_md = models.TextField(default="", db_default="", blank=True)
    status = models.TextField(
        choices=Status.choices, default=Status.DRAFT, db_default=Status.DRAFT
    )
    # Shape is governed by product_type.attribute_schema.
    attributes = models.JSONField(default=dict, db_default=json_default({}))
    # Overrides product_type.variant_axes when a product is unusual.
    variant_axes = models.JSONField(null=True, blank=True)
    # Home-page featured products, in featured_position order (G28, ADR-0030).
    is_featured = models.BooleanField(default=False, db_default=False)
    featured_position = models.IntegerField(default=0, db_default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    categories = models.ManyToManyField(
        Category, through="ProductCategory", related_name="products"
    )

    class Meta:
        db_table = "product"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["draft", "active", "archived"]),
                name="product_status_check",
            ),
            models.CheckConstraint(
                condition=Q(featured_position__gte=0),
                name="product_featured_position_check",
            ),
            models.CheckConstraint(
                condition=~Q(status="active") | Q(published_at__isnull=False),
                name="product_active_needs_publish",
            ),
        ]
        indexes = [
            GinIndex(
                fields=["attributes"],
                opclasses=["jsonb_path_ops"],
                name="product_attributes_gin",
            ),
            GinIndex(
                fields=["name"], opclasses=["gin_trgm_ops"], name="product_name_trgm"
            ),
            models.Index(
                F("status"),
                F("published_at").desc(),
                condition=Q(status="active"),
                name="product_active_idx",
            ),
            models.Index(fields=["product_type"], name="product_type_idx"),
            models.Index(fields=["franchise"], name="product_franchise_idx"),
            models.Index(
                fields=["featured_position"],
                condition=Q(status="active", is_featured=True),
                name="product_featured_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        validate_attributes(self.attributes, self.product_type.attribute_schema)

    def save(self, *args: Any, **kwargs: Any) -> None:
        update_fields = kwargs.get("update_fields")
        if update_fields is None or {"attributes", "product_type"} & set(update_fields):
            self.clean()
        super().save(*args, **kwargs)


class ProductCategory(models.Model):
    pk = models.CompositePrimaryKey("product", "category")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_index=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_index=False)

    class Meta:
        db_table = "product_category"
        indexes = [models.Index(fields=["category"], name="product_category_cat_idx")]


class Variant(models.Model):
    """The sellable unit. A product with no variation has exactly one, with options `{}`."""

    public_id = models.UUIDField(
        default=uuid.uuid4, db_default=GEN_RANDOM_UUID, unique=True, editable=False
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants", db_index=False
    )
    sku = CITextField(unique=True)
    barcode = models.TextField(null=True, blank=True)
    # Values along the product's variant_axes: {"talla": "L", "color": "negro"}.
    options = models.JSONField(default=dict, db_default=json_default({}))
    price_cents = models.IntegerField()
    compare_at_cents = models.IntegerField(null=True, blank=True)
    cost_cents = models.IntegerField(null=True, blank=True)
    weight_grams = models.IntegerField(default=0, db_default=0)
    requires_shipping = models.BooleanField(default=True, db_default=True)
    is_active = models.BooleanField(default=True, db_default=True)
    position = models.IntegerField(default=0, db_default=0)
    # Per-customer purchase limit in units; NULL means no limit (G31, ADR-0030).
    purchase_limit = models.IntegerField(null=True, blank=True)
    # Pre-order stock is not drawn from stock_item.
    is_preorder = models.BooleanField(default=False, db_default=False)
    preorder_limit = models.IntegerField(null=True, blank=True)
    preorder_committed = models.IntegerField(default=0, db_default=0)
    expected_release_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "variant"
        constraints = [
            models.CheckConstraint(
                condition=Q(price_cents__gte=0), name="variant_price_cents_check"
            ),
            models.CheckConstraint(
                condition=Q(compare_at_cents__isnull=True) | Q(compare_at_cents__gte=0),
                name="variant_compare_at_cents_check",
            ),
            models.CheckConstraint(
                condition=Q(cost_cents__isnull=True) | Q(cost_cents__gte=0),
                name="variant_cost_cents_check",
            ),
            models.CheckConstraint(
                condition=Q(weight_grams__gte=0), name="variant_weight_grams_check"
            ),
            models.CheckConstraint(
                condition=Q(purchase_limit__isnull=True) | Q(purchase_limit__gt=0),
                name="variant_purchase_limit_check",
            ),
            models.CheckConstraint(
                condition=Q(preorder_limit__isnull=True) | Q(preorder_limit__gte=0),
                name="variant_preorder_limit_check",
            ),
            models.CheckConstraint(
                condition=Q(preorder_committed__gte=0),
                name="variant_preorder_committed_check",
            ),
            models.CheckConstraint(
                condition=Q(is_preorder=False) | Q(expected_release_date__isnull=False),
                name="variant_preorder_needs_date",
            ),
            models.CheckConstraint(
                condition=Q(preorder_limit__isnull=True)
                | Q(preorder_committed__lte=F("preorder_limit")),
                name="variant_preorder_within_limit",
            ),
            # `variant_product_options_uq` is a unique index, created by `RunSQL` (migration 0002).
        ]
        indexes = [
            models.Index(fields=["product"], name="variant_product_idx"),
            GinIndex(
                fields=["options"],
                opclasses=["jsonb_path_ops"],
                name="variant_options_gin",
            ),
        ]

    def __str__(self) -> str:
        return str(self.sku)


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images", db_index=False
    )
    # The database constraint is `product_image_variant_fk`, added by RunSQL.
    variant = models.ForeignKey(
        Variant,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=False,
        db_constraint=False,
    )
    storage_key = models.TextField()  # an object-storage key, not a URL
    alt = models.TextField(default="", db_default="", blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    position = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "product_image"
        indexes = [
            models.Index(
                fields=["product", "position"], name="product_image_product_idx"
            )
        ]
