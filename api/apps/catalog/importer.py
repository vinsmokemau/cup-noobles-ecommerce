"""Catalog importer (SPEC.md §4.4, T3.6, CR-49).

`import_catalog` reads a CSV and creates or updates variants keyed on SKU, creating the products,
brands, franchises and categories the rows name. It goes through `create_product`, `add_variant`
and `Product.save()`, so a row is validated exactly like one typed in the admin.

- G12 (ADR-0033): all or nothing per file. Every row is checked in one transaction; if any
  row is invalid, or in a dry run, the transaction is rolled back and every invalid row is reported.
- G39 (proposed resolution): `image_urls` holds `|`-separated file paths relative to an images folder
  given at run time. A remote URL is a row error and the importer never makes a network call.
  Files are stored after the commit, so a rolled-back run leaves nothing in media storage.
- The file path is a run-time argument. A file that holds costs is never committed (CR-49); a
  `cost` column, like any column not listed in `COLUMNS`, is ignored.
- Imported products stay `draft`. Publishing is the owner's call.
"""

import csv
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from apps.catalog.images import add_product_image
from apps.catalog.models import Brand, Category, Franchise, Product, Variant
from apps.catalog.services import (
    DUPLICATE_OPTIONS_CODE,
    add_variant,
    check_option_keys,
    create_product,
    resolve_variant_axes,
)
from apps.catalog.slugs import slugify

COLUMNS = (
    "sku",
    "product_slug",
    "product_name",
    "product_type",
    "brand",
    "franchise",
    "categories",
    "price_mxn",
    "options_json",
    "attributes_json",
    "weight_grams",
    "image_urls",
)
LIST_SEPARATOR = "|"
REMOTE_URL = re.compile(r"^[a-z][a-z0-9+.-]*://|^//", re.IGNORECASE)
# Form-field names a service raises, mapped to the CSV column the owner has to fix.
FIELD_TO_COLUMN = {
    "options": "options_json",
    "attributes": "attributes_json",
    "price_cents": "price_mxn",
}

CREATE, UPDATE, UNCHANGED = "create", "update", "unchanged"


class MissingColumns(Exception):
    """The file cannot be read as a catalog: a required column is absent."""


@dataclass(frozen=True)
class RowError:
    row: int  # 1 is the header; the first data row is 2, as in a spreadsheet
    field: str
    message: str

    def __str__(self) -> str:
        return f"row {self.row}, {self.field}: {self.message}"


@dataclass
class ImportReport:
    dry_run: bool
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    products_created: int = 0
    images_added: int = 0
    created_lookups: dict[str, int] = field(default_factory=dict)
    ignored_columns: list[str] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def rows(self) -> int:
        return self.created + self.updated + self.unchanged


class _RowFailed(Exception):
    def __init__(self, errors: list[RowError]) -> None:
        self.errors = errors


@dataclass
class _ParsedRow:
    number: int
    sku: str
    product_slug: str
    product_name: str
    product_type: str
    brand: str
    franchise: str
    categories: list[str]
    price_cents: int
    options: dict[str, Any]
    attributes: dict[str, Any]
    weight_grams: int
    images: list[Path]

    def product_signature(self) -> tuple:
        """What rows of one product must agree on, so a re-run changes nothing."""
        return (
            self.product_name,
            self.product_type,
            self.brand,
            self.franchise,
            tuple(self.categories),
            json.dumps(self.attributes, sort_keys=True),
        )


