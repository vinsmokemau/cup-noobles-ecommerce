"""Catalog factories (SPEC.md Phase 2, "Fixtures and factories introduced").

The `ProductTypeFactory` traits for the launch types arrive with their schemas in T2.8.
"""

import factory
from django.utils import timezone

from apps.catalog.models import (
    Brand,
    Category,
    Franchise,
    Product,
    ProductCategory,
    ProductImage,
    ProductType,
    Variant,
)


class ProductTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductType

    code = factory.Sequence(lambda n: f"tipo_{n}")
    name = factory.Sequence(lambda n: f"Tipo {n}")
    # Open schema: tests that need attribute rules use a launch type or pass their own schema (T2.5).
    attribute_schema = factory.LazyFunction(lambda: {"type": "object"})


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
        skip_postgeneration_save = (
            True  # `categories` writes through rows, not the product
        )

    product_type = factory.SubFactory(ProductTypeFactory)
    slug = factory.Sequence(lambda n: f"producto-{n}")
    name = factory.Sequence(lambda n: f"Producto {n}")

    class Params:
        # Visible in the public catalog: `ProductFactory(published=True)`.
        published = factory.Trait(
            status=Product.Status.ACTIVE,
            published_at=factory.LazyFunction(timezone.now),
        )

    @factory.post_generation
    def categories(self, create, extracted, **kwargs):
        if create and extracted:
            for category in extracted:
                ProductCategory.objects.create(product=self, category=category)


class VariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Variant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    price_cents = 10000


class ProductImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductImage

    product = factory.SubFactory(ProductFactory)
    storage_key = factory.Sequence(lambda n: f"products/imagen-{n}.jpg")
    alt = "Foto de prueba"
