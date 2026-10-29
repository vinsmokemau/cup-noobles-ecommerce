"""The CFDI queue, "Facturas (CFDI)" (SPEC.md T10.14, A8, ADR-0019).

Staff only. The list shows paid orders waiting for a CFDI, oldest first, then any request flagged
for review. Recording goes through `providers.invoicer()`; with the manual invoicer the form
asks for the folio, the UUID and both files. The documents download from here and are never
served from public media storage (§4.4).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Case, IntegerField, Q, QuerySet, Value, When
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import localize

from apps.core import providers
from apps.invoicing import services
from apps.invoicing.base import ManualIssueRequired
from apps.invoicing.models import InvoiceDocument, InvoiceRequest
from apps.invoicing.services import MAX_DOCUMENT_BYTES, InvoiceError
from apps.orders.admin import format_money

CONTENT_TYPES = {"pdf": "application/pdf", "xml": "application/xml"}


def _sniff(kind: str, head: bytes) -> bool:
    head = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    return head.startswith(b"%PDF-") if kind == "pdf" else head.startswith(b"<")


class RecordCfdiForm(forms.Form):
    folio = forms.CharField(label="Folio", max_length=100)
    cfdi_uuid = forms.UUIDField(label="Folio fiscal (UUID)")
    pdf = forms.FileField(label="PDF")
    xml = forms.FileField(label="XML")

    def _clean_file(self, kind: str) -> Any:
        upload = self.cleaned_data[kind]
        if upload.size > MAX_DOCUMENT_BYTES:
            raise forms.ValidationError("El archivo pesa más de 5 MB.")
        if not upload.name.lower().endswith(f".{kind}") or not _sniff(
            kind, upload.read(16)
        ):
            raise forms.ValidationError(f"El archivo debe ser un {kind.upper()}.")
        upload.seek(0)
        return upload

    def clean_pdf(self) -> Any:
        return self._clean_file("pdf")

    def clean_xml(self) -> Any:
        return self._clean_file("xml")


@admin.register(InvoiceRequest)
class InvoiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "paid",
        "order_total",
        "rfc",
        "legal_name",
        "fiscal_postal_code",
        "tax_regime",
        "cfdi_use",
        "status",
        "needs_review",
    )
    list_display_links = ("order_number",)
    list_filter = ("status", "needs_review")
    search_fields = ("order__number", "rfc", "legal_name")
    list_select_related = ("order",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def get_queryset(self, request: HttpRequest) -> QuerySet[InvoiceRequest]:
        queryset = super().get_queryset(request)
        if not getattr(request, "_cfdi_queue", False):
            return queryset
        return (
            queryset.filter(
                Q(status="requested", order__paid_at__isnull=False)
                | Q(needs_review=True)
            )
            .annotate(
                waiting=Case(
                    When(status="requested", then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("waiting", "created_at", "pk")
        )

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        # The bare list is the work queue; a filter or a search widens it to every request.
        request._cfdi_queue = not request.GET  # type: ignore[attr-defined]
        return super().changelist_view(request, extra_context)

    @admin.display(description="Pedido", ordering="order__number")
    def order_number(self, obj: InvoiceRequest) -> str:
        return obj.order.number

    @admin.display(description="Pagado")
    def paid(self, obj: InvoiceRequest) -> str:
        paid_at = obj.order.paid_at
        return localize(timezone.localtime(paid_at)) if paid_at else "—"

    @admin.display(description="Total")
    def order_total(self, obj: InvoiceRequest) -> str:
        return format_money(obj.order.total_cents)

    def get_urls(self):
        name = f"{self.opts.app_label}_{self.opts.model_name}"
        return [
            path(
                "<path:object_id>/record/",
                self.admin_site.admin_view(self.record_view),
                name=f"{name}_record",
            ),
            path(
                "<path:object_id>/review/",
                self.admin_site.admin_view(self.review_view),
                name=f"{name}_review",
            ),
            path(
                "<path:object_id>/cancel/",
                self.admin_site.admin_view(self.cancel_view),
                name=f"{name}_cancel",
            ),
            path(
                "<path:object_id>/document/<str:kind>/",
                self.admin_site.admin_view(self.document_view),
                name=f"{name}_document",
            ),
            *super().get_urls(),
        ]

    def _url(self, name: str, obj: InvoiceRequest, *extra: str) -> str:
        return reverse(
            f"admin:{self.opts.app_label}_{self.opts.model_name}_{name}",
            args=[obj.pk, *extra],
        )

    def _get(self, request: HttpRequest, object_id: str) -> InvoiceRequest:
        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404
        return obj

    def _detail(
        self,
        request: HttpRequest,
        obj: InvoiceRequest,
        form: RecordCfdiForm | None = None,
        errors: dict[str, str] | None = None,
    ) -> HttpResponse:
        documents = [
            {
                "kind": d.kind.upper(),
                "filename": d.filename,
                "sha256": d.sha256,
                "size": d.size_bytes,
                "url": self._url("document", obj, d.kind),
            }
            for d in obj.documents.order_by("kind")
        ]
        return TemplateResponse(
            request,
            "admin/invoicing/invoicerequest/detail.html",
            {
                **self.admin_site.each_context(request),
                "title": f"CFDI · pedido {obj.order.number}",
                "request_obj": obj,
                "order_total": format_money(obj.order.total_cents),
                "documents": documents,
                "form": form or RecordCfdiForm(),
                "errors": errors or {},
                "can_edit": self.has_change_permission(request, obj),
                "record_url": self._url("record", obj),
                "review_url": self._url("review", obj),
                "cancel_url": self._url("cancel", obj),
                "list_url": reverse(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"
                ),
            },
        )

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        obj = self._get(request, object_id)
        if not self.has_view_permission(request, obj):
            raise PermissionDenied
        return self._detail(request, obj)

    def _back(self, obj: InvoiceRequest) -> HttpResponseRedirect:
        return HttpResponseRedirect(
            reverse(
                f"admin:{self.opts.app_label}_{self.opts.model_name}_change",
                args=[obj.pk],
            )
        )

    def _post_obj(self, request: HttpRequest, object_id: str) -> InvoiceRequest:
        obj = self._get(request, object_id)
        if request.method != "POST" or not self.has_change_permission(request, obj):
            raise PermissionDenied
        return obj

    def record_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        obj = self._post_obj(request, object_id)
        if obj.status != InvoiceRequest.Status.REQUESTED:
            self.message_user(
                request, "Esta solicitud ya no está pendiente de CFDI.", messages.ERROR
            )
            return self._back(obj)
        try:
            issued = providers.invoicer().issue(obj)
        except ManualIssueRequired:
            pass
        else:  # a PAC adapter returned the invoice itself (R2 or later)
            return self._record(
                request,
                obj,
                folio=issued.folio,
                cfdi_uuid=issued.cfdi_uuid,
                pdf=("cfdi.pdf", issued.pdf),
                xml=("cfdi.xml", issued.xml),
            )
        form = RecordCfdiForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._detail(request, obj, form)
        data = form.cleaned_data
        return self._record(
            request,
            obj,
            form=form,
            folio=data["folio"],
            cfdi_uuid=data["cfdi_uuid"],
            pdf=(data["pdf"].name, data["pdf"].read()),
            xml=(data["xml"].name, data["xml"].read()),
        )

    def _record(
        self,
        request: HttpRequest,
        obj: InvoiceRequest,
        *,
        form: RecordCfdiForm | None = None,
        folio: str,
        cfdi_uuid: UUID,
        pdf: tuple[str, bytes],
        xml: tuple[str, bytes],
    ) -> HttpResponse:
        try:
            services.record_cfdi(
                obj.pk,
                folio=folio,
                cfdi_uuid=cfdi_uuid,
                pdf=pdf,
                xml=xml,
                staff_user_id=request.user.pk,  # type: ignore[arg-type]
            )
        except InvoiceError as error:
            if form is not None and error.field:
                form.add_error(error.field, error.message)
                return self._detail(request, obj, form)
            self.message_user(request, error.message, messages.ERROR)
            return self._back(obj)
        self.message_user(
            request,
            f"CFDI registrado para el pedido {obj.order.number}.",
            messages.SUCCESS,
        )
        return self._back(obj)

    def _note_action(
        self, request: HttpRequest, object_id: str, action: Any, done: str
    ) -> HttpResponse:
        obj = self._post_obj(request, object_id)
        try:
            action(obj.pk, note=request.POST.get("note", ""))
        except InvoiceError as error:
            return self._detail(request, obj, errors={"note": error.message})
        self.message_user(request, done, messages.SUCCESS)
        return self._back(obj)

    def review_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        return self._note_action(
            request, object_id, services.mark_reviewed, "Marcado como revisado."
        )

    def cancel_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        return self._note_action(
            request, object_id, services.cancel_cfdi, "Cancelación de CFDI registrada."
        )

    def document_view(
        self, request: HttpRequest, object_id: str, kind: str
    ) -> HttpResponse:
        obj = self._get(request, object_id)
        if not self.has_view_permission(request, obj):
            raise PermissionDenied
        document = InvoiceDocument.objects.filter(
            invoice_request=obj, kind=kind
        ).first()
        if document is None:
            raise Http404
        response = HttpResponse(
            bytes(document.content), content_type=CONTENT_TYPES[document.kind]
        )
        response["Content-Disposition"] = (
            f'attachment; filename="cfdi-{obj.order.number}.{document.kind}"'
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
