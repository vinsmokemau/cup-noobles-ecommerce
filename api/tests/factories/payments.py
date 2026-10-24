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
