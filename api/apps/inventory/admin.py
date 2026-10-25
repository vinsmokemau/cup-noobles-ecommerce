"""Inventory admin (SPEC.md §4.4, T4.4).

`on_hand` and `reserved` are never editable here: a raw edit would skip the ledger (CR-05). Staff
change stock through the "Ajustar stock" action, which calls `adjust_stock`. The ledger is a
read-only view. Goods arrive through "Recibir mercancía", which calls `receive_stock` (T4.7, G20).
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path

from apps.catalog.models import Variant
from apps.inventory.errors import AdjustmentBelowReserved, InvalidQuantity
from apps.inventory.models import Location, StockItem, StockLedger
from apps.inventory.services import ADJUSTMENT_REASONS, adjust_stock, receive_stock

REASON_LABELS = {
    StockLedger.Reason.ADJUSTMENT: "Ajuste",
    StockLedger.Reason.DAMAGE: "Merma o daño",
    StockLedger.Reason.COUNT_CORRECTION: "Corrección de conteo",
}


class AdjustStockForm(forms.Form):
    delta = forms.IntegerField(
        label="Cambio de unidades",
        help_text="Positivo suma, negativo resta.",
    )
    reason = forms.ChoiceField(
        label="Motivo",
        choices=[
            (r.value, REASON_LABELS[r])
            for r in StockLedger.Reason
            if r in ADJUSTMENT_REASONS
        ],
    )
    note = forms.CharField(label="Nota", max_length=500)

    def clean_delta(self) -> int:
        delta = self.cleaned_data["delta"]
        if delta == 0:
            raise forms.ValidationError("El cambio no puede ser cero.")
        return delta


class VariantChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: Variant) -> str:
        return f"{obj.sku} — {obj.product.name}"


class ReceiveGoodsForm(forms.Form):
    variant = VariantChoiceField(
        label="Variante",
        queryset=Variant.objects.select_related("product").order_by("sku"),
        empty_label="Elige…",
    )
    location = forms.ModelChoiceField(
        label="Ubicación",
        queryset=Location.objects.filter(is_active=True).order_by("name"),
        empty_label="Elige…",
    )
    quantity = forms.IntegerField(
        label="Cantidad recibida",
        min_value=1,
        error_messages={"min_value": "La cantidad debe ser de al menos 1."},
    )
    note = forms.CharField(label="Nota", max_length=500, required=False)


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = (
        "variant",
        "location",
        "on_hand",
        "reserved",
        "safety_stock",
        "available",
    )
    list_filter = ("location",)
    list_select_related = ("variant", "location")
    search_fields = ("variant__sku", "variant__product__name")
    actions = ("adjust",)
    change_list_template = "admin/inventory/stockitem/change_list.html"
    fields = (
        "variant",
        "location",
        "on_hand",
        "reserved",
        "safety_stock",
        "bin_location",
        "updated_at",
    )
    # `on_hand` and `reserved` are display-only: the services own them (CR-05, CR-06).
    readonly_fields = ("variant", "location", "on_hand", "reserved", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: StockItem | None = None
    ) -> bool:
        return False

    def get_urls(self):
        return [
            path(
                "receive/",
                self.admin_site.admin_view(self.receive_goods),
                name=f"{self.opts.app_label}_{self.opts.model_name}_receive",
            ),
            *super().get_urls(),
        ]

    def receive_goods(self, request: HttpRequest) -> HttpResponse:
        if not self.has_change_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            form = ReceiveGoodsForm(request.POST)
            if form.is_valid():
                variant = form.cleaned_data["variant"]
                quantity = form.cleaned_data["quantity"]
                receive_stock(
                    variant,
                    form.cleaned_data["location"],
                    quantity,
                    actor=request.user,
                    note=form.cleaned_data["note"],
                )
                self.message_user(
                    request,
                    f"Se recibieron {quantity} unidades de {variant.sku}.",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = ReceiveGoodsForm()
        context = {
            **self.admin_site.each_context(request),
            "title": "Recibir mercancía",
            "opts": self.model._meta,
            "form": form,
        }
        return TemplateResponse(
            request, "admin/inventory/stockitem/receive.html", context
        )

    @admin.display(description="Disponible")
    def available(self, obj: StockItem) -> int:
        return max(0, obj.on_hand - obj.reserved - obj.safety_stock)

    @admin.action(description="Ajustar stock", permissions=["change"])
    def adjust(
        self, request: HttpRequest, queryset: QuerySet[StockItem]
    ) -> HttpResponse | None:
        items = list(queryset.select_related("variant", "location").order_by("pk"))
        if len(items) != 1:
            self.message_user(
                request, "Elige un solo registro de stock para ajustar.", messages.ERROR
            )
            return None
        item = items[0]

        if "apply" in request.POST:
            form = AdjustStockForm(request.POST)
            if form.is_valid():
                try:
                    adjust_stock(
                        item.variant,
                        item.location,
                        form.cleaned_data["delta"],
                        reason=form.cleaned_data["reason"],
                        actor=request.user,
                        note=form.cleaned_data["note"],
                    )
                except AdjustmentBelowReserved as error:
                    form.add_error(
                        "delta",
                        f"Hay {error.held_units} unidades apartadas por pedidos; "
                        f"no puedes dejar el stock por debajo de eso.",
                    )
                except InvalidQuantity as error:
                    form.add_error("delta", str(error))
                else:
                    self.message_user(
                        request,
                        f"Stock de {item.variant} ajustado en "
                        f"{form.cleaned_data['delta']:+d}.",
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(request.get_full_path())
        else:
            form = AdjustStockForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Ajustar stock",
            "opts": self.model._meta,
            "item": item,
            "form": form,
            "action_name": "adjust",
            "selected": [item.pk],
        }
        return TemplateResponse(
            request, "admin/inventory/stockitem/adjust.html", context
        )


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    """Append-only history, read-only. Filter by variant and by date."""

    list_display = (
        "created_at",
        "variant",
        "location",
        "delta",
        "balance_after",
        "reason",
        "actor_user_id",
        "note",
    )
    list_filter = (
        ("created_at", admin.DateFieldListFilter),
        "reason",
        ("stock_item__variant", admin.RelatedOnlyFieldListFilter),
    )
    list_select_related = ("stock_item__variant", "stock_item__location")
    search_fields = ("stock_item__variant__sku", "note")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-pk")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: StockLedger | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: StockLedger | None = None
    ) -> bool:
        return False

    @admin.display(description="Variante", ordering="stock_item__variant__sku")
    def variant(self, obj: StockLedger) -> str:
        return str(obj.stock_item.variant)

    @admin.display(description="Ubicación", ordering="stock_item__location__name")
    def location(self, obj: StockLedger) -> str:
        return str(obj.stock_item.location)
