"""Recording a CFDI that staff issued outside the store (SPEC.md T10.14, A8, A12).

The store never decides the fiscal treatment (D16): these functions only record what staff did.
Each one runs in a single transaction, so a failure leaves the request untouched.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.invoicing.models import InvoiceDocument, InvoiceRequest
from apps.notifications.outbox import enqueue_email

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024


class InvoiceError(Exception):
    """A rule the record broke. `field` names the form field, or `None` for the whole form."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


def _lock(request_id: int) -> InvoiceRequest:
    return (
        InvoiceRequest.objects.select_for_update()
        .select_related("order")
        .get(pk=request_id)
    )


def record_cfdi(
    request_id: int,
    *,
    folio: str,
    cfdi_uuid: UUID,
    pdf: tuple[str, bytes],
    xml: tuple[str, bytes],
    staff_user_id: int,
) -> InvoiceRequest:
    """Store both files, mark the request `issued` and queue one `cfdi_issued` email."""
    folio = folio.strip()
    if not folio:
        raise InvoiceError("El folio es obligatorio.", "folio")
    documents = {InvoiceDocument.Kind.PDF: pdf, InvoiceDocument.Kind.XML: xml}
    for kind, (_name, content) in documents.items():
        if not content:
            raise InvoiceError("El archivo está vacío.", kind.value)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise InvoiceError("El archivo pesa más de 5 MB.", kind.value)
    try:
        with transaction.atomic():
            request = _lock(request_id)
            if request.status != InvoiceRequest.Status.REQUESTED:
                raise InvoiceError("Esta solicitud ya no está pendiente de CFDI.")
            if request.order.paid_at is None:
                raise InvoiceError("El pedido no está pagado.")
            for kind, (name, content) in documents.items():
                InvoiceDocument.objects.create(
                    invoice_request=request,
                    kind=kind,
                    filename=name[:200],
                    content=content,
                    sha256=hashlib.sha256(content).hexdigest(),
                    size_bytes=len(content),
                )
            request.status = InvoiceRequest.Status.ISSUED
            request.folio = folio
            request.cfdi_uuid = cfdi_uuid
            request.issued_at = timezone.now()
            request.issued_by_user_id = staff_user_id
            request.save()
            enqueue_email(
                request.order.email,
                "cfdi_issued",
                {"order_number": request.order.number, "folio": folio},
                order=request.order,
                dedupe_key=f"cfdi_issued:{request.pk}",
            )
    except IntegrityError:
        raise InvoiceError(
            "Ese folio fiscal (UUID) ya está registrado en otra factura.", "cfdi_uuid"
        ) from None
    return request


def mark_reviewed(request_id: int, *, note: str) -> InvoiceRequest:
    """Clear `needs_review`. The note is added after the refund note T9.14 wrote."""
    note = note.strip()
    if not note:
        raise InvoiceError("Escribe una nota de revisión.", "note")
    with transaction.atomic():
        request = _lock(request_id)
        if not request.needs_review:
            raise InvoiceError("Esta solicitud no está pendiente de revisión.")
        request.needs_review = False
        request.review_note = "\n".join(filter(None, [request.review_note, note]))
        request.save(update_fields=["needs_review", "review_note", "updated_at"])
    return request


def cancel_cfdi(request_id: int, *, note: str) -> InvoiceRequest:
    """Record a cancellation made outside the store. It leaves the review queue too."""
    note = note.strip()
    if not note:
        raise InvoiceError("Escribe el motivo de la cancelación.", "note")
    with transaction.atomic():
        request = _lock(request_id)
        if request.status == InvoiceRequest.Status.CANCELLED:
            raise InvoiceError("Este CFDI ya está cancelado.")
        request.status = InvoiceRequest.Status.CANCELLED
        request.cancelled_at = timezone.now()
        request.needs_review = False
        request.review_note = "\n".join(filter(None, [request.review_note, note]))
        request.save()
    return request
