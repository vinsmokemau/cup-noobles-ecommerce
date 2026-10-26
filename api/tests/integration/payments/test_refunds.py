"""Refunds from the admin (SPEC.md 9.8, T9.8, REQ-032, G46)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.invoicing.models import InvoiceRequest
from apps.payments.base import RefundNotSupported
from apps.payments.mock import MockPaymentProvider
from apps.payments.models import Payment
from apps.payments.refunds import RefundRejected, refund_payment
from tests.factories.invoicing import InvoiceRequestFactory
from tests.factories.orders import order_in_state
from tests.factories.payments import PaymentFactory, mock_payment_for

pytestmark = pytest.mark.django_db

EVENT = "admin:orders_order_event"
CHANGE = "admin:orders_order_change"
OXXO_MESSAGE = (
    "Los pagos en efectivo (OXXO) no se pueden reembolsar a través del proveedor. "
    "Reembolsa por SPEI y registra el reembolso manual."
)


def paid_order(state="paid", *, method="credit_card"):
    """An order in `state` with an approved payment the mock provider knows about."""
    order = order_in_state(state)
    provider_id = mock_payment_for(order, method=method)
    payment = PaymentFactory(
        order=order,
        provider="mock",
        provider_payment_id=provider_id,
        method=method,
        status="approved",
        amount_cents=order.total_cents,
    )
    return order, payment


@pytest.fixture
def issued_invoice_order():
    """A paid order whose `invoice_request` is `issued`, with its payment: `(order, payment)`."""
    order, payment = paid_order()
    InvoiceRequestFactory(
        order=order,
        status="issued",
        cfdi_uuid="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        issued_at=timezone.now(),
    )
    return order, payment


def cfdi_queue():
    """The requests the admin CFDI queue lists for review (T10.14): `needs_review`."""
    return InvoiceRequest.objects.filter(needs_review=True)


@pytest.fixture
def provider_calls(monkeypatch):
    """The amounts `MockPaymentProvider.refund` was called with."""
    calls = []
    original = MockPaymentProvider.refund

    def spy(self, payment, amount_cents):
        calls.append(amount_cents)
        return original(self, payment, amount_cents)

    monkeypatch.setattr(MockPaymentProvider, "refund", spy)
    return calls


def test_p9_v15_refund_boundaries(provider_calls):
    order, payment = paid_order()

    with pytest.raises(RefundRejected):
        refund_payment(payment.pk, actor="staff:1", amount_cents=10001)

    assert provider_calls == []
    payment.refresh_from_db()
    assert payment.refunded_cents == 0

    moved = refund_payment(payment.pk, actor="staff:1", amount_cents=10000)

    assert provider_calls == [10000]
    assert moved.state == "refunded"
    payment.refresh_from_db()
    assert (payment.refunded_cents, payment.status) == (10000, "refunded")
    event = order.events.get()
    assert (event.event, event.actor) == ("refund_issued", "staff:1")


def test_p9_v15_two_partials_summing_to_the_total_end_refunded(provider_calls):
    order, payment = paid_order()

    first = refund_payment(payment.pk, actor="staff:1", amount_cents=4000)

    # G46: the payment holds the running total after each refund.
    payment.refresh_from_db()
    assert (first.state, payment.refunded_cents) == ("paid", 4000)
    assert payment.status == "partially_refunded"

    with pytest.raises(RefundRejected):
        refund_payment(payment.pk, actor="staff:1", amount_cents=6001)

    second = refund_payment(payment.pk, actor="staff:1", amount_cents=6000)

    payment.refresh_from_db()
    assert (second.state, payment.refunded_cents) == ("refunded", 10000)
    assert provider_calls == [4000, 6000]
    assert [e.event for e in order.events.order_by("pk")] == [
        "partial_refund_issued",
        "refund_issued",
    ]


def test_p9_v15_two_partials_that_do_not_finish_keep_the_order_fulfillable():
    order, payment = paid_order("preparing")

    refund_payment(payment.pk, actor="staff:1", amount_cents=1000)
    moved = refund_payment(payment.pk, actor="staff:1", amount_cents=2000)

    payment.refresh_from_db()
    assert (moved.state, payment.refunded_cents) == ("preparing", 3000)


def test_p9_v15_no_amount_refunds_what_is_left(provider_calls):
    order, payment = paid_order()
    refund_payment(payment.pk, actor="staff:1", amount_cents=2500)

    moved = refund_payment(payment.pk, actor="staff:1")

    assert provider_calls == [2500, 7500]
    assert moved.state == "refunded"


@pytest.mark.parametrize("amount", [0, -1])
def test_p9_v15_a_non_positive_amount_is_rejected(provider_calls, amount):
    _, payment = paid_order()

    with pytest.raises(RefundRejected):
        refund_payment(payment.pk, actor="staff:1", amount_cents=amount)

    assert provider_calls == []


def test_p9_v15_a_payment_with_nothing_left_is_rejected(provider_calls):
    _, payment = paid_order()
    refund_payment(payment.pk, actor="staff:1")

    with pytest.raises(RefundRejected):
        refund_payment(payment.pk, actor="staff:1", amount_cents=1)

    assert provider_calls == [10000]


def test_p9_v15_a_refund_after_the_order_closed_is_a_payment_record():
    order, payment = paid_order("completed")

    moved = refund_payment(payment.pk, actor="staff:1", amount_cents=500)

    payment.refresh_from_db()
    assert (moved.state, payment.refunded_cents) == ("completed", 500)


def test_p9_v15_the_notification_the_mock_queues_is_a_no_op(settings, client):
    """The provider reports the refund we already recorded; processing it changes nothing."""
    from apps.payments.models import WebhookEvent
    from tests.factories.payments import post_notification, signed_notification

    order, payment = paid_order()
    refund_payment(payment.pk, actor="staff:1", amount_cents=4000)
    body, headers = signed_notification(settings, payment.provider_payment_id)

    assert post_notification(client, body, headers).status_code == 200

    assert WebhookEvent.objects.get().processed_at is not None
    payment.refresh_from_db()
    assert payment.refunded_cents == 4000
    assert [e.event for e in order.events.order_by("pk")] == [
        "partial_refund_issued",
        "webhook_no_op",
    ]


def test_p9_v16_oxxo_manual_refund_requires_note(provider_calls):
    order, payment = paid_order(method="oxxo")

    with pytest.raises(RefundNotSupported):
        refund_payment(payment.pk, actor="staff:7", amount_cents=3000)
    for note in ("", "   "):
        with pytest.raises(RefundRejected):
            refund_payment(
                payment.pk, actor="staff:7", amount_cents=3000, manual_note=note
            )
    payment.refresh_from_db()
    assert payment.refunded_cents == 0
    assert not order.events.exists()

    moved = refund_payment(
        payment.pk,
        actor="staff:7",
        amount_cents=3000,
        manual_note="  Transferencia SPEI 123  ",
    )

    # The provider was asked once (and refused); the manual refund never reached it.
    assert provider_calls == [3000]
    payment.refresh_from_db()
    assert (moved.state, payment.refunded_cents) == ("paid", 3000)
    event = order.events.get()
    assert (event.event, event.actor) == ("partial_refund_issued", "staff:7")
    assert event.payload["manual"] is True
    assert event.payload["note"] == "Transferencia SPEI 123"


def test_p9_v16_a_manual_refund_of_the_whole_payment_refunds_the_order(provider_calls):
    order, payment = paid_order(method="oxxo")

    moved = refund_payment(
        payment.pk, actor="staff:7", manual_note="Efectivo devuelto en mostrador"
    )

    assert provider_calls == []
    assert moved.state == "refunded"
    payment.refresh_from_db()
    assert payment.refunded_cents == payment.amount_cents


def test_p9_v16_a_manual_refund_is_also_bounded_by_the_balance():
    _, payment = paid_order(method="oxxo")

    with pytest.raises(RefundRejected):
        refund_payment(
            payment.pk, actor="staff:7", amount_cents=10001, manual_note="Excede"
        )


# --- the admin ---------------------------------------------------------------------------


def fire(client, order, event, **fields):
    return client.post(
        reverse(EVENT, args=[order.pk]), {"event": event, **fields}, follow=True
    )


def messages_of(response):
    return [str(message) for message in response.context["messages"]]


def test_p9_v15_admin_partial_then_full_refund(admin_client, admin_user):
    order, payment = paid_order()

    response = fire(admin_client, order, "partial_refund_issued", amount="40.00")

    assert "aplicado: el pedido está en paid" in messages_of(response)[0]
    payment.refresh_from_db()
    assert payment.refunded_cents == 4000
    assert order.events.get().actor == f"staff:{admin_user.pk}"

    response = fire(admin_client, order, "refund_issued")

    order.refresh_from_db()
    payment.refresh_from_db()
    assert (order.state, payment.refunded_cents) == ("refunded", 10000)


def test_p9_v15_admin_rejects_an_amount_above_the_balance(admin_client, provider_calls):
    order, payment = paid_order()

    response = fire(admin_client, order, "partial_refund_issued", amount="100.01")

    assert "No se pudo aplicar" in messages_of(response)[0]
    assert provider_calls == []
    payment.refresh_from_db()
    assert payment.refunded_cents == 0


@pytest.mark.parametrize("amount", ["", "abc", "10.005", "-5"])
def test_p9_v15_admin_rejects_a_missing_or_malformed_partial_amount(
    admin_client, provider_calls, amount
):
    order, payment = paid_order()

    response = fire(admin_client, order, "partial_refund_issued", amount=amount)

    assert "No se pudo aplicar" in messages_of(response)[0]
    assert provider_calls == []


def test_p9_v15_admin_without_a_payment_says_so(admin_client):
    order = order_in_state("paid")

    response = fire(admin_client, order, "refund_issued")

    assert "no tiene un pago por reembolsar" in messages_of(response)[0]


def test_p9_v16_admin_oxxo_shows_the_message_and_offers_the_manual_refund(
    admin_client, admin_user
):
    order, payment = paid_order(method="oxxo")

    response = fire(admin_client, order, "partial_refund_issued", amount="30.00")

    assert messages_of(response) == [OXXO_MESSAGE]
    html = response.content.decode()
    assert "Registrar reembolso manual" in html
    assert 'name="note"' in html
    payment.refresh_from_db()
    assert payment.refunded_cents == 0

    # Without a note nothing is recorded; with one, the event carries the staff actor.
    response = fire(
        admin_client,
        order,
        "partial_refund_issued",
        manual="1",
        payment=payment.pk,
        amount="30.00",
        note="",
    )
    assert "necesita una nota" in messages_of(response)[0]
    assert not order.events.exists()

    fire(
        admin_client,
        order,
        "partial_refund_issued",
        manual="1",
        payment=payment.pk,
        amount="30.00",
        note="SPEI 456",
    )
    payment.refresh_from_db()
    assert payment.refunded_cents == 3000
    event = order.events.get()
    assert (event.actor, event.payload["note"]) == (
        f"staff:{admin_user.pk}",
        "SPEI 456",
    )


def test_p9_v16_the_manual_form_is_not_offered_before_a_refusal(admin_client):
    order, _ = paid_order(method="oxxo")

    html = admin_client.get(reverse(CHANGE, args=[order.pk])).content.decode()

    assert "Registrar reembolso manual" not in html
    assert 'name="amount"' in html


def test_p9_v15_the_manual_form_ignores_a_payment_of_another_order(admin_client):
    order, _ = paid_order(method="oxxo")
    _, other = paid_order(method="oxxo")

    html = admin_client.get(
        reverse(CHANGE, args=[order.pk]), {"manual_refund": str(other.pk)}
    ).content.decode()

    assert "Registrar reembolso manual" not in html
    assert Payment.objects.count() == 2


def test_p9_v22_refund_flags_issued_cfdi(issued_invoice_order):
    order, payment = issued_invoice_order
    assert not cfdi_queue().exists()

    refund_payment(payment.pk, actor="staff:1", amount_cents=4000)

    invoice = order.invoice_request
    invoice.refresh_from_db()
    assert invoice.needs_review is True
    assert "$40.00" in invoice.review_note
    assert invoice.status == "issued"
    assert list(cfdi_queue()) == [invoice]

    # The rest of the payment is a full refund; the note names each amount.
    refund_payment(payment.pk, actor="staff:1", amount_cents=6000)

    invoice.refresh_from_db()
    assert "$40.00" in invoice.review_note and "$60.00" in invoice.review_note


def test_p9_v22_a_failed_refund_leaves_the_request_unflagged(issued_invoice_order):
    order, payment = issued_invoice_order

    with pytest.raises(RefundRejected):
        refund_payment(payment.pk, actor="staff:1", amount_cents=10001)

    order.invoice_request.refresh_from_db()
    assert order.invoice_request.needs_review is False


@pytest.mark.parametrize("status", ["requested", "cancelled"])
def test_p9_v22_a_request_that_is_not_issued_is_left_alone(status):
    order, payment = paid_order()
    InvoiceRequestFactory(
        order=order,
        status=status,
        cancelled_at=timezone.now() if status == "cancelled" else None,
    )

    refund_payment(payment.pk, actor="staff:1", amount_cents=4000)

    order.invoice_request.refresh_from_db()
    assert (order.invoice_request.needs_review, order.invoice_request.review_note) == (
        False,
        "",
    )


def test_p9_v22_a_refund_of_an_order_without_a_cfdi_changes_no_request():
    order, payment = paid_order()
    other = InvoiceRequestFactory(
        status="issued",
        cfdi_uuid="3fa85f64-5717-4562-b3fc-2c963f66afa7",
        issued_at=timezone.now(),
    )

    moved = refund_payment(payment.pk, actor="staff:1", amount_cents=4000)

    assert moved.state == "paid"
    other.refresh_from_db()
    assert other.needs_review is False
    assert not cfdi_queue().exists()
