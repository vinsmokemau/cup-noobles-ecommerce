from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image

from apps.catalog.admin import ProductImageForm
from apps.catalog.images import (
    DERIVATIVE_WIDTHS,
    add_product_image,
    delete_product_image_files,
    derivative_key,
    derivative_urls,
)
from apps.catalog.models import ProductImage
from apps.core import providers
from tests.factories.catalog import ProductFactory

pytestmark = pytest.mark.django_db


def stored_size(key: str) -> tuple[int, int]:
    with providers.media_store().open(key) as handle:  # type: ignore[attr-defined]
        with Image.open(handle) as picture:
            assert picture.format == "WEBP"
            return picture.size


def test_p3_v04_three_webp_derivatives(jpeg_image):
    product = ProductFactory()

    image = add_product_image(product, jpeg_image(3000), alt="Miku")

    store = providers.media_store()
    assert store.exists(image.storage_key)
    widths = []
    for width in DERIVATIVE_WIDTHS:
        key = derivative_key(image.storage_key, width)
        assert store.exists(key)
        widths.append(stored_size(key)[0])
    assert widths == [400, 800, 1600]
    assert (image.width, image.height) == (3000, 4500)
    # The API gives out derivatives only: no URL for the original.
    urls = derivative_urls(image)
    assert set(urls) == set(DERIVATIVE_WIDTHS)
    assert all(url.endswith(".webp") for url in urls.values())
    assert store.url(image.storage_key) not in urls.values()


def test_small_source_is_never_upscaled(jpeg_image):
    image = add_product_image(ProductFactory(), jpeg_image(300))

    assert [
        stored_size(derivative_key(image.storage_key, w))[0] for w in DERIVATIVE_WIDTHS
    ] == [300, 300, 300]


def test_a_file_that_is_not_an_image_is_rejected_and_nothing_is_stored():
    product = ProductFactory()

    with pytest.raises(ValidationError):
        add_product_image(product, ContentFile(b"not an image", name="x.jpg"))

    assert not ProductImage.objects.exists()


def test_delete_removes_all_four_keys(jpeg_image):
    image = add_product_image(ProductFactory(), jpeg_image(900))

    delete_product_image_files(image)

    store = providers.media_store()
    assert not store.exists(image.storage_key)
    assert not any(
        store.exists(derivative_key(image.storage_key, w)) for w in DERIVATIVE_WIDTHS
    )


def test_admin_form_stores_the_upload_and_fills_the_size(jpeg_image):
    product = ProductFactory()
    form = ProductImageForm(
        data={"alt": "Miku", "position": 0},
        files={"file": jpeg_image(1000)},
        instance=ProductImage(product=product),
    )

    assert form.is_valid(), form.errors
    image = form.save()

    assert image.storage_key.startswith("products/")
    assert (image.width, image.height) == (1000, 1500)
    assert providers.media_store().exists(derivative_key(image.storage_key, 400))


def test_admin_form_without_a_file_is_an_error_on_new_rows():
    form = ProductImageForm(
        data={"alt": "sin archivo", "position": 0},
        instance=ProductImage(product=ProductFactory()),
    )

    assert not form.is_valid()
    assert "file" in form.errors


def test_png_with_alpha_is_converted(tmp_path):
    buffer = BytesIO()
    Image.new("RGBA", (900, 600), (0, 0, 0, 0)).save(buffer, "PNG")

    image = add_product_image(
        ProductFactory(), ContentFile(buffer.getvalue(), name="a.png")
    )

    assert image.storage_key.endswith(".png")
    assert stored_size(derivative_key(image.storage_key, 800)) == (800, 533)
