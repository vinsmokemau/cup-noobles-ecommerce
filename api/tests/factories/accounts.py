import factory

from apps.accounts.models import Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"cliente{n}@example.com")
    full_name = factory.Sequence(lambda n: f"Cliente {n}")
    password = factory.PostGenerationMethodCall("set_password", "contraseña-de-prueba")
