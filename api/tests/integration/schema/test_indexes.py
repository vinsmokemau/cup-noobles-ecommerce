import pytest

from tests.factories.catalog import ProductFactory

pytestmark = pytest.mark.django_db


def test_p2_v06_attributes_gin_used(raw_sql):
    ProductFactory(attributes={"linea": "Nendoroid", "numero": 1234})
    ProductFactory(attributes={"linea": "Figma"})
    # Inside the test's transaction, so the setting does not outlive it.
    raw_sql("SET LOCAL enable_seqscan = off")
    plan = "\n".join(
        row[0]
        for row in raw_sql(
            "EXPLAIN SELECT id FROM product WHERE attributes @> %s::jsonb",
            ['{"linea":"Nendoroid"}'],
        )
    )
    assert "product_attributes_gin" in plan, plan
