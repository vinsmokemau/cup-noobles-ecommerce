import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.catalog.images import derivative_key
from apps.catalog.importer import MissingColumns, import_catalog
from apps.catalog.models import Brand, Category, Product, ProductImage, Variant
from apps.catalog.seeds import seed_product_types
from apps.core import providers

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def launch_types():
    seed_product_types()


def figure_row(n: int, **overrides) -> dict:
    row = {
        "sku": f"FIG-{n:03d}",
        "product_slug": f"figura-{n}",
        "product_name": f"Figura {n}",
        "product_type": "figure",
        "brand": "Good Smile Company",
        "franchise": "Vocaloid",
        "categories": "Figuras|Nendoroid",
        "price_mxn": "1299.50",
        "attributes_json": json.dumps({"linea": "Nendoroid", "numero": n}),
        "weight_grams": "300",
    }
    return {**row, **overrides}


def run(csv_path, *args) -> tuple[str, str]:
    out, err = StringIO(), StringIO()
    call_command("import_catalog", str(csv_path), *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_p3_v03_dry_run_and_idempotent_import(catalog_csv):
    path = catalog_csv([figure_row(n) for n in range(50)])

    dry = import_catalog(path, dry_run=True)

    assert dry.ok and dry.dry_run
    assert (dry.created, dry.updated) == (50, 0)
    assert not Product.objects.exists()
    assert not Variant.objects.exists()
    assert not Brand.objects.exists()

    first = import_catalog(path)
    assert (first.created, first.updated) == (50, 0)
    assert Product.objects.count() == 50

    second = import_catalog(path)
    assert (second.created, second.updated, second.unchanged) == (0, 0, 50)
    assert Product.objects.count() == 50
    assert Variant.objects.count() == 50
    assert Brand.objects.count() == 1
    assert Category.objects.count() == 2


def test_p3_v03_command_prints_the_summary(catalog_csv):
    path = catalog_csv([figure_row(n) for n in range(3)])

    out, _ = run(path, "--dry-run")
    assert "Dry run, nothing written: 3 created, 0 updated" in out
    assert not Product.objects.exists()

    out, _ = run(path)
    assert "3 created, 0 updated, 0 unchanged" in out


def test_p3_v09_invalid_row_reported(catalog_csv):
    path = catalog_csv(
        [
            figure_row(1),
            figure_row(2, attributes_json="{not json"),
            figure_row(3, product_type="no_existe"),
            figure_row(4, attributes_json=json.dumps({"linea": "X", "extra": 1})),
        ]
    )

    report = import_catalog(path)

    assert not report.ok
    found = {(error.row, error.field) for error in report.errors}
    assert {
        (3, "attributes_json"),
        (4, "product_type"),
        (5, "attributes_json"),
    } <= found
    assert all(error.row >= 2 for error in report.errors)


def test_p3_v09_command_fails_and_names_row_and_field(catalog_csv):
    path = catalog_csv([figure_row(1, price_mxn="barato")])

    with pytest.raises(CommandError, match="nothing was imported"):
        run(path)


def test_p3_v09_g12_one_invalid_row_imports_nothing(catalog_csv):
    """G12 (ADR-0033): all or nothing per file, every invalid row reported."""
    path = catalog_csv(
        [
            figure_row(1),
            figure_row(2, attributes_json="{not json"),
            figure_row(3),
            figure_row(4, product_type="no_existe"),
        ]
    )

    report = import_catalog(path)

    assert sorted(error.row for error in report.errors) == [3, 5]
    assert not Product.objects.exists()
    assert not Variant.objects.exists()


def test_p3_v10_reimport_updates_price(catalog_csv, tmp_path):
    rows = [figure_row(n) for n in range(5)]
    import_catalog(catalog_csv(rows))

    rows[2] = figure_row(2, price_mxn="1499.00")
    report = import_catalog(catalog_csv(rows, name="nuevo.csv"))

    assert (report.created, report.updated, report.unchanged) == (0, 1, 4)
    assert Variant.objects.get(sku="FIG-002").price_cents == 149900
    assert Variant.objects.get(sku="FIG-001").price_cents == 129950


def test_price_is_parsed_to_integer_centavos(catalog_csv):
    import_catalog(
        catalog_csv([figure_row(1, price_mxn="99"), figure_row(2, price_mxn="0.10")])
    )

    assert Variant.objects.get(sku="FIG-001").price_cents == 9900
    assert Variant.objects.get(sku="FIG-002").price_cents == 10


@pytest.mark.parametrize("price", ["", "12.345", "-5", "NaN", "1e2x"])
def test_bad_prices_are_row_errors(catalog_csv, price):
    report = import_catalog(catalog_csv([figure_row(1, price_mxn=price)]))

    assert [(e.row, e.field) for e in report.errors] == [(2, "price_mxn")]


def test_rows_of_one_product_become_its_variants(catalog_csv):
    shared = {
        "product_slug": "sudadera",
        "product_name": "Sudadera",
        "product_type": "apparel",
        "attributes_json": json.dumps({"material": "algodón"}),
    }
    rows = [
        {
            **shared,
            "sku": f"SUD-{talla}",
            "price_mxn": "650",
            "options_json": json.dumps({"talla": talla, "color": "negro"}),
        }
        for talla in ("S", "M", "L")
    ]

    report = import_catalog(catalog_csv(rows))

    assert report.ok
    assert (report.products_created, report.created) == (1, 3)
    assert Product.objects.get(slug="sudadera").variants.count() == 3
    assert import_catalog(catalog_csv(rows)).unchanged == 3


def test_variant_options_must_match_the_axes(catalog_csv):
    row = figure_row(1, options_json=json.dumps({"talla": "S"}))

    report = import_catalog(catalog_csv([row]))

    assert [(e.row, e.field) for e in report.errors] == [(2, "options_json")]


def test_rows_of_one_product_must_agree(catalog_csv):
    rows = [
        figure_row(1, product_slug="misma", sku="A-1"),
        figure_row(1, product_slug="misma", sku="A-2", product_name="Otro nombre"),
    ]

    report = import_catalog(catalog_csv(rows))

    assert [(e.row, e.field) for e in report.errors] == [(3, "product_name")]


def test_repeated_sku_in_a_file_is_an_error(catalog_csv):
    report = import_catalog(catalog_csv([figure_row(1), figure_row(2, sku="fig-001")]))

    assert [(e.row, e.field) for e in report.errors] == [(3, "sku")]


def test_product_type_of_an_existing_product_cannot_change(catalog_csv):
    import_catalog(catalog_csv([figure_row(1)]))

    report = import_catalog(
        catalog_csv([figure_row(1, product_type="accessory", attributes_json="")])
    )

    assert [(e.row, e.field) for e in report.errors] == [(2, "product_type")]


def test_imported_products_stay_draft(catalog_csv):
    import_catalog(catalog_csv([figure_row(1)]))

    product = Product.objects.get()
    assert (product.status, product.published_at) == ("draft", None)
    assert product.slug == "figura-1"


def test_a_cost_column_is_ignored(catalog_csv):
    path = catalog_csv([figure_row(1, costo_mxn="500")])

    report = import_catalog(path)

    assert report.ok and report.ignored_columns == ["costo_mxn"]
    assert Variant.objects.get().cost_cents is None


def test_missing_column_is_a_file_error(tmp_path):
    path = tmp_path / "malo.csv"
    path.write_text("sku,product_name\nA,B\n", encoding="utf-8")

    with pytest.raises(MissingColumns, match="price_mxn"):
        import_catalog(path)
    with pytest.raises(CommandError, match="missing column"):
        run(path)


def test_images_come_from_the_images_folder_once(catalog_csv, jpeg_image, tmp_path):
    images = tmp_path / "imagenes"
    images.mkdir()
    (images / "miku.jpg").write_bytes(jpeg_image(1000).read())
    path = catalog_csv([figure_row(1, image_urls="miku.jpg")])

    report = import_catalog(path, images_dir=images)

    assert report.images_added == 1
    image = ProductImage.objects.get()
    assert providers.media_store().exists(derivative_key(image.storage_key, 400))
    # A second run adds no duplicate.
    assert import_catalog(path, images_dir=images).images_added == 0
    assert ProductImage.objects.count() == 1


def test_dry_run_stores_no_image(catalog_csv, jpeg_image, tmp_path):
    images = tmp_path / "imagenes"
    images.mkdir()
    (images / "miku.jpg").write_bytes(jpeg_image(1000).read())

    report = import_catalog(
        catalog_csv([figure_row(1, image_urls="miku.jpg")]),
        dry_run=True,
        images_dir=images,
    )

    assert report.ok and report.images_added == 0
    assert not ProductImage.objects.exists()


@pytest.mark.parametrize(
    ("value", "needs_dir"),
    [
        ("https://ejemplo.mx/miku.jpg", True),
        ("//cdn.ejemplo.mx/miku.jpg", True),
        ("../fuera.jpg", True),
        ("no-existe.jpg", True),
        ("miku.jpg", False),
    ],
)
def test_g39_images_are_files_never_urls(catalog_csv, tmp_path, value, needs_dir):
    images = tmp_path / "imagenes"
    images.mkdir()
    path = catalog_csv([figure_row(1, image_urls=value)])

    report = import_catalog(path, images_dir=images if needs_dir else None)

    assert [(e.row, e.field) for e in report.errors] == [(2, "image_urls")]
    assert not Product.objects.exists()
