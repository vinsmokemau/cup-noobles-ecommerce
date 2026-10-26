"""Payment branches the other suites do not reach: rejected stores, closed guards, odd ids,
dev-tool refusals (SPEC.md 9.3 to 9.12b; T9.17 coverage gaps)."""

import logging
import urllib.error
import urllib.request
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.core import providers
from apps.orders.state_machine import GuardFailed
from apps.payments import mapping, webhooks
from apps.payments.base import NormalizedStatus, ProviderPayment
from apps.payments.devtools import delivery, replay
from apps.payments.mock import MockPaymentProvider
from apps.payments.models import Payment, WebhookEvent
from tests.factories.orders import order_in_state
from tests.factories.payments import (
    WebhookEventFactory,
    mock_payment_for,
    signed_notification,
)


class OtherProvider:
    code = "mercadopago"


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def process(order, **payment):
    payment_id = mock_payment_for(order, **payment)
    provider_payment = MockPaymentProvider().fetch_payment(payment_id)
    return webhooks.process_provider_payment("mock", provider_payment)


# --- webhooks.py ---------------------------------------------------------------------------


def test_a_rejected_notification_is_still_a_401_when_it_cannot_be_stored(
    settings, db, monkeypatch, caplog
):
    def refuse(*args, **kwargs):
        raise RuntimeError("database refused the body")

    monkeypatch.setattr(webhooks, "_store_unverified", refuse)
    body, headers = signed_notification(settings, "mock_pay_" + "a" * 32)
    headers["x-signature"] = "ts=1,v1=" + "0" * 64

    status = webhooks.receive_notification("mock", headers, body)

    assert status == 401
    assert WebhookEvent.objects.count() == 0
    assert "Could not store a rejected payment notification" in caplog.text


def test_a_row_that_is_gone_or_already_processed_is_not_processed_again(db):
    done = WebhookEventFactory(processed_at=timezone.now())

    assert webhooks.process_webhook_event(done.pk) is False
    assert webhooks.process_webhook_event(done.pk + 1000) is False
    done.refresh_from_db()
    assert done.attempts == 0


def test_a_failure_on_a_row_that_is_gone_or_processed_records_nothing(db):
    done = WebhookEventFactory(processed_at=timezone.now())

    webhooks._record_failure(done.pk, RuntimeError("late"))
    webhooks._record_failure(done.pk + 1000, RuntimeError("late"))

    done.refresh_from_db()
    assert (done.attempts, done.error) == (0, "")


def test_an_external_reference_that_is_not_a_uuid_is_an_unknown_order(db, caplog):
    caplog.set_level(logging.ERROR)
    provider_payment = ProviderPayment(
        provider_payment_id="mock_pay_" + "b" * 32,
        external_reference="not-a-uuid",
        status=NormalizedStatus.APPROVED,
        status_detail="",
        method="credit_card",
        amount_cents=100,
        refunded_cents=0,
        installments=None,
        voucher_url=None,
        voucher_expires_at=None,
        raw={},
    )

    error = webhooks.process_provider_payment("mock", provider_payment)

    assert "No order has public_id 'not-a-uuid'" in error
    assert Payment.objects.count() == 0


# --- mapping.py ----------------------------------------------------------------------------


def test_a_rejection_after_the_deadline_changes_nothing(db, caplog):
    caplog.set_level(logging.WARNING)
    order = order_in_state("pending_payment")
    order.payment_deadline_at = timezone.now() - timedelta(minutes=1)
    order.save(update_fields=["payment_deadline_at"])

    assert process(order, status="rejected") == ""

    order.refresh_from_db()
    assert order.state == "pending_payment"
    assert "Rejected payment ignored" in caplog.text


def test_a_refused_approval_is_raised_so_the_row_is_retried(db, monkeypatch):
    order = order_in_state("pending_payment")

    def refuse(*args, **kwargs):
        raise GuardFailed("payment_approved", "the order has pre-order lines")

    monkeypatch.setattr(mapping, "apply_event", refuse)

    with pytest.raises(GuardFailed):
        process(order, status="approved")


def test_a_pending_voucher_on_an_order_already_paid_moves_nothing(db):
    order = order_in_state("paid")
    deadline = order.payment_deadline_at

    assert (
        process(
            order,
            status="pending",
            method="oxxo",
            voucher_url="https://example.test/voucher",
            voucher_expires_at=timezone.now() + timedelta(days=2),
        )
        == ""
    )

    order.refresh_from_db()
    assert (order.state, order.payment_deadline_at) == ("paid", deadline)


