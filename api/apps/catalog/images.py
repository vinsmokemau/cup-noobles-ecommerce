"""Product image handling (T3.5, SPEC.md §4.3).

An upload is stored as four keys through `providers.media_store()`: the original and three WebP
derivatives. Only the derivatives are ever given out as URLs; the original is never served.
"""

import uuid
from dataclasses import dataclass
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.catalog.models import Product, ProductImage, Variant
from apps.core import providers

DERIVATIVE_WIDTHS = (400, 800, 1600)
WEBP_QUALITY = 82


@dataclass(frozen=True)
class StoredImage:
    storage_key: str  # the original's key; derivative keys follow from it
    width: int
    height: int


def derivative_key(storage_key: str, width: int) -> str:
    stem = storage_key.rsplit(".", 1)[0]
    return f"{stem}-{width}.webp"


def derivative_urls(image: ProductImage) -> dict[int, str]:
    """Width to URL for each derivative. There is deliberately no URL for the original."""
    store = providers.media_store()
    return {
        width: store.url(derivative_key(image.storage_key, width))
        for width in DERIVATIVE_WIDTHS
    }


def process_image(file: File, *, directory: str = "products") -> StoredImage:
    """Store `file` and its WebP derivatives. Raises `ValidationError` if it is not an image."""
    try:
        with Image.open(file) as source:
            source.load()
            picture = ImageOps.exif_transpose(source)
            image_format = (source.format or "").lower()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValidationError("El archivo no es una imagen válida.") from error

    extension = {"jpeg": "jpg"}.get(image_format, image_format) or "img"
    store = providers.media_store()

    file.seek(0)
    original_key = store.save(f"{directory}/{uuid.uuid4().hex}.{extension}", file)

    rgb = picture.convert("RGBA" if "A" in picture.getbands() else "RGB")
    for width in DERIVATIVE_WIDTHS:
        # Never upscale: a small source keeps its own width.
        target = min(width, rgb.width)
        height = max(1, round(rgb.height * target / rgb.width))
        buffer = BytesIO()
        rgb.resize((target, height), Image.Resampling.LANCZOS).save(
            buffer, "WEBP", quality=WEBP_QUALITY
        )
        store.save(derivative_key(original_key, width), ContentFile(buffer.getvalue()))

    return StoredImage(original_key, picture.width, picture.height)


def add_product_image(
    product: Product,
    file: File,
    *,
    alt: str = "",
    variant: Variant | None = None,
    position: int = 0,
) -> ProductImage:
    stored = process_image(file, directory=f"products/{product.pk}")
    return ProductImage.objects.create(
        product=product,
        variant=variant,
        storage_key=stored.storage_key,
        alt=alt,
        width=stored.width,
        height=stored.height,
        position=position,
    )


def delete_product_image_files(image: ProductImage) -> None:
    store = providers.media_store()
    store.delete(image.storage_key)
    for width in DERIVATIVE_WIDTHS:
        store.delete(derivative_key(image.storage_key, width))
