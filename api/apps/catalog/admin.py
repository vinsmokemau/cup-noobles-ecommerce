"""Catalog admin (SPEC.md §4.4, T3.3).

The owner adds and edits products here. Status changes only through the "Publicar" and
"Archivar" actions, which call the catalog services, so `published_at` is always set with
`active` and a published slug is never edited. Money is shown from integer centavos.
"""

import json
from typing import Any

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

from apps.catalog.attribute_fields import (
    FIELD_PREFIX,
    build_attribute_fields,
    collect_attributes,
)
from apps.catalog.images import process_image
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


class ProductImageForm(forms.ModelForm):
    """The owner uploads a file; the storage key and size come from `process_image` (T3.5)."""

    file = forms.ImageField(required=False, label="Imagen")

    class Meta:
        model = ProductImage
        fields = ("alt", "variant", "position")

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if not self.instance.storage_key and not cleaned.get("file"):
            self.add_error("file", "Sube una imagen.")
        return cleaned

    def save(self, commit: bool = True) -> ProductImage:
        upload = self.cleaned_data.get("file")
        if upload:
            stored = process_image(upload)
            self.instance.storage_key = stored.storage_key
            self.instance.width = stored.width
            self.instance.height = stored.height
        return super().save(commit)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageForm
    extra = 0
    ordering = ("position", "pk")
    fields = ("file", "alt", "variant", "position", "storage_key", "width", "height")
    readonly_fields = ("storage_key", "width", "height")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only the variants of the product being edited.
        if db_field.name == "variant":
            match = request.resolver_match
            product_id = match.kwargs.get("object_id") if match else None
            kwargs["queryset"] = Variant.objects.filter(product_id=product_id or 0)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProductAdminForm(forms.ModelForm):
    # `attr_<key>` fields declared by `ProductAdmin.get_form` for the chosen product type (T3.4).
    attribute_fields: dict[str, forms.Field] = {}

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank means "generate it from the name" (T3.2).
        self.fields["slug"].required = False

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if self.attribute_fields:
            # Set before the model's own validation so the schema check sees the typed values.
            self.instance.attributes = collect_attributes(
                cleaned, self.attribute_fields
            )
        return cleaned

    def _update_errors(self, errors: ValidationError) -> None:
        # The model reports schema failures on "attributes", a field this form may not have:
        # point each one at its `attr_<key>` field through the JSON pointer ("/numero").
        error_dict = getattr(errors, "error_dict", None)
        if self.attribute_fields and error_dict and "attributes" in error_dict:
            for error in error_dict.pop("attributes"):
                pointer = (error.params or {}).get("pointer", "")
                name = FIELD_PREFIX + pointer.removeprefix("/").split("/")[0]
                target = name if name in self.attribute_fields else None
                self.add_error(target, error)
        super()._update_errors(errors)  # type: ignore[misc]


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

    class Media:
        js = ("catalog/admin/product_type_reload.js",)

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

    def get_form(  # type: ignore[override]
        self, request: HttpRequest, obj: Product | None = None, **kwargs: Any
    ):
        """Declare one form field per property of the chosen type's schema (T3.4).

        The type is read from the submitted form, then from `?product_type=` (the add page reloads
        with it when the select changes), then from the product. With none, or with a schema the
        widget cannot read, the raw `attributes` JSON field stays.
        """
        fields = self._attribute_fields(request, obj)
        if fields is not None:
            kwargs["form"] = type(
                "ProductAttributesForm",
                (self.form,),
                {"attribute_fields": fields, **fields},
            )
        return super().get_form(request, obj, **kwargs)

    def get_exclude(self, request: HttpRequest, obj: Product | None = None):
        # The typed fields replace the raw JSON field.
        if self._attribute_fields(request, obj) is not None:
            return ("attributes",)
        return super().get_exclude(request, obj)

    def _attribute_fields(
        self, request: HttpRequest, obj: Product | None
    ) -> dict[str, forms.Field] | None:
        # Built once per request: get_form runs several times while the page is assembled.
        if not hasattr(request, "_attribute_fields"):
            product_type = self._chosen_type(request, obj)
            current = obj.attributes if obj is not None else {}
            request._attribute_fields = (  # type: ignore[attr-defined]
                None
                if product_type is None
                else build_attribute_fields(product_type.attribute_schema, current)
            )
        return request._attribute_fields  # type: ignore[attr-defined,no-any-return]

    @staticmethod
    def _chosen_type(request: HttpRequest, obj: Product | None) -> ProductType | None:
        raw = request.POST.get("product_type") or request.GET.get("product_type")
        if raw:
            try:
                return ProductType.objects.filter(pk=int(raw)).first()
            except ValueError:
                return None
        return obj.product_type if obj is not None else None

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
