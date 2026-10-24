import factory

from apps.shipping.models import MxState


class MxStateFactory(factory.django.DjangoModelFactory):
    """A state row for tests. The 32 real subdivisions are seeded by T2.7."""

    class Meta:
        model = MxState
        django_get_or_create = ("code",)

    code = "CMX"
    name = "Ciudad de México"
