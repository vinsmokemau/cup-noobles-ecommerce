"""Catalog factories (SPEC.md Phase 2, "Fixtures and factories introduced").

The `ProductTypeFactory` traits for the launch types arrive with their schemas in T2.8.
"""

import factory

from apps.catalog.models import (
    Brand,
    Category,
    Franchise,
    Product,
    ProductType,
    Variant,
)


class ProductTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductType

    code = factory.Sequence(lambda n: f"tipo_{n}")
    name = factory.Sequence(lambda n: f"Tipo {n}")


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    slug = factory.Sequence(lambda n: f"categoria-{n}")
    name = factory.Sequence(lambda n: f"Categoría {n}")


class BrandFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Brand

    slug = factory.Sequence(lambda n: f"marca-{n}")
    name = factory.Sequence(lambda n: f"Marca {n}")


class FranchiseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Franchise

    slug = factory.Sequence(lambda n: f"franquicia-{n}")
    name = factory.Sequence(lambda n: f"Franquicia {n}")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    product_type = factory.SubFactory(ProductTypeFactory)
    slug = factory.Sequence(lambda n: f"producto-{n}")
    name = factory.Sequence(lambda n: f"Producto {n}")


class VariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Variant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    price_cents = 10000
