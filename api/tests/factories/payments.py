import factory

from apps.payments.models import Payment, WebhookEvent
from tests.factories.orders import OrderFactory


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    order = factory.SubFactory(OrderFactory)
    status = "initiated"
    amount_cents = 10000


class WebhookEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WebhookEvent

    provider = "mercadopago"
    topic = "payment"
    external_id = factory.Sequence(lambda n: f"notificacion-{n}")
    signature_ok = True
    payload = factory.LazyFunction(dict)


def mock_payment_for(
    order, *, status="approved", method="credit_card", amount_cents=None
):
    """Record a payment for `order` on the mock provider's side; returns its `mock_pay_…` id.

    Nothing is queued and no database row is written: that is what a notification is for.
    """
    from apps.payments.base import NormalizedStatus
    from apps.payments.mock import MockPaymentProvider

    provider = MockPaymentProvider()
    preference_id = provider.create_checkout(order).preference_id
    return provider.record_payment(
        preference_id,
        status=NormalizedStatus(status),
        method=method,
        amount_cents=amount_cents,
    )


def signed_notification(
    settings, resource_id, *, notification_id=None, topic="payment", ts=None
):
    """`(body, headers)` of a notification the mock would deliver: ids only, HMAC-signed.

    `ts` defaults to now, frozen clocks included.
    """
    import json
    import time
    import uuid

    from apps.payments import signing

    body = json.dumps(
        {
            "id": notification_id or f"mock_ntf_{uuid.uuid4().hex}",
            "type": topic,
            "data": {"id": resource_id},
        }
    ).encode()
    headers = {
        "x-request-id": "req-test",
        "x-signature": signing.sign(
            settings.MOCK_PAYMENT_WEBHOOK_SECRET,
            resource_id=resource_id,
            request_id="req-test",
            ts=int(time.time()) if ts is None else ts,
        ),
    }
    return body, headers


def post_notification(client, body, headers, provider="mock"):
    """POST a notification to the webhook endpoint the way a provider would."""
    return client.post(
        f"/api/webhooks/payments/{provider}/",
        data=body,
        content_type="application/json",
        headers=headers,
    )
