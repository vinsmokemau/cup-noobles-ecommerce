"""The rest of the mock provider: fetch, find, webhook verification and refunds (SPEC.md 9.9)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps.payments import signing
from apps.payments.base import (
    NormalizedStatus,
    PaymentNotFound,
    RefundNotSupported,
    WebhookRef,
)
from apps.payments.mock import MockPaymentProvider
from tests.factories.orders import OrderFactory, OrderLineFactory
from tests.factories.payments import PaymentFactory

NOW = 1_700_000_000


@pytest.fixture
def provider():
    return MockPaymentProvider()


@pytest.fixture
def preference(provider, db):
    order = OrderFactory(subtotal_cents=116000, total_cents=116000)
    OrderLineFactory(order=order, quantity=1, unit_price_cents=116000)
    return order, provider.create_checkout(order).preference_id


def _signed(settings, body: dict, *, ts: int | None = None, secret: str | None = None):
    raw = json.dumps(body).encode()
    ts = int(datetime.now(UTC).timestamp()) if ts is None else ts
    headers = {
        "x-request-id": "req-1",
        "x-signature": signing.sign(
            secret or settings.MOCK_PAYMENT_WEBHOOK_SECRET,
            resource_id=body["data"]["id"],
            request_id="req-1",
            ts=ts,
        ),
    }
    return headers, raw


def test_the_preference_total_is_stored_in_pesos(provider, preference, settings):
    _, preference_id = preference
    stored = json.loads(
        (
            Path(settings.MOCK_STORE_DIR) / "payments" / f"{preference_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert stored["total"] == "1160.00"


def test_fetch_payment_reads_amounts_through_pesos(provider, preference):
    order, preference_id = preference
    payment_id = provider.record_payment(
        preference_id,
        status=NormalizedStatus.APPROVED,
        method="credit_card",
        installments=3,
    )

    fetched = provider.fetch_payment(payment_id)

    assert payment_id.startswith("mock_pay_")
    assert fetched.provider_payment_id == payment_id
    assert fetched.external_reference == str(order.public_id)
    assert fetched.status is NormalizedStatus.APPROVED
    assert (fetched.amount_cents, fetched.refunded_cents) == (116000, 0)
    assert (fetched.method, fetched.installments) == ("credit_card", 3)
    assert fetched.raw["amount"] == "1160.00"


def test_fetch_payment_keeps_the_voucher(provider, preference):
    _, preference_id = preference
    expires = datetime(2026, 11, 1, 18, 0, tzinfo=UTC)
    payment_id = provider.record_payment(
        preference_id,
        status=NormalizedStatus.PENDING,
        method="oxxo",
        voucher_url="http://localhost:8080/dev/payments/voucher/1/",
        voucher_expires_at=expires,
    )

    fetched = provider.fetch_payment(payment_id)

    assert fetched.voucher_url == "http://localhost:8080/dev/payments/voucher/1/"
    assert fetched.voucher_expires_at == expires


@pytest.mark.parametrize(
    "unknown", ["mock_pay_" + "0" * 32, "123456", "../../etc/passwd", "", "mock_pay_x"]
)
def test_fetch_payment_unknown_id_raises_payment_not_found(provider, unknown):
    with pytest.raises(PaymentNotFound):
        provider.fetch_payment(unknown)


def test_find_payments_returns_only_that_order_oldest_first(provider, preference, db):
    order, preference_id = preference
    other = OrderFactory()
    other_preference = provider.create_checkout(other).preference_id
    first = provider.record_payment(
        preference_id, status=NormalizedStatus.REJECTED, method="credit_card"
    )
    second = provider.record_payment(
        preference_id, status=NormalizedStatus.APPROVED, method="credit_card"
    )
    provider.record_payment(
        other_preference, status=NormalizedStatus.APPROVED, method="spei"
    )

    found = provider.find_payments(str(order.public_id))

    assert [payment.provider_payment_id for payment in found] == [first, second]
    assert provider.find_payments("no-such-order") == []


def test_find_payments_on_an_empty_store(provider):
    assert provider.find_payments("anything") == []


def test_verify_webhook_accepts_a_signed_notification(provider, settings):
    body = {"id": "mock_ntf_1", "type": "payment", "data": {"id": "mock_pay_1"}}
    headers, raw = _signed(settings, body)

    assert provider.verify_webhook(headers, raw) == WebhookRef(
        topic="payment", notification_id="mock_ntf_1", resource_id="mock_pay_1"
    )


def test_verify_webhook_rejects_a_wrong_secret(provider, settings):
    body = {"id": "mock_ntf_1", "type": "payment", "data": {"id": "mock_pay_1"}}
    headers, raw = _signed(settings, body, secret="another-secret")
    assert provider.verify_webhook(headers, raw) is None


def test_verify_webhook_rejects_a_stale_timestamp(provider, settings):
    body = {"id": "mock_ntf_1", "type": "payment", "data": {"id": "mock_pay_1"}}
    stale = int(datetime.now(UTC).timestamp()) - settings.WEBHOOK_MAX_AGE_SECONDS - 5
    headers, raw = _signed(settings, body, ts=stale)
    assert provider.verify_webhook(headers, raw) is None


def test_verify_webhook_rejects_a_resource_swapped_after_signing(provider, settings):
    body = {"id": "mock_ntf_1", "type": "payment", "data": {"id": "mock_pay_1"}}
    headers, _ = _signed(settings, body)
    swapped = {**body, "data": {"id": "mock_pay_2"}}
    assert provider.verify_webhook(headers, json.dumps(swapped).encode()) is None


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not json",
        b"[]",
        b'{"id": "n"}',
        b'{"id": "n", "type": "payment", "data": {}}',
        b'{"id": 1, "type": "payment", "data": {"id": "p"}}',
    ],
)
def test_verify_webhook_rejects_a_malformed_body(provider, settings, raw):
    headers = {"x-request-id": "req-1", "x-signature": f"ts={NOW},v1=00"}
    assert provider.verify_webhook(headers, raw) is None


def test_queue_notification_carries_ids_only(provider, preference, settings):
    _, preference_id = preference
    payment_id = provider.record_payment(
        preference_id, status=NormalizedStatus.APPROVED, method="credit_card"
    )

    notification_id = provider.queue_notification(payment_id)

    assert notification_id.startswith("mock_ntf_")
    stored = json.loads(
        (
            Path(settings.MOCK_STORE_DIR) / "payments" / f"{notification_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert {key: stored[key] for key in ("id", "type", "data")} == {
        "id": notification_id,
        "type": "payment",
        "data": {"id": payment_id},
    }
    assert "amount" not in json.dumps(stored)
    assert "status" not in json.dumps(stored)


def test_refund_of_a_stored_payment_updates_it_and_queues_a_notification(
    provider, preference, settings
):
    order, preference_id = preference
    payment_id = provider.record_payment(
        preference_id, status=NormalizedStatus.APPROVED, method="credit_card"
    )
    payment = PaymentFactory(
        order=order,
        provider="mock",
        provider_payment_id=payment_id,
        method="credit_card",
        status="approved",
        amount_cents=116000,
    )

    provider.refund(payment, 16000)
    partial = provider.fetch_payment(payment_id)
    assert (partial.status, partial.refunded_cents) == (
        NormalizedStatus.PARTIALLY_REFUNDED,
        16000,
    )

    payment.refunded_cents = 16000
    provider.refund(payment, None)
    full = provider.fetch_payment(payment_id)
    assert (full.status, full.refunded_cents) == (NormalizedStatus.REFUNDED, 116000)

    folder = Path(settings.MOCK_STORE_DIR) / "payments"
    assert len(list(folder.glob("mock_ntf_*.json"))) == 2


def test_refund_of_an_oxxo_payment_is_not_supported(provider, preference, settings):
    order, preference_id = preference
    payment_id = provider.record_payment(
        preference_id, status=NormalizedStatus.APPROVED, method="oxxo"
    )
    payment = PaymentFactory(
        order=order,
        provider="mock",
        provider_payment_id=payment_id,
        method="oxxo",
        status="approved",
        amount_cents=116000,
    )

    with pytest.raises(RefundNotSupported):
        provider.refund(payment, None)

    assert provider.fetch_payment(payment_id).refunded_cents == 0
    folder = Path(settings.MOCK_STORE_DIR) / "payments"
    assert list(folder.glob("mock_ref_*.json")) == []


def test_cancel_payment_ends_a_pending_payment_and_is_idempotent(provider, preference):
    _, preference_id = preference
    payment_id = provider.record_payment(
        preference_id, status=NormalizedStatus.PENDING, method="oxxo"
    )

    provider.cancel_payment(payment_id)
    provider.cancel_payment(payment_id)

    assert provider.fetch_payment(payment_id).status is NormalizedStatus.CANCELLED


def test_cancel_payment_of_an_unknown_id_is_not_found(provider, db):
    with pytest.raises(PaymentNotFound):
        provider.cancel_payment("mock_pay_" + "0" * 32)
