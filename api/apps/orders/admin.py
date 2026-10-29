"""Order admin (SPEC.md 8.A, T8.5, REQ-020).

An order is read-only here except for its internal note and, while it is being prepared for
delivery, a new shipment (T10.1). `state` is never in the form: staff move an order through the
action bar, which calls `apply_event` and shows a button only for an event that is legal from the
current state (CR-09, CR-10).
"""

from datetime import datetime
from io import StringIO
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.forms.formsets import (
    INITIAL_FORM_COUNT,
    MAX_NUM_FORM_COUNT,
    MIN_NUM_FORM_COUNT,
    TOTAL_FORM_COUNT,
    ManagementForm,
)
from django.forms.models import BaseInlineFormSet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import localize
from django.utils.functional import cached_property

from apps.core import providers
from apps.inventory.models import InventoryReservation, StockItem
from apps.orders import exports
from apps.orders.models import Order, OrderEvent, OrderLine, Shipment
from apps.orders.state_machine import (
    TRANSITIONS,
    GuardFailed,
    IllegalTransition,
    apply_event,
)
from apps.payments.base import RefundNotSupported
from apps.payments.money import cents_to_pesos, pesos_to_cents
from apps.payments.refunds import RefundRejected, refund_payment, refundable_payments
from apps.shipping.carriers.base import TrackingNumberRequired

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
# Refunds go through `refund_payment`, which calls the provider first (T9.8).
REFUND_EVENTS = ("refund_issued", "partial_refund_issued")

ALREADY_SHIPPED = "No se pudo crear el envío: el pedido ya tiene un envío."

OXXO_REFUND_MESSAGE = (
    "Los pagos en efectivo (OXXO) no se pueden reembolsar a través del proveedor. "
    "Reembolsa por SPEI y registra el reembolso manual."
)


def legal_events(order: Order) -> list[str]:
    """The events `TRANSITIONS` accepts from the order's current state, in table order."""
    return [event for state, event in TRANSITIONS if state == order.state]


def packing_lines(order: Order) -> list[dict[str, Any]]:
    """Each line with the bin location of the stock item it was reserved from. A line with no
    reservation row falls back to the variant's fulfillment-source stock rows. Reads only: nothing
    here moves stock (T10.17)."""
    lines = list(order.lines.order_by("pk"))
    locations: dict[int, int] = {}
    for variant_id, location_id in InventoryReservation.objects.filter(
        order=order, location__isnull=False
    ).values_list("variant_id", "location_id"):
        locations.setdefault(variant_id, location_id)
    rows = []
    for line in lines:
        items = StockItem.objects.filter(variant_id=line.variant_id or 0)
        if line.variant_id in locations:
            items = items.filter(location_id=locations[line.variant_id])
        else:
            items = items.filter(
                location__is_active=True, location__is_fulfillment_source=True
            )
        item = items.exclude(bin_location="").order_by("pk").first()
        rows.append(
            {
                "sku": line.sku,
                "product_name": line.product_name,
                "options": ", ".join(
                    f"{key}: {value}" for key, value in line.options_snapshot.items()
                ),
                "quantity": line.quantity,
                "bin_location": item.bin_location if item else "",
            }
        )
    return rows


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


def _local(moment: datetime) -> str:
    """A timestamp in the store's timezone (G5, CR-31)."""
    return localize(timezone.localtime(moment))


class ShipmentForm(forms.ModelForm):
    """A new shipment: the tracking number (optional when the carrier can generate one) and an
    optional cost in pesos. The row itself is written by `OrderAdmin.save_formset`, because the
    carrier supplies `carrier`, `tracking_number` and `tracking_url`."""

    create = forms.BooleanField(
        required=False,
        label="Crear envío",
        help_text="Marca esta casilla para crear el envío sin escribir una guía.",
    )
    tracking_number = forms.CharField(required=False, label="Guía", max_length=200)
    cost = forms.CharField(required=False, label="Costo (MXN)")

    class Meta:
        model = Shipment
        fields = ("tracking_number",)
        # The change form's column headers read these, not the field labels.
        labels = {
            "create": "Crear envío",
            "tracking_number": "Guía",
            "cost": "Costo (MXN)",
        }

    def clean_cost(self) -> int | None:
        raw = self.cleaned_data["cost"].strip()
        if not raw:
            return None
        try:
            return pesos_to_cents(raw)
        except (ArithmeticError, ValueError):
            raise forms.ValidationError("El costo no es válido.") from None


class ShipmentFormSet(BaseInlineFormSet):
    """A page rendered before the order reached `preparing` has no shipment form. Saving it
    afterwards (the note, say) must still work, so a post without the management data is a post
    with no shipment forms, not an error."""

    @cached_property
    def management_form(self) -> ManagementForm:
        if self.is_bound and f"{self.prefix}-{TOTAL_FORM_COUNT}" not in self.data:
            form = ManagementForm(
                {
                    f"{self.prefix}-{TOTAL_FORM_COUNT}": 0,
                    f"{self.prefix}-{INITIAL_FORM_COUNT}": 0,
                    f"{self.prefix}-{MIN_NUM_FORM_COUNT}": 0,
                    f"{self.prefix}-{MAX_NUM_FORM_COUNT}": 0,
                },
                auto_id=self.auto_id,
                prefix=self.prefix,
                renderer=self.renderer,  # type: ignore[attr-defined]
            )
            form.full_clean()
            return form
        return super().management_form


