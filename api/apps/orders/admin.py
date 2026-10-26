"""Order admin (SPEC.md 8.A, T8.5, REQ-020).

An order is read-only here except for its internal note. `state` is never in the form: staff move
an order through the action bar, which calls `apply_event` and shows a button only for an event
that is legal from the current state (CR-09, CR-10).
"""

from typing import Any

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import path, reverse

from apps.orders.models import Order, OrderEvent, OrderLine
from apps.orders.state_machine import (
    TRANSITIONS,
    GuardFailed,
    IllegalTransition,
    apply_event,
)

EVENT_LABELS = {
    "checkout_submitted": "Enviar a pago",
    "payment_approved": "Marcar pago aprobado",
    "payment_rejected": "Marcar pago rechazado",
    "deadline_passed": "Vencer por falta de pago",
    "cancelled_by_customer": "Cancelar por el cliente",
    "auto": "Pasar a preparación",
    "shipment_created": "Marcar como enviado",
    "marked_delivered": "Marcar como entregado",
    "auto_after_7d": "Completar",
    "cancelled_by_staff": "Cancelar por el personal",
    "refund_issued": "Registrar reembolso total",
    "partial_refund_issued": "Registrar reembolso parcial",
}

# Events that take a typed value from the action bar.
EVENT_NEEDS_REASON = "cancelled_by_staff"


def legal_events(order: Order) -> list[str]:
    """The events `TRANSITIONS` accepts from the order's current state, in table order."""
    return [event for state, event in TRANSITIONS if state == order.state]


def format_money(cents: int | None) -> str:
    """Centavos as pesos for display only; arithmetic stays in integers (CR-01)."""
    if cents is None:
        return "—"
    pesos, centavos = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}${pesos:,}.{centavos:02d} MXN"


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class OrderLineInline(ReadOnlyInline):
    model = OrderLine
    verbose_name = "línea"
    verbose_name_plural = "Líneas"
    fields = (
        "sku",
        "product_name",
        "options_snapshot",
        "quantity",
        "price",
        "total",
    )
    readonly_fields = fields

    @admin.display(description="Precio unitario")
    def price(self, obj: OrderLine) -> str:
        return format_money(obj.unit_price_cents)

    @admin.display(description="Total de la línea")
    def total(self, obj: OrderLine) -> str:
        return format_money(obj.line_total_cents)


class OrderEventInline(ReadOnlyInline):
    model = OrderEvent
    verbose_name = "evento"
    verbose_name_plural = "Historial"
    fields = ("created_at", "event", "from_state", "to_state", "actor", "payload")
    readonly_fields = fields
    ordering = ("created_at", "pk")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "state",
        "email",
        "fulfillment_method",
        "total",
        "created_at",
    )
    list_filter = ("state", "fulfillment_method")
    search_fields = ("number", "email", "phone")
    ordering = ("-created_at", "-pk")
    date_hierarchy = "created_at"
    inlines = (OrderLineInline, OrderEventInline)
    change_form_template = "admin/orders/order/change_form.html"

    fieldsets = (
        (
            None,
            {"fields": ("number", "state", "email", "phone", "customer_note")},
        ),
        (
            "Entrega",
            {
                "fields": (
                    "fulfillment_method",
                    "shipping_address",
                    "shipping_rate_name",
                    "cancel_reason",
                )
            },
        ),
        (
            "Totales",
            {
                "fields": (
                    "subtotal",
                    "shipping",
                    "discount",
                    "order_total",
                    "tax_included",
                )
            },
        ),
        (
            "Fechas",
            {
                "fields": (
                    "created_at",
                    "placed_at",
                    "payment_deadline_at",
                    "paid_at",
                    "shipped_at",
                    "completed_at",
                    "cancelled_at",
                )
            },
        ),
        ("Notas internas", {"fields": ("internal_note",)}),
    )
    readonly_fields = (
        "number",
        "state",
        "email",
        "phone",
        "customer_note",
        "fulfillment_method",
        "shipping_address",
        "shipping_rate_name",
        "cancel_reason",
        "subtotal",
        "shipping",
        "discount",
        "order_total",
        "tax_included",
        "created_at",
        "placed_at",
        "payment_deadline_at",
        "paid_at",
        "shipped_at",
        "completed_at",
        "cancelled_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def save_model(
        self, request: HttpRequest, obj: Order, form: Any, change: bool
    ) -> None:
        # Only the note is writable: a stale `state` loaded with the page must never be saved
        # over a transition committed meanwhile (CR-09).
        obj.save(update_fields=["internal_note", "updated_at"])

    @admin.display(description="Subtotal")
    def subtotal(self, obj: Order) -> str:
        return format_money(obj.subtotal_cents)

    @admin.display(description="Envío")
    def shipping(self, obj: Order) -> str:
        return format_money(obj.shipping_cents)

    @admin.display(description="Descuento")
    def discount(self, obj: Order) -> str:
        return format_money(obj.discount_cents)

    @admin.display(description="Total", ordering="total_cents")
    def order_total(self, obj: Order) -> str:
        return format_money(obj.total_cents)

    total = order_total

    @admin.display(description="IVA incluido")
    def tax_included(self, obj: Order) -> str:
        return format_money(obj.tax_included_cents)

    def get_urls(self):
        return [
            path(
                "<path:object_id>/event/",
                self.admin_site.admin_view(self.fire_event),
                name=f"{self.opts.app_label}_{self.opts.model_name}_event",
            ),
            *super().get_urls(),
        ]

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        order = self.get_object(request, object_id)
        actions = []
        if order is not None and self.has_change_permission(request, order):
            actions = [
                {
                    "event": event,
                    "label": EVENT_LABELS.get(event, event),
                    "needs_reason": event == EVENT_NEEDS_REASON,
                }
                for event in legal_events(order)
            ]
        context = {
            **(extra_context or {}),
            "event_actions": actions,
            "event_url": reverse(
                f"admin:{self.opts.app_label}_{self.opts.model_name}_event",
                args=[object_id],
            ),
        }
        return super().change_view(request, object_id, form_url, context)

    def fire_event(self, request: HttpRequest, object_id: str) -> HttpResponse:
        order = self.get_object(request, object_id)
        if order is None:
            raise PermissionDenied
        if request.method != "POST" or not self.has_change_permission(request, order):
            raise PermissionDenied
        back = HttpResponseRedirect(
            reverse(
                f"admin:{self.opts.app_label}_{self.opts.model_name}_change",
                args=[order.pk],
            )
        )
        event = request.POST.get("event", "")
        kwargs: dict[str, Any] = {}
        if event == EVENT_NEEDS_REASON:
            kwargs["cancel_reason"] = request.POST.get("cancel_reason", "")
        try:
            moved = apply_event(
                order.pk, event, actor=f"staff:{request.user.pk}", **kwargs
            )
        except IllegalTransition:
            self.message_user(
                request,
                "Ese evento no es válido para el estado actual del pedido.",
                messages.ERROR,
            )
        except GuardFailed as error:
            self.message_user(
                request,
                f"No se pudo aplicar «{EVENT_LABELS.get(event, event)}»: {error.reason}.",
                messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f"«{EVENT_LABELS.get(event, event)}» aplicado: el pedido está en {moved.state}.",
                messages.SUCCESS,
            )
        return back
