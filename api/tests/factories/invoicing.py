import factory

from apps.invoicing.models import InvoiceRequest
from tests.factories.orders import OrderFactory


class InvoiceRequestFactory(factory.django.DjangoModelFactory):
    """Fiscal data for tests only; the codes are not the accountant's subset (D16)."""

    class Meta:
        model = InvoiceRequest

    order = factory.SubFactory(OrderFactory)
    rfc = "XAXX010101000"
    legal_name = "Cliente de Prueba"
    fiscal_postal_code = "06700"
    tax_regime = "601"
    cfdi_use = "G03"
