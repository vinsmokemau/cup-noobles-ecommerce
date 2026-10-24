"""Catalog admin (SPEC.md §4.4, T3.3).

The owner adds and edits products here. Status changes only through the "Publicar" and
"Archivar" actions, which call the catalog services, so `published_at` is always set with
`active` and a published slug is never edited. Money is shown from integer centavos.
"""

import json

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import (
    Count,
    F,
    IntegerField,
    Max,
    Min,
    OuterRef,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpRequest

from apps.catalog.models import (
    Brand,
    Category,
    Franchise,
    Product,
    ProductImage,
    ProductType,
    Variant,
)
from apps.catalog.services import (
    DUPLICATE_OPTIONS_CODE,
    archive_product,
    check_option_keys,
    duplicate_product,
    publish_product,
    resolve_variant_axes,
)
from apps.inventory.models import StockItem


def format_centavos(cents: int) -> str:
    pesos, centavos = divmod(cents, 100)
    return f"${pesos:,}.{centavos:02d}"


class VariantInlineFormSet(forms.BaseInlineFormSet):
    """Checks every variant's option keys against the product's axes, and rejects duplicates.

    The services do the same for `add_variant`; here the whole submission is checked at once, so
    a duplicate becomes a form error and never reaches the unique index.
    """

    def clean(self) -> None:
        super().clean()
        product = self.instance
        if any(self.errors) or product.product_type_id is None:
            return
        axes = resolve_variant_axes(product)
        seen: set[str] = set()
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not data or data.get("DELETE") or "options" not in data:
                continue
            options = data["options"]
            try:
                check_option_keys(axes, options)
            except ValidationError as error:
                form.add_error("options", error.error_dict["options"])
                continue
            key = json.dumps(options, sort_keys=True)
            if key in seen:
                form.add_error(
                    "options",
                    ValidationError(
                        "This product already has a variant with these options.",
                        code=DUPLICATE_OPTIONS_CODE,
                    ),
                )
            seen.add(key)


class VariantInline(admin.TabularInline):
    model = Variant
    formset = VariantInlineFormSet
    extra = 0
    ordering = ("position", "pk")
    fields = (
        "sku",
        "options",
        "price_cents",
        "compare_at_cents",
        "cost_cents",
        "weight_grams",
        "requires_shipping",
        "is_active",
        "position",
        "barcode",
        "purchase_limit",
        "is_preorder",
        "preorder_limit",
        "expected_release_date",
    )


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    ordering = ("position", "pk")
    fields = ("storage_key", "alt", "variant", "position", "width", "height")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only the variants of the product being edited.
        if db_field.name == "variant":
            match = request.resolver_match
            product_id = match.kwargs.get("object_id") if match else None
            kwargs["queryset"] = Variant.objects.filter(product_id=product_id or 0)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank means "generate it from the name" (T3.2).
        self.fields["slug"].required = False


def _subquery(queryset: QuerySet, aggregate) -> Subquery:
    return Subquery(
        queryset.order_by().values("product").annotate(value=aggregate).values("value"),
        output_field=IntegerField(),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    inlines = (VariantInline, ProductImageInline)
    list_display = (
        "name",
        "product_type",
        "status",
        "variant_count",
        "available_stock",
        "price_range",
    )
    list_filter = ("status", "product_type", "franchise", "brand")
    search_fields = ("name", "variants__sku")
    actions = ("publish", "archive", "duplicate")
    list_select_related = ("product_type",)
    readonly_fields = (
        "status",
        "published_at",
        "public_id",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        variants = Variant.objects.filter(product=OuterRef("pk"))
        # available = on_hand - reserved - safety_stock, never negative (CR-04), summed per product.
        stock = (
            StockItem.objects.filter(variant__product=OuterRef("pk"))
            .order_by()
            .values("variant__product")
            .annotate(
                value=Sum(
                    Greatest(Value(0), F("on_hand") - F("reserved") - F("safety_stock"))
                )
            )
            .values("value")
        )
        return (
            super()
            .get_queryset(request)
            .annotate(
                _variant_count=Coalesce(_subquery(variants, Count("pk")), Value(0)),
                _price_min=_subquery(variants, Min("price_cents")),
                _price_max=_subquery(variants, Max("price_cents")),
                _available=Coalesce(
                    Subquery(stock, output_field=IntegerField()), Value(0)
                ),
            )
        )

    def get_readonly_fields(self, request: HttpRequest, obj: Product | None = None):
        fields = super().get_readonly_fields(request, obj)
        # A published slug is immutable (T3.2).
        if obj is not None and obj.published_at is not None:
            return (*fields, "slug")
        return fields

    @admin.display(description="Variantes", ordering="_variant_count")
    def variant_count(self, obj: Product) -> int:
        return obj._variant_count  # type: ignore[attr-defined]

    @admin.display(description="Stock disponible", ordering="_available")
    def available_stock(self, obj: Product) -> int:
        return obj._available  # type: ignore[attr-defined]

    @admin.display(description="Precio", ordering="_price_min")
    def price_range(self, obj: Product) -> str:
        low, high = obj._price_min, obj._price_max  # type: ignore[attr-defined]
        if low is None:
            return "—"
        if low == high:
            return format_centavos(low)
        return f"{format_centavos(low)} – {format_centavos(high)}"

    @admin.action(description="Publicar")
    def publish(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        for product in queryset:
            publish_product(product)
        self.message_user(request, f"Publicados: {queryset.count()}.")

    @admin.action(description="Archivar")
    def archive(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        for product in queryset:
            archive_product(product)
        self.message_user(request, f"Archivados: {queryset.count()}.")

    @admin.action(description="Duplicar producto")
    def duplicate(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        copies = [duplicate_product(product) for product in queryset]
        self.message_user(
            request,
            "Copias en borrador: " + ", ".join(copy.name for copy in copies) + ".",
            messages.SUCCESS,
        )


@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "position")
    search_fields = ("name", "code")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "position")
    search_fields = ("name", "slug")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    search_fields = ("name", "slug")


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    search_fields = ("name", "slug")
