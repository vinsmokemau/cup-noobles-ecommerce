"""P9-V19: the voucher on the order status (T9.6, SPEC.md 9.4)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from apps.inventory import services
from apps.notifications.models import EmailOutbox
from apps.payments.models import Payment
from tests.factories.inventory import stocked_variant
from tests.factories.orders import order_in_state
from tests.factories.payments import (
    mock_payment_for,
    post_notification,
    signed_notification,
)

pytestmark = pytest.mark.django_db

LOOKUP = "/api/orders/lookup/"
EXPIRY = datetime(2026, 3, 4, 12, 0, tzinfo=UTC)
ISO = "2026-03-04T12:00:00Z"
VOUCHER = "http://localhost:8080/dev/payments/voucher/1/"


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    cache.clear()
    yield
    cache.clear()


def lookup(client, order):
    return client.post(
        LOOKUP, {"number": order.number, "email": order.email}, format="json"
    )


def notify(api_client, settings, order, **payment):
    payment_id = mock_payment_for(order, **payment)
    body, headers = signed_notification(settings, payment_id)
    assert post_notification(api_client, body, headers).status_code == 200


def test_p9_v19_voucher_surfaced(api_client, settings):
    order = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    services.reserve(order, [(stocked_variant(5), 1)], ttl=timedelta(minutes=30))
    assert lookup(api_client, order).json()["voucher_url"] is None

    notify(
        api_client,
        settings,
        order,
        status="pending",
        method="oxxo",
        voucher_url=VOUCHER,
        voucher_expires_at=EXPIRY,
    )

    payment = Payment.objects.get(order=order)
    assert payment.voucher_url
    assert payment.voucher_expires_at == EXPIRY
    body = lookup(api_client, order).json()
    assert body["voucher_url"] == payment.voucher_url
    assert body["voucher_expires_at"].replace("+00:00", "Z") == ISO
    # The confirmation email carries the ficha and its expiry, once per payment.
    email = EmailOutbox.objects.get(template="oxxo_voucher")
    assert email.to_email == order.email
    assert email.context["voucher_url"] == payment.voucher_url
    assert email.context["voucher_expires_at"] == EXPIRY.isoformat()
