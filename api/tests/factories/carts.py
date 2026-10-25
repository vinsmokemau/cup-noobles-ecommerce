import factory

from apps.carts.models import Cart, CartLine
from tests.factories.catalog import VariantFactory


class CartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cart


class CartLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CartLine

    cart = factory.SubFactory(CartFactory)
    variant = factory.SubFactory(VariantFactory)
    quantity = 1
