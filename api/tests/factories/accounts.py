import factory

from apps.accounts.models import Address, Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"cliente{n}@example.com")
    full_name = factory.Sequence(lambda n: f"Cliente {n}")
    password = factory.PostGenerationMethodCall("set_password", "contraseña-de-prueba")


class AddressFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Address

    customer = factory.SubFactory(CustomerFactory)
    recipient_name = factory.SelfAttribute("customer.full_name")
    phone = "5555550100"
    street = "Calle de Prueba"
    ext_number = "10"
    neighborhood = "Colonia de Prueba"
    municipality = "Cuauhtémoc"
    state = factory.SubFactory("tests.factories.shipping.MxStateFactory")
    postal_code = "06700"