class ShipmentInline(admin.TabularInline):
    """Existing shipments are shown read-only; only a new one can be added, and only while the
    order is in `preparing` and goes out for delivery (T10)."""

    model = Shipment
    form = ShipmentForm
    formset = ShipmentFormSet
    extra = 1
    max_num = 1
    can_delete = False
    verbose_name = "envío"
    verbose_name_plural = "Envíos"
    fields = (
        "create",
        "tracking_number",
        "cost",
        "carrier_name",
        "tracking_link",
        "shipped",
        "delivered",
    )
    readonly_fields = ("carrier_name", "tracking_link", "shipped", "delivered")

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        # With no change permission a saved row is shown through the display methods below;
        # only the blank row is a form.
        return False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return self._can_ship(obj) and super().has_add_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    @staticmethod
    def _can_ship(order: Order | None) -> bool:
        return (
            order is not None
            and order.state == "preparing"
            and order.fulfillment_method == Order.FulfillmentMethod.DELIVERY
            and not order.shipments.exists()
        )

    def get_extra(self, request: HttpRequest, obj: Any = None, **kwargs: Any) -> int:
        return 1 if self._can_ship(obj) else 0

    def get_max_num(self, request: HttpRequest, obj: Any = None, **kwargs: Any) -> int:
        # An order has at most one shipment (OA-60): a saved one leaves no blank row.
        saved = obj.shipments.count() if obj is not None else 0
        return saved + (1 if self._can_ship(obj) else 0)

    @admin.display(description="Crear envío")
    def create(self, obj: Shipment) -> str:
        return ""

    @admin.display(description="Costo (MXN)")
    def cost(self, obj: Shipment) -> str:
        return "" if obj.cost_cents is None else str(cents_to_pesos(obj.cost_cents))

    @admin.display(description="Transportista")
    def carrier_name(self, obj: Shipment) -> str:
        return obj.carrier if obj.pk else ""

    @admin.display(description="Seguimiento")
    def tracking_link(self, obj: Shipment) -> str:
        return obj.tracking_url if obj.pk else ""

    @admin.display(description="Enviado")
    def shipped(self, obj: Shipment) -> str:
        return _local(obj.shipped_at) if obj.pk else ""

    @admin.display(description="Entregado")
    def delivered(self, obj: Shipment) -> str:
        return _local(obj.delivered_at) if obj.pk and obj.delivered_at else ""


