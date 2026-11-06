"""P13-V27: the pay-retry endpoint (T13.10, G22, ADR-0066)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from apps.inventory.models import InventoryReservation
from apps.orders import status_token
from apps.orders.models import Order
from apps.payments.models import Payment
from tests.factories.orders import order_in_state

pytestmark = pytest.mark.django_db

OTHER_STATES = ["paid", "expired", "cancelled", "shipped", "delivered"]


@pytest.fixture(autouse=True)
def _fresh_counters():
    cache.clear()
    yield
    cache.clear()


def pay_url(public_id, token):
    return f"/api/orders/{public_id}/pay/?t={token}"


def _pending():
    return order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )


def test_p13_v27_pay_retry(api_client):
    order = _pending()
    token = status_token.issue(order)
    reservations = InventoryReservation.objects.count()
    deadline = order.payment_deadline_at

    first = api_client.post(pay_url(order.public_id, token))
    second = api_client.post(pay_url(order.public_id, token))

    assert first.status_code == 200
    assert first.json()["checkout_url"].startswith("http")
    assert second.status_code == 200
    assert second.json()["checkout_url"] != first.json()["checkout_url"]
    assert Payment.objects.filter(order=order).count() == 2
    assert InventoryReservation.objects.count() == reservations
    order.refresh_from_db()
    assert order.state == "pending_payment"
    assert order.payment_deadline_at == deadline


@pytest.mark.parametrize("state", OTHER_STATES)
def test_p13_v27_any_other_state_is_409(api_client, state):
    order = order_in_state(
        state, payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    response = api_client.post(pay_url(order.public_id, status_token.issue(order)))
    assert response.status_code == 409
    assert Payment.objects.filter(order=order).count() == 0
    assert Order.objects.get(pk=order.pk).state == state


def test_p13_v27_bad_token_is_the_status_404(api_client):
    order = _pending()
    token = status_token.issue(order)
    expired = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    other = _pending()
    reference = api_client.get(f"/api/orders/{uuid.uuid4()}/status/?t={token}").json()
    for url in (
        pay_url(uuid.uuid4(), token),
        pay_url(order.public_id, token[:-2] + "xx"),
        f"/api/orders/{order.public_id}/pay/",
        pay_url(other.public_id, token),
        pay_url(expired.public_id, status_token.issue(expired)),
    ):
        response = api_client.post(url)
        assert response.status_code == 404
        assert response.json() == reference
    assert Payment.objects.count() == 0