class _Parser:
    def __init__(self, images_dir: Path | None) -> None:
        self.images_dir = images_dir

    def parse(self, number: int, raw: dict[str, str]) -> _ParsedRow:
        errors: list[RowError] = []

        def fail(column: str, message: str) -> None:
            errors.append(RowError(number, column, message))

        def text(column: str) -> str:
            return (raw.get(column) or "").strip()

        for column in ("sku", "product_name", "product_type"):
            if not text(column):
                fail(column, "is required")
        price_cents = self._price(text("price_mxn"), fail)
        weight = self._weight(text("weight_grams"), fail)
        options = self._json_object(text("options_json"), "options_json", fail)
        attributes = self._json_object(text("attributes_json"), "attributes_json", fail)
        images = self._images(text("image_urls"), fail)
        if errors:
            raise _RowFailed(errors)
        return _ParsedRow(
            number=number,
            sku=text("sku"),
            product_slug=text("product_slug"),
            product_name=text("product_name"),
            product_type=text("product_type"),
            brand=text("brand"),
            franchise=text("franchise"),
            categories=_split(text("categories")),
            price_cents=price_cents,
            options=options,
            attributes=attributes,
            weight_grams=weight,
            images=images,
        )

    @staticmethod
    def _price(value: str, fail) -> int:
        """Pesos to integer centavos. `Decimal` only parses the text; no float is involved (CR-01)."""
        if not value:
            fail("price_mxn", "is required")
            return 0
        try:
            pesos = Decimal(value)
        except InvalidOperation:
            fail("price_mxn", f"{value!r} is not a number")
            return 0
        centavos = pesos * 100
        if not pesos.is_finite() or centavos != centavos.to_integral_value():
            fail("price_mxn", "must have at most two decimals")
            return 0
        if centavos < 0:
            fail("price_mxn", "cannot be negative")
            return 0
        return int(centavos)

    @staticmethod
    def _weight(value: str, fail) -> int:
        if not value:
            return 0
        if not value.isdigit():
            fail("weight_grams", f"{value!r} is not a whole number of grams")
            return 0
        return int(value)

    @staticmethod
    def _json_object(value: str, column: str, fail) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            fail(column, f"is not valid JSON ({error.msg})")
            return {}
        if not isinstance(parsed, dict):
            fail(column, "must be a JSON object")
            return {}
        return parsed

    def _images(self, value: str, fail) -> list[Path]:
        paths: list[Path] = []
        for item in _split(value):
            if REMOTE_URL.match(item):
                fail("image_urls", f"{item!r} is a remote URL; use a file path (G39)")
            elif self.images_dir is None:
                fail("image_urls", "needs --images-dir to resolve file paths (G39)")
                break
            else:
                path = (self.images_dir / item).resolve()
                if not path.is_relative_to(self.images_dir.resolve()):
                    fail("image_urls", f"{item!r} is outside the images folder")
                elif not path.is_file():
                    fail("image_urls", f"{item!r} was not found in the images folder")
                elif not _is_image(path):
                    fail("image_urls", f"{item!r} is not a valid image")
                else:
                    paths.append(path)
        return paths


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(LIST_SEPARATOR) if part.strip()]


def _is_image(path: Path) -> bool:
    try:
        with Image.open(path) as picture:
            picture.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    return True


def _errors_from(error: ValidationError, number: int) -> list[RowError]:
    found: list[RowError] = []
    for name, messages in error.message_dict.items():
        column = FIELD_TO_COLUMN.get(name, name)
        found.extend(RowError(number, column, message) for message in messages)
    return found