class ReportExportForm(forms.Form):
    """The range and the file for the reporting exports (T10.16)."""

    report = forms.ChoiceField(label="Reporte", choices=list(exports.report_choices()))
    start = forms.DateField(
        label="Desde", widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        start, end = data.get("start"), data.get("end")
        if start and end and end < start:
            self.add_error("end", "La fecha final no puede ser anterior a la inicial.")
        return data


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
    inlines = (OrderLineInline, ShipmentInline, OrderEventInline)
    change_form_template = "admin/orders/order/change_form.html"
    change_list_template = "admin/orders/order/change_list.html"

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

    def save_formset(
        self, request: HttpRequest, form: Any, formset: Any, change: bool
    ) -> None:
        if formset.model is not Shipment:
            super().save_formset(request, form, formset, change)
            return
        order = form.instance
        actor = f"staff:{request.user.pk}"
        # The admin's change message reads these; the formset's own `save` is not used.
        formset.new_objects = []
        formset.changed_objects = []
        formset.deleted_objects = []
        for shipment_form in formset.forms:
            if shipment_form.instance.pk or not shipment_form.has_changed():
                continue
            data = shipment_form.cleaned_data
            try:
                with transaction.atomic():
                    ref = providers.carrier().create_shipment(
                        order, tracking_number=data["tracking_number"].strip() or None
                    )
                    shipment = Shipment.objects.create(
                        order=order,
                        carrier=ref.carrier,
                        tracking_number=ref.tracking_number,
                        tracking_url=ref.tracking_url,
                        cost_cents=data["cost"],
                    )
                    moved = apply_event(order.pk, "shipment_created", actor=actor)
                formset.new_objects.append(shipment)
            except (
                IntegrityError
            ):  # a second save raced past the form's own check (OA-60)
                self.message_user(request, ALREADY_SHIPPED, messages.ERROR)
            except TrackingNumberRequired:
                self.message_user(
                    request,
                    "El transportista activo no genera guías: escribe el número de guía.",
                    messages.ERROR,
                )
            except (IllegalTransition, GuardFailed) as error:
                reason = getattr(error, "reason", None) or str(error)
                self.message_user(
                    request,
                    f"No se pudo crear el envío: {reason}.",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"Envío creado: el pedido está en {moved.state}.",
                    messages.SUCCESS,
                )

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
                "reports/",
                self.admin_site.admin_view(self.reports_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_reports",
            ),
            path(
                "<path:object_id>/event/",
                self.admin_site.admin_view(self.fire_event),
                name=f"{self.opts.app_label}_{self.opts.model_name}_event",
            ),
            path(
                "<path:object_id>/packing/",
                self.admin_site.admin_view(self.packing_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_packing",
            ),
            *super().get_urls(),
        ]

    def reports_view(self, request: HttpRequest) -> HttpResponse:
        """CSV exports of orders, order lines and shipments for a date range (T10.16, A19)."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        form = ReportExportForm(request.GET or None)
        if form.is_bound and form.is_valid():
            report = form.cleaned_data["report"]
            start, end = form.cleaned_data["start"], form.cleaned_data["end"]
            buffer = StringIO()
            exports.REPORTS[report][1](buffer, start, end)
            response = HttpResponse(
                buffer.getvalue(), content_type="text/csv; charset=utf-8"
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{report}-{start}-{end}.csv"'
            )
            response["Cache-Control"] = "private, no-store"
            return response
        return TemplateResponse(
            request,
            "admin/orders/order/reports.html",
            {
                **self.admin_site.each_context(request),
                "title": "Exportar reportes",
                "form": form,
                "list_url": reverse(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"
                ),
            },
        )

    def packing_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        """The printable pick list for an order being prepared (T10.17)."""
        order = self.get_object(request, object_id)
        if order is None or not self.has_view_permission(request, order):
            raise PermissionDenied
        if order.state != "preparing":
            self.message_user(
                request,
                "La hoja de empaque solo está disponible para pedidos en preparación.",
                messages.WARNING,
            )
            return HttpResponseRedirect(
                reverse(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_change",
                    args=[order.pk],
                )
            )
        return TemplateResponse(
            request,
            "admin/orders/order/packing.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Hoja de empaque · pedido {order.number}",
                "order": order,
                "lines": packing_lines(order),
            },
        )

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
        refund_actions = [a for a in actions if a["event"] in REFUND_EVENTS]
        payments = (
            refundable_payments(order) if order is not None and refund_actions else []
        )
        manual = request.GET.get("manual_refund", "")
        context = {
            **(extra_context or {}),
            "event_actions": actions,
            "has_refund_actions": bool(refund_actions),
            "refund_payments": [
                {
                    "pk": p.pk,
                    "label": f"#{p.pk} · {format_money(p.amount_cents - p.refunded_cents)} por reembolsar",
                }
                for p in payments
            ],
            "manual_refund": next(
                (p.pk for p in payments if str(p.pk) == manual), None
            ),
            "manual_amount": request.GET.get("amount", ""),
            "packing_url": (
                reverse(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_packing",
                    args=[object_id],
                )
                if order is not None and order.state == "preparing"
                else ""
            ),
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
        if event in REFUND_EVENTS:
            return self._refund(request, order, event, back)
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

    def _refund(
        self,
        request: HttpRequest,
        order: Order,
        event: str,
        back: HttpResponseRedirect,
    ) -> HttpResponse:
        """A refund from the action bar: the provider is called, then the event applied. The
        manual form sends `manual` and a note and skips the provider (REQ-032)."""
        label = EVENT_LABELS[event]
        manual = bool(request.POST.get("manual"))
        raw_amount = request.POST.get("amount", "").strip()
        try:
            payments = {str(p.pk): p for p in refundable_payments(order)}
            payment = payments.get(request.POST.get("payment", "")) or (
                next(iter(payments.values())) if len(payments) == 1 else None
            )
            if payment is None:
                raise RefundRejected("El pedido no tiene un pago por reembolsar.")
            if raw_amount and (manual or event == "partial_refund_issued"):
                try:
                    amount = pesos_to_cents(raw_amount)
                except (ArithmeticError, ValueError):
                    raise RefundRejected("El monto no es válido.") from None
            elif manual or event == "partial_refund_issued":
                raise RefundRejected("Indica el monto del reembolso.")
            else:
                amount = None
            moved = refund_payment(
                payment.pk,
                actor=f"staff:{request.user.pk}",
                amount_cents=amount,
                manual_note=request.POST.get("note", "") if manual else None,
            )
        except RefundNotSupported:
            self.message_user(request, OXXO_REFUND_MESSAGE, messages.WARNING)
            query = f"?manual_refund={payment.pk}"  # type: ignore[union-attr]
            if raw_amount:
                query += f"&amount={raw_amount}"
            return HttpResponseRedirect(back.url + query)
        except (RefundRejected, GuardFailed, IllegalTransition) as error:
            reason = getattr(error, "reason", None) or str(error)
            self.message_user(
                request, f"No se pudo aplicar «{label}»: {reason}", messages.ERROR
            )
        else:
            self.message_user(
                request,
                f"«{label}» aplicado: el pedido está en {moved.state}.",
                messages.SUCCESS,
            )
        return back
