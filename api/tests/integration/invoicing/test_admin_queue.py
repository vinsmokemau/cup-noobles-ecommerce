"""The admin CFDI queue and recording (SPEC.md T10.14, P10-V23, REQ-060)."""

import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.core import providers
from apps.invoicing.base import ManualIssueRequired
from apps.invoicing.models import InvoiceDocument, InvoiceRequest
from apps.notifications.models import EmailOutbox
from tests.factories.invoicing import InvoiceRequestFactory
from tests.factories.orders import order_in_state

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n% factura de prueba\n"
XML = b'<?xml version="1.0"?><cfdi:Comprobante/>'


def paid_request(**fields):
    order = order_in_state("paid", paid_at=fields.pop("paid_at", timezone.now()))
    return InvoiceRequestFactory(order=order, **fields)


def payload(**overrides):
    data = {
        "folio": "A-123",
        "cfdi_uuid": str(uuid4()),
        "pdf": SimpleUploadedFile("factura.pdf", PDF, "application/pdf"),
        "xml": SimpleUploadedFile("factura.xml", XML, "application/xml"),
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def record(client, request, **overrides):
    url = reverse("admin:invoicing_invoicerequest_record", args=[request.pk])
    return client.post(url, payload(**overrides))


def test_p10_v23_queue_and_record(admin_client):
    now = timezone.now()
    newer = paid_request(paid_at=now)
    older = paid_request(paid_at=now - timedelta(days=2))
    InvoiceRequest.objects.filter(pk=older.pk).update(
        created_at=now - timedelta(days=2)
    )
    unpaid = InvoiceRequestFactory(order=order_in_state("pending_payment"))

    listing = admin_client.get(reverse("admin:invoicing_invoicerequest_changelist"))

    queue = [r.pk for r in listing.context["cl"].result_list]
    assert queue == [older.pk, newer.pk]
    assert unpaid.pk not in queue
    assert older.order.number in listing.content.decode()

    with pytest.raises(ManualIssueRequired):
        providers.invoicer().issue(newer)

    missing = record(admin_client, newer, cfdi_uuid=None, pdf=None)
    assert missing.status_code == 200
    errors = missing.context["form"].errors
    assert "cfdi_uuid" in errors and "pdf" in errors
    newer.refresh_from_db()
    assert newer.status == "requested"
    assert not InvoiceDocument.objects.exists()
    assert not EmailOutbox.objects.exists()

    uuid = str(uuid4())
    done = record(admin_client, newer, cfdi_uuid=uuid)

    assert done.status_code == 302
    newer.refresh_from_db()
    assert newer.status == "issued"
    assert str(newer.cfdi_uuid) == uuid
    assert newer.folio == "A-123"
    assert newer.issued_at is not None and newer.issued_by_user_id is not None
    documents = {d.kind: d for d in newer.documents.all()}
    assert bytes(documents["pdf"].content) == PDF
    assert documents["pdf"].sha256 == hashlib.sha256(PDF).hexdigest()
    assert documents["xml"].size_bytes == len(XML)
    mail = EmailOutbox.objects.get()
    assert (mail.template, mail.to_email, mail.order_id) == (
        "cfdi_issued",
        newer.order.email,
        newer.order_id,
    )

    again = record(admin_client, newer)
    assert again.status_code == 302
    assert EmailOutbox.objects.count() == 1
    assert InvoiceDocument.objects.count() == 2


@pytest.mark.parametrize(
    ("field", "upload"),
    [
        ("pdf", SimpleUploadedFile("factura.pdf", b"x" * (5 * 1024 * 1024 + 1))),
        ("pdf", SimpleUploadedFile("factura.pdf", b"no es un pdf")),
        ("pdf", SimpleUploadedFile("factura.xml", PDF)),
        ("xml", SimpleUploadedFile("factura.xml", b"texto plano")),
        ("xml", SimpleUploadedFile("factura.pdf", XML)),
    ],
)
def test_bad_files_are_field_errors(admin_client, field, upload):
    request = paid_request()

    response = record(admin_client, request, **{field: upload})

    assert field in response.context["form"].errors
    request.refresh_from_db()
    assert request.status == "requested"
    assert not InvoiceDocument.objects.exists()
    assert not EmailOutbox.objects.exists()


def test_a_duplicate_uuid_is_a_field_error_and_saves_nothing(admin_client):
    taken = paid_request(status="issued", issued_at=timezone.now(), cfdi_uuid=uuid4())
    request = paid_request()

    response = record(admin_client, request, cfdi_uuid=str(taken.cfdi_uuid))

    assert "cfdi_uuid" in response.context["form"].errors
    request.refresh_from_db()
    assert request.status == "requested"
    assert not InvoiceDocument.objects.filter(invoice_request=request).exists()
    assert not EmailOutbox.objects.exists()


def test_review_queue_and_mark_reviewed(admin_client):
    flagged = paid_request(
        status="issued",
        cfdi_uuid=uuid4(),
        issued_at=timezone.now(),
        needs_review=True,
        review_note="Reembolso de $100.00 MXN.",
    )
    waiting = paid_request()
    url = reverse("admin:invoicing_invoicerequest_review", args=[flagged.pk])

    listing = admin_client.get(reverse("admin:invoicing_invoicerequest_changelist"))
    assert [r.pk for r in listing.context["cl"].result_list] == [waiting.pk, flagged.pk]

    blank = admin_client.post(url, {"note": "  "})
    assert blank.status_code == 200
    flagged.refresh_from_db()
    assert flagged.needs_review

    admin_client.post(url, {"note": "Lo revisó la contadora."})
    flagged.refresh_from_db()
    assert not flagged.needs_review
    assert flagged.review_note == "Reembolso de $100.00 MXN.\nLo revisó la contadora."


def test_cancel_cfdi_needs_a_note(admin_client):
    request = paid_request(status="issued", cfdi_uuid=uuid4(), issued_at=timezone.now())
    url = reverse("admin:invoicing_invoicerequest_cancel", args=[request.pk])

    assert admin_client.post(url, {"note": ""}).status_code == 200
    request.refresh_from_db()
    assert request.status == "issued"

    admin_client.post(url, {"note": "Cancelado en el SAT."})
    request.refresh_from_db()
    assert request.status == "cancelled"
    assert request.cancelled_at is not None
    assert "Cancelado en el SAT." in request.review_note


def test_documents_download_for_staff_only(admin_client, client):
    request = paid_request()
    record(admin_client, request)
    url = reverse("admin:invoicing_invoicerequest_document", args=[request.pk, "pdf"])

    response = admin_client.get(url)

    assert response.status_code == 200
    assert response.content == PDF
    assert response["Content-Type"] == "application/pdf"
    assert "attachment" in response["Content-Disposition"]
    assert client.get(url).status_code == 302
