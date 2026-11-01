"""The `cfdi_issued` email with the PDF and XML attached (SPEC.md T11.8, P11-V11, REQ-060)."""

from uuid import uuid4

import pytest
from django.utils import timezone

from apps.invoicing.models import InvoiceDocument
from apps.invoicing.services import record_cfdi
from apps.notifications.models import EmailOutbox
from apps.notifications.sending import send_pending
from tests.factories.invoicing import InvoiceRequestFactory
from tests.factories.orders import order_in_state

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n% factura de prueba\n"
XML = b'<?xml version="1.0"?><cfdi:Comprobante/>'


def issue(request):
    return record_cfdi(
        request.pk,
        folio="A-1001",
        cfdi_uuid=uuid4(),
        pdf=("factura.pdf", PDF),
        xml=("factura.xml", XML),
        staff_user_id=1,
    )


def paid_request():
    order = order_in_state("paid", paid_at=timezone.now())
    return InvoiceRequestFactory(order=order)


def test_p11_v11_cfdi_issued_with_attachments(mailbox):
    request = paid_request()
    issue(request)

    row = EmailOutbox.objects.get()
    assert row.dedupe_key == f"cfdi_issued:{request.pk}"
    assert row.context["invoice_request_id"] == request.pk
    # the files are not copied into the outbox
    assert b"%PDF" not in str(row.context).encode()

    assert send_pending() == (1, 0)

    (message,) = mailbox.messages()
    assert request.order.number in message.html
    assert request.order.number in message.text
    assert message.attachments == {"factura.pdf": PDF, "factura.xml": XML}
    assert "-cfdi_issued-" in message.prefix


def test_p11_v11_one_email_per_issued_request(mailbox):
    first, second = paid_request(), paid_request()
    issue(first)
    issue(second)

    assert EmailOutbox.objects.count() == 2
    assert send_pending() == (2, 0)
    assert len(mailbox.messages()) == 2


def test_p11_v11_missing_document_keeps_the_row_pending(mailbox):
    request = paid_request()
    issue(request)
    InvoiceDocument.objects.filter(invoice_request=request, kind="xml").delete()

    assert send_pending() == (0, 1)

    row = EmailOutbox.objects.get()
    assert (row.sent_at, row.attempts) == (None, 1)
    assert "xml" in row.last_error
    assert mailbox.messages() == []
