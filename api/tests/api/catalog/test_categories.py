"""The category tree (T5.1)."""

import pytest

from apps.catalog.models import Category
from tests.factories.catalog import CategoryFactory

pytestmark = pytest.mark.django_db

URL = "/api/catalog/categories/"


def test_tree_nests_children_in_position_order(api_client, catalog_dataset):
    body = api_client.get(URL).json()

    assert [c["slug"] for c in body] == ["figuras", "cartas"]
    assert [c["slug"] for c in body[0]["children"]] == ["nendoroid"]
    assert body[0]["children"][0]["children"] == []
    assert set(body[0]) == {"slug", "name", "description", "children"}


def test_inactive_categories_hide_their_subtree(api_client, catalog_dataset):
    CategoryFactory(parent=catalog_dataset.nendoroids, slug="nendoroid-swacchao")
    Category.objects.filter(pk=catalog_dataset.figuras.pk).update(is_active=False)

    assert [c["slug"] for c in api_client.get(URL).json()] == ["cartas"]


def test_empty_catalog_is_an_empty_list(api_client):
    assert api_client.get(URL).json() == []
