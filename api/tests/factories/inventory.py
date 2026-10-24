import factory

from apps.inventory.models import Location


class LocationFactory(factory.django.DjangoModelFactory):
    """The warehouse. It is never presented as a store (CR-47)."""

    class Meta:
        model = Location
        django_get_or_create = ("code",)

    code = "almacen"
    name = "Almacén de prueba"
    kind = Location.Kind.WAREHOUSE