# --- devtools/delivery.py and replay.py ----------------------------------------------------


def test_http_transport_returns_the_status_of_an_http_error(monkeypatch):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 503, "down", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", refuse)

    send = delivery.http_transport("http://proxy:8080")

    assert send(b"{}", {}) == 503


def test_deliver_refuses_a_provider_without_a_mock_queue(monkeypatch):
    monkeypatch.setattr(providers, "payment_provider", lambda: OtherProvider())

    with pytest.raises(CommandError, match="PAYMENT_PROVIDER is not mock"):
        delivery.deliver(lambda body, headers: 200, honour_delay=False)


def test_replay_refuses_a_row_of_another_provider(db):
    event = WebhookEventFactory(
        provider="mercadopago", payload={"ref": {"resource_id": "1"}, "body": {}}
    )

    with pytest.raises(CommandError, match="but PAYMENT_PROVIDER is"):
        replay.verified_event(event.pk)


def test_replay_needs_a_webhook_secret(settings, db):
    event = WebhookEventFactory(
        provider="mock", payload={"ref": {"resource_id": "1"}, "body": {"id": "x"}}
    )
    settings.MOCK_PAYMENT_WEBHOOK_SECRET = ""

    with pytest.raises(CommandError, match="no webhook secret"):
        replay.build_request(event)


# --- the `webhooks` command ----------------------------------------------------------------


def run_webhooks(*args) -> str:
    out = StringIO()
    call_command("webhooks", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def stored_event(db):
    order = order_in_state("pending_payment")
    payment_id = mock_payment_for(order)
    return WebhookEventFactory(
        provider="mock",
        external_id="mock_ntf_branches",
        payload={
            "ref": {
                "topic": "payment",
                "notification_id": "mock_ntf_branches",
                "resource_id": payment_id,
            },
            "body": {
                "id": "mock_ntf_branches",
                "type": "payment",
                "data": {"id": payment_id},
            },
        },
    )


def test_duplicate_needs_a_positive_count(stored_event):
    with pytest.raises(CommandError, match="--count must be at least 1"):
        run_webhooks("duplicate", str(stored_event.pk), "--count", "0")


def test_duplicate_fails_when_a_delivery_is_not_answered_200(stored_event, monkeypatch):
    monkeypatch.setattr(
        delivery,
        "http_transport",
        lambda base_url, path=None: lambda body, headers: 500,
    )

    with pytest.raises(CommandError, match="should answer 200"):
        run_webhooks("duplicate", str(stored_event.pk), "--count", "2")


# --- the `mock_payments` command -----------------------------------------------------------


def run_mock(*args) -> str:
    out = StringIO()
    call_command("mock_payments", *args, stdout=out)
    return out.getvalue()


def test_mock_payments_needs_the_mock_provider(monkeypatch):
    monkeypatch.setattr(providers, "payment_provider", lambda: OtherProvider())

    with pytest.raises(CommandError, match="needs PAYMENT_PROVIDER=mock"):
        run_mock("list")


def test_pay_voucher_of_an_unknown_payment_fails(db):
    with pytest.raises(CommandError, match="There is no mock payment"):
        run_mock("pay-voucher", "mock_pay_" + "0" * 32)


def test_pay_voucher_of_a_card_payment_fails(db):
    order = order_in_state("pending_payment")
    payment_id = mock_payment_for(order, method="credit_card")

    with pytest.raises(CommandError, match="is not an OXXO or SPEI payment"):
        run_mock("pay-voucher", payment_id)


def test_chargeback_of_an_unknown_payment_fails(db):
    with pytest.raises(CommandError, match="There is no mock payment"):
        run_mock("chargeback", "mock_pay_" + "0" * 32)


def test_deliver_loop_reports_a_pass_only_when_something_moved(monkeypatch):
    results = iter([delivery.DeliveryResult(delivered=1), delivery.DeliveryResult()])
    monkeypatch.setattr(
        delivery, "deliver", lambda transport, honour_delay: next(results)
    )
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr("time.sleep", sleep)
    out = StringIO()

    with pytest.raises(KeyboardInterrupt):
        call_command("mock_payments", "deliver", "--loop", stdout=out)

    assert out.getvalue().count("1 delivered") == 1
    assert len(sleeps) == 2
