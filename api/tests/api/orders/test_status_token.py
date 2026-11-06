"""P13-V26: the order-status token (T13.9, G21, ADR-0065)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from apps.orders import status_token
from tests.factories.orders import order_in_state

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    cache.clear()
    yield
    cache.clear()


def status_url(public_id, token):
    return f"/api/orders/{public_id}/status/?t={token}"


def test_p13_v26_status_token(api_client):
    order = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    token = status_token.issue(order)

    ok = api_client.get(status_url(order.public_id, token))
    assert ok.status_code == 200
    assert ok.json()["number"] == order.number
    assert ok.json()["state"] == "pending_payment"
    assert ok.json()["total_cents"] == order.total_cents

    missing = api_client.get(status_url(uuid.uuid4(), token))
    tampered = api_client.get(status_url(order.public_id, token[:-2] + "xx"))
    no_token = api_client.get(f"/api/orders/{order.public_id}/status/")
    other = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    wrong_order = api_client.get(status_url(other.public_id, token))
    expired_order = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    expired = api_client.get(
        status_url(expired_order.public_id, status_token.issue(expired_order))
    )

    for response in (missing, tampered, no_token, wrong_order, expired):
        assert response.status_code == 404
        assert response.json() == missing.json()


def test_p13_v26_not_limited_like_the_guest_lookup(api_client):
    order = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    url = status_url(order.public_id, status_token.issue(order))
    assert all(api_client.get(url).status_code == 200 for _ in range(20))


def test_p13_v26_back_urls_carry_the_token():
    from apps.payments.mock import MockPaymentProvider

    order = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    urls = MockPaymentProvider._back_urls(order)
    token = status_token.issue(order)
    assert urls["success"].endswith(f"/gracias?t={token}")
    assert urls["pending"].endswith(f"/pendiente?t={token}")
    assert urls["failure"].endswith(f"/error?t={token}")