class _Importer:
    def __init__(self, report: ImportReport) -> None:
        self.report = report
        self.signatures: dict[str, tuple[int, tuple]] = {}
        self.seen_skus: dict[str, int] = {}
        # Images are stored after the commit: product pk -> paths, in file order.
        self.pending_images: dict[int, list[Path]] = {}

    def run_row(self, row: _ParsedRow) -> None:
        errors: list[RowError] = []
        key = row.sku.lower()
        if key in self.seen_skus:
            errors.append(
                RowError(
                    row.number,
                    "sku",
                    f"repeats the SKU of row {self.seen_skus[key]}",
                )
            )
        self.seen_skus.setdefault(key, row.number)
        if errors:
            raise _RowFailed(errors)
        try:
            with transaction.atomic():
                self._apply(row)
        except ValidationError as error:
            raise _RowFailed(_errors_from(error, row.number)) from None

    def _apply(self, row: _ParsedRow) -> None:
        variant = (
            Variant.objects.select_related("product__product_type")
            .filter(sku=row.sku)
            .first()
        )
        product: Product | None
        if variant is not None:
            self._check_slug(row, variant.product.slug)
            product = variant.product
        else:
            product = (
                Product.objects.select_related("product_type")
                .filter(slug=row.product_slug)
                .first()
                if row.product_slug
                else None
            )
        self._check_agreement(row, product)

        changed = False
        brand = self._lookup(Brand, row.brand)
        franchise = self._lookup(Franchise, row.franchise)
        categories = [self._lookup(Category, name) for name in row.categories]

        if product is None:
            product = create_product(
                row.product_type,
                row.product_name,
                row.attributes,
                categories=categories,
                brand=brand,
                franchise=franchise,
                **({"slug": row.product_slug} if row.product_slug else {}),
            )
            self.report.products_created += 1
            changed = True
        else:
            changed |= self._update_product(row, product, brand, franchise, categories)

        if variant is None:
            add_variant(
                product,
                row.options,
                row.price_cents,
                row.sku,
                weight_grams=row.weight_grams,
            )
            changed = True
        else:
            changed |= self._update_variant(row, product, variant)

        if row.images and not product.images.exists():
            known = self.pending_images.setdefault(product.pk, [])
            known.extend(path for path in row.images if path not in known)

        if variant is None:
            self.report.created += 1
        elif changed:
            self.report.updated += 1
        else:
            self.report.unchanged += 1

    def _check_slug(self, row: _ParsedRow, stored_slug: str) -> None:
        if row.product_slug and row.product_slug.lower() != stored_slug.lower():
            raise ValidationError(
                {
                    "product_slug": f"SKU {row.sku} belongs to product "
                    f"{stored_slug!r}, not {row.product_slug!r}"
                }
            )

    def _check_agreement(self, row: _ParsedRow, product: Product | None) -> None:
        """Rows of one product must carry the same product-level columns."""
        if product is None and not row.product_slug:
            return
        identity = product.slug if product is not None else row.product_slug
        previous = self.signatures.setdefault(
            identity.lower(), (row.number, row.product_signature())
        )
        if previous[1] != row.product_signature():
            raise ValidationError(
                {
                    "product_name": f"product columns differ from row {previous[0]}, "
                    f"which names the same product {identity!r}"
                }
            )

    def _update_product(
        self,
        row: _ParsedRow,
        product: Product,
        brand: Brand | None,
        franchise: Franchise | None,
        categories: list[Category],
    ) -> bool:
        if product.product_type.code.lower() != row.product_type.lower():
            raise ValidationError(
                {"product_type": "cannot change the type of an existing product"}
            )
        changed = False
        fields: list[str] = []
        for name, value in (
            ("name", row.product_name),
            ("attributes", row.attributes),
            ("brand", brand),
            ("franchise", franchise),
        ):
            if getattr(product, name) != value:
                setattr(product, name, value)
                fields.append(name)
        if fields:
            product.save(update_fields=[*fields, "updated_at"])
            changed = True
        if set(product.categories.all()) != set(categories):
            product.categories.set(categories)
            changed = True
        return changed

    def _update_variant(
        self, row: _ParsedRow, product: Product, variant: Variant
    ) -> bool:
        fields: list[str] = []
        if variant.options != row.options:
            check_option_keys(resolve_variant_axes(product), row.options)
            if (
                product.variants.exclude(pk=variant.pk)
                .filter(options=row.options)
                .exists()
            ):
                raise ValidationError(
                    {
                        "options": ValidationError(
                            "This product already has a variant with these options.",
                            code=DUPLICATE_OPTIONS_CODE,
                        )
                    }
                )
            variant.options = row.options
            fields.append("options")
        for name, value in (
            ("price_cents", row.price_cents),
            ("weight_grams", row.weight_grams),
        ):
            if getattr(variant, name) != value:
                setattr(variant, name, value)
                fields.append(name)
        if fields:
            variant.save(update_fields=[*fields, "updated_at"])
        return bool(fields)

    def _lookup(self, model: type[Brand | Franchise | Category], name: str):
        if not name:
            return None
        slug = slugify(name)
        instance = model.objects.filter(slug=slug).first()
        if instance is None:
            instance = model.objects.create(slug=slug, name=name)
            label = model._meta.verbose_name_plural or model.__name__
            self.report.created_lookups[str(label)] = (
                self.report.created_lookups.get(str(label), 0) + 1
            )
        return instance


class _DryRun(Exception):
    """Raised inside the transaction to roll it back."""


def import_catalog(
    path: Path, *, dry_run: bool = False, images_dir: Path | None = None
) -> ImportReport:
    """Import `path`. Raises `MissingColumns` when the header lacks a required column.

    Nothing is written when `dry_run` is set or when any row is invalid (G12).
    """
    report = ImportReport(dry_run=dry_run)
    importer = _Importer(report)
    parser = _Parser(images_dir)

    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = [name.strip() for name in reader.fieldnames or []]
        missing = [column for column in COLUMNS if column not in header]
        if missing:
            raise MissingColumns(f"missing column(s): {', '.join(missing)}")
        report.ignored_columns = [name for name in header if name not in COLUMNS]
        rows = [
            (number, {(k or "").strip(): v for k, v in raw.items()})
            for number, raw in enumerate(reader, start=2)
            if any(isinstance(v, str) and v.strip() for v in raw.values())
        ]

    try:
        with transaction.atomic():
            for number, raw in rows:
                try:
                    importer.run_row(parser.parse(number, raw))
                except _RowFailed as failure:
                    report.errors.extend(failure.errors)
            if report.errors or dry_run:
                raise _DryRun
    except _DryRun:
        pass

    if report.ok and not dry_run:
        report.images_added = _store_images(importer.pending_images)
    elif not report.ok:
        # Nothing was written, so no count describes a real change.
        report.created = report.updated = report.unchanged = 0
        report.products_created = 0
        report.created_lookups = {}
    return report


def _store_images(pending: dict[int, list[Path]]) -> int:
    added = 0
    for product_id, paths in pending.items():
        product = Product.objects.get(pk=product_id)
        for position, path in enumerate(paths):
            with path.open("rb") as handle:
                add_product_image(
                    product,
                    File(handle, name=path.name),
                    alt=product.name,
                    position=position,
                )
            added += 1
    return added
