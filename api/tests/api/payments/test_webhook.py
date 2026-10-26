"""The webhook endpoint over HTTP (SPEC.md 9.A, T9.3)."""

import json

import pytest

from apps.payments.models import Payment, WebhookEvent
from tests.factories.orders import order_in_state
from tests.factories.payments import (
    mock_payment_for,
    post_notification,
    signed_notification,
)


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def test_p9_v11_provider_path_mismatch(api_client, settings, db):
    body, headers = signed_notification(settings, "mock_pay_" + "0" * 32)

    response = post_notification(api_client, body, headers, provider="mercadopago")

    assert response.status_code == 404
    assert WebhookEvent.objects.count() == 0


def test_p9_v12_missing_or_malformed_signature(api_client, settings, db):
    order = order_in_state("pending_payment")
    body, headers = signed_notification(settings, mock_payment_for(order))

    missing = post_notification(api_client, body, {})
    assert missing.status_code == 401
    unsigned = WebhookEvent.objects.get()
    assert unsigned.signature_ok is False
    assert unsigned.processed_at is None

    altered = json.loads(body)
    altered["data"]["id"] = "mock_pay_" + "1" * 32
    tampered = post_notification(api_client, json.dumps(altered).encode(), headers)
    assert tampered.status_code == 401

    garbage = post_notification(api_client, b"not json", headers)
    assert garbage.status_code == 401

    assert WebhookEvent.objects.filter(signature_ok=True).count() == 0
    assert WebhookEvent.objects.filter(signature_ok=False).count() == 3
    assert Payment.objects.count() == 0


def test_signed_notification_is_processed_inline_without_a_csrf_token(
    api_client, settings, db
):
    order = order_in_state("pending_payment")
    payment_id = mock_payment_for(order, status="pending", method="oxxo")
    body, headers = signed_notification(settings, payment_id)

    response = post_notification(api_client, body, headers)

    assert response.status_code == 200
    event = WebhookEvent.objects.get()
    assert event.signature_ok is True
    assert event.processed_at is not None
    assert event.attempts == 1
    assert event.payload["ref"]["resource_id"] == payment_id
    payment = Payment.objects.get()
    assert (payment.order, payment.provider, payment.provider_payment_id) == (
        order,
        "mock",
        payment_id,
    )
    assert (payment.status, payment.method, payment.amount_cents) == (
        "pending",
        "oxxo",
        order.total_cents,
    )


def test_duplicate_delivery_is_acknowledged_and_stored_once(api_client, settings, db):
    order = order_in_state("pending_payment")
    body, headers = signed_notification(settings, mock_payment_for(order))

    first = post_notification(api_client, body, headers)
    second = post_notification(api_client, body, headers)

    assert (first.status_code, second.status_code) == (200, 200)
    assert WebhookEvent.objects.count() == 1
    assert Payment.objects.count() == 1


def test_endpoint_is_rate_limited(api_client, db):
    statuses = {
        post_notification(api_client, b"{}", {}).status_code for _ in range(301)
    }

    assert statuses == {401, 429}
