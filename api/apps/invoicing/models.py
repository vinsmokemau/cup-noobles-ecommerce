"""Manual CFDI tables (§4.4, `spec/schema.sql` INVOICING; A8, ADR-0019).

The customer's fiscal data is captured at checkout; staff issue the CFDI outside the store and
record it here. The RFC format is checked in the application, not in the schema.
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.db import NOW
from apps.core.fields import CITextField, FixedCharField


class InvoiceRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested"
        ISSUED = "issued"
        CANCELLED = "cancelled"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="invoice_request",
    )
    rfc = CITextField()
    legal_name = models.TextField()  # nombre o razón social
    fiscal_postal_code = FixedCharField(max_length=5)
    tax_regime = models.TextField()  # régimen fiscal, SAT catalog code
    cfdi_use = models.TextField()  # uso de CFDI, SAT catalog code
    status = models.TextField(
        choices=Status.choices, default=Status.REQUESTED, db_default=Status.REQUESTED
    )
    folio = models.TextField(default="", db_default="", blank=True)
    cfdi_uuid = models.UUIDField(null=True, blank=True, unique=True)  # folio fiscal
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by_user_id = models.BigIntegerField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    # Set when an order with an issued CFDI is refunded; the accountant decides
    # the fiscal treatment (A12, D16).
    needs_review = models.BooleanField(default=False, db_default=False)
    review_note = models.TextField(default="", db_default="", blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "invoice_request"
        constraints = [
            models.CheckConstraint(
                condition=Q(fiscal_postal_code__regex=r"^[0-9]{5}$"),
                name="invoice_request_fiscal_postal_code_check",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["requested", "issued", "cancelled"]),
                name="invoice_request_status_check",
            ),
            models.CheckConstraint(
                condition=~Q(status="issued")
                | Q(cfdi_uuid__isnull=False, issued_at__isnull=False),
                name="invoice_issued_complete",
            ),
            models.CheckConstraint(
                condition=~Q(status="cancelled") | Q(cancelled_at__isnull=False),
                name="invoice_cancelled_dated",
            ),
        ]
        indexes = [
            models.Index(
                fields=["created_at"],
                condition=Q(status="requested") | Q(needs_review=True),
                name="invoice_request_queue_idx",
            )
        ]


class InvoiceDocument(models.Model):
    """The PDF and XML the owner uploads. Kept in the database: they hold fiscal data.

    An issued request has one of each; the service enforces that (P10-V23).
    """

    class Kind(models.TextChoices):
        PDF = "pdf"
        XML = "xml"

    invoice_request = models.ForeignKey(
        InvoiceRequest,
        on_delete=models.CASCADE,
        related_name="documents",
        db_index=False,
    )
    kind = models.TextField(choices=Kind.choices)
    filename = models.TextField()
    content = models.BinaryField()
    sha256 = FixedCharField(max_length=64)
    size_bytes = models.IntegerField()
    uploaded_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "invoice_document"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["pdf", "xml"]), name="invoice_document_kind_check"
            ),
            models.CheckConstraint(
                condition=Q(size_bytes__gt=0, size_bytes__lte=5242880),
                name="invoice_document_size_bytes_check",
            ),
            models.UniqueConstraint(
                fields=["invoice_request", "kind"],
                name="invoice_document_invoice_request_id_kind_key",
            ),
        ]
