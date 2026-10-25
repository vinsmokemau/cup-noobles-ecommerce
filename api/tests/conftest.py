import os
import re
from collections.abc import Sequence
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
import time_machine
from django.core.files.base import ContentFile
from django.db import connection
from hypothesis import HealthCheck
from hypothesis import settings as hypothesis_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.core import providers

pytest_plugins = ["pytester"]

POSTGRES_GUARD_MESSAGE = (
    "Tests run on PostgreSQL only (CR-40): "
    "DATABASE_URL must point at the compose `db` service, not {vendor}."
)

hypothesis_settings.register_profile(
    "dev", max_examples=100, suppress_health_check=[HealthCheck.too_slow]
)
hypothesis_settings.register_profile(
    "ci", max_examples=1000, derandomize=True, deadline=None
)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.fixture(scope="session", autouse=True)
def _require_postgres():
    """Abort the whole run unless the database is PostgreSQL (CR-40)."""
    if connection.vendor != "postgresql":
        pytest.exit(
            POSTGRES_GUARD_MESSAGE.format(vendor=connection.vendor), returncode=3
        )


@pytest.fixture(autouse=True)
def _isolated_file_stores(settings, tmp_path):
    """Emails and mock-provider state go to a per-test directory (§4.6)."""
    settings.EMAIL_FILE_DIR = str(tmp_path / "emails")
    settings.MOCK_STORE_DIR = str(tmp_path / "mock_store")
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture
def jpeg_image():
    """`jpeg_image(width)`: a Pillow-generated in-memory JPEG, 2:3 portrait by default."""

    def make(width: int, height: int | None = None) -> ContentFile:
        buffer = BytesIO()
        Image.new("RGB", (width, height or width * 3 // 2), (200, 30, 90)).save(
            buffer, "JPEG"
        )
        return ContentFile(buffer.getvalue(), name="foto.jpg")

    return make


CATALOG_CSV_COLUMNS = (
    "sku,product_slug,product_name,product_type,brand,franchise,categories,"
    "price_mxn,options_json,attributes_json,weight_grams,image_urls"
).split(",")


@pytest.fixture
def catalog_csv(tmp_path):
    """`catalog_csv(rows)`: write an import file in `tmp_path` and return its path.

    Each row is a dict of the importer's columns; a missing column is left empty. Extra keys
    become extra columns, so a test can prove the importer ignores them.
    """
    import csv

    def make(rows: Sequence[dict[str, Any]], name: str = "catalogo.csv") -> Path:
        extra = [k for row in rows for k in row if k not in CATALOG_CSV_COLUMNS]
        columns = [*CATALOG_CSV_COLUMNS, *dict.fromkeys(extra)]
        path = tmp_path / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return path

    return make


@pytest.fixture
def raw_sql():
    """`raw_sql(statement, params)`: run SQL that bypasses the ORM, for constraint tests.

    Returns the rows of a statement that produces any, else an empty list.
    """

    def run(statement: str, params: Sequence[Any] | None = None) -> list[tuple]:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchall() if cursor.description else []

    return run


SCHEMA_SQL = Path(__file__).resolve().parents[2] / "spec" / "schema.sql"
if not SCHEMA_SQL.exists():  # the compose api service mounts the repository at /repo
    SCHEMA_SQL = Path("/repo/spec/schema.sql")


@pytest.fixture(scope="session")
def canonical_ddl() -> list[str]:
    """The statements of `spec/schema.sql`, comments removed, in file order (SPEC.md §4.4)."""
    text = re.sub(r"--[^\n]*", "", SCHEMA_SQL.read_text(encoding="utf-8"))
    return [statement.strip() for statement in text.split(";") if statement.strip()]


@pytest.fixture
def api_client() -> APIClient:
    """An anonymous DRF client that enforces CSRF, so CSRF is under test."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def auth_client():
    """`auth_client(customer)`: a CSRF-enforcing client logged in through the session."""

    def make(user) -> APIClient:
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        return client

    return make


class Clock:
    """Moves time for one test: `clock.travel("2026-01-01T12:00:00Z")`."""

    def __init__(self, stack: ExitStack) -> None:
        self._stack = stack

    def travel(self, destination, *, tick: bool = False) -> time_machine.travel:
        traveller = time_machine.travel(destination, tick=tick)
        self._stack.enter_context(traveller)
        return traveller


@pytest.fixture
def clock():
    with ExitStack() as stack:
        yield Clock(stack)


@pytest.fixture
def use_provider(settings):
    """Switch a provider setting for one test: `use_provider("PAYMENT_PROVIDER", "mock")`.

    Applies the setting override and clears the registry caches, so no chosen
    implementation leaks into another test (SPEC.md §4.3).
    """

    def apply(setting: str, value: str) -> None:
        setattr(settings, setting, value)
        providers.clear_provider_caches()

    yield apply
    providers.clear_provider_caches()


@pytest.fixture
def catalog_dataset():
    """Products across the launch types, with stock at each availability boundary (Phase 5).

    Visible: a Zelda Nendoroid (in stock), a Zelda Figma (low stock, two variants), a Pokémon
    box (out of stock). Hidden: a draft and an archived product. The pre-order product is R2
    (T5.8) and joins this dataset then.
    """
    from types import SimpleNamespace

    from apps.catalog.services import archive_product
    from tests.factories.catalog import (
        BrandFactory,
        CategoryFactory,
        FranchiseFactory,
        ProductFactory,
        ProductImageFactory,
        ProductTypeFactory,
    )
    from tests.factories.inventory import stocked_variant

    figure = ProductTypeFactory(
        code="figure",
        name="Figura",
        attribute_schema={
            "type": "object",
            "properties": {"linea": {"type": "string", "title": "Línea"}},
        },
        filterable_keys=["linea"],
    )
    tcg = ProductTypeFactory(code="tcg_sealed", name="TCG sellado")
    zelda = FranchiseFactory(slug="zelda", name="Zelda")
    pokemon = FranchiseFactory(slug="pokemon", name="Pokémon")
    gsc = BrandFactory(slug="good-smile", name="Good Smile Company")
    figuras = CategoryFactory(slug="figuras", name="Figuras", position=1)
    nendoroids = CategoryFactory(
        slug="nendoroid", name="Nendoroid", parent=figuras, position=1
    )
    cartas = CategoryFactory(slug="cartas", name="Cartas", position=2)

    nendoroid = ProductFactory(
        published=True,
        name="Nendoroid Link",
        slug="nendoroid-link",
        product_type=figure,
        franchise=zelda,
        brand=gsc,
        categories=[nendoroids],
        attributes={"linea": "Nendoroid"},
    )
    stocked_variant(10, product=nendoroid, price_cents=90000, sku="NEN-LINK")
    ProductImageFactory(product=nendoroid, alt="Link de frente")

    figma = ProductFactory(
        published=True,
        name="Figma Zelda",
        slug="figma-zelda",
        product_type=figure,
        franchise=zelda,
        brand=gsc,
        categories=[figuras],
        attributes={"linea": "Figma"},
    )
    stocked_variant(3, product=figma, price_cents=150000, sku="FIG-ZELDA-A", position=1)
    stocked_variant(
        0,
        product=figma,
        price_cents=130000,
        sku="FIG-ZELDA-B",
        position=2,
        options={"edicion": "basica"},
    )

    box = ProductFactory(
        published=True,
        name="Caja Prismatic Evolutions",
        slug="caja-prismatic",
        product_type=tcg,
        franchise=pokemon,
        categories=[cartas],
    )
    stocked_variant(0, product=box, price_cents=120000, sku="TCG-PRISMATIC")

    draft = ProductFactory(name="Borrador", slug="borrador", product_type=figure)
    stocked_variant(5, product=draft, sku="DRAFT-1")
    archived = ProductFactory(
        published=True, name="Archivado", slug="archivado", product_type=figure
    )
    stocked_variant(5, product=archived, sku="ARCH-1")
    archive_product(archived)

    return SimpleNamespace(
        nendoroid=nendoroid,
        figma=figma,
        box=box,
        draft=draft,
        archived=archived,
        zelda=zelda,
        pokemon=pokemon,
        gsc=gsc,
        figuras=figuras,
        nendoroids=nendoroids,
        cartas=cartas,
        visible=[nendoroid, figma, box],
    )


@pytest.fixture
def search_corpus():
    """Products with overlapping names and descriptions, for ranking and trigram tests."""
    from types import SimpleNamespace

    from tests.factories.catalog import ProductFactory

    by_name = ProductFactory(
        published=True,
        name="Nendoroid Zelda",
        slug="nendoroid-zelda",
        description_md="Figura articulada con accesorios.",
    )
    by_description = ProductFactory(
        published=True,
        name="Estatua de colección",
        slug="estatua-coleccion",
        description_md="Una pieza para quien ama su nendoroid zelda favorita.",
    )
    unrelated = ProductFactory(
        published=True,
        name="Caja de sobres Pokémon",
        slug="caja-sobres",
        description_md="Treinta y seis sobres.",
    )
    draft = ProductFactory(name="Nendoroid Zelda borrador", slug="zelda-borrador")
    return SimpleNamespace(
        by_name=by_name, by_description=by_description, unrelated=unrelated, draft=draft
    )
