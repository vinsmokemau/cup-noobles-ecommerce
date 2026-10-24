import pytest
from django.core.management import call_command

from apps.catalog.models import ProductType
from apps.shipping.models import MxState

pytestmark = pytest.mark.django_db

LAUNCH_TYPES = {"tcg_sealed", "board_game", "apparel", "figure", "accessory"}


def snapshot():
    return (
        list(MxState.objects.order_by("code").values_list("code", "name")),
        list(ProductType.objects.order_by("code").values()),
    )


def test_p2_v15_seed_states_and_types():
    call_command("seed_dev_defaults")
    first = snapshot()
    call_command("seed_dev_defaults")
    assert snapshot() == first

    states, _ = first
    assert len(states) == 32
    assert all(len(code) == 3 for code, _ in states)

    types = {t.code: t for t in ProductType.objects.all()}
    assert set(types) == LAUNCH_TYPES
    assert types["apparel"].variant_axes == ["talla", "color"]
    assert all(t.variant_axes == [] for code, t in types.items() if code != "apparel")
    assert all(
        t.attribute_schema["$comment"] == "[PLACEHOLDER]" for t in types.values()
    )
    assert all(
        t.attribute_schema["additionalProperties"] is False for t in types.values()
    )
    for code in ("board_game", "accessory"):
        assert types[code].attribute_schema["properties"] == {}
    assert set(types["figure"].attribute_schema["properties"]) == {
        "linea",
        "numero",
        "escala",
        "altura_mm",
        "fabricante",
    }


def test_p2_v15_seed_keeps_admin_edits():
    call_command("seed_dev_defaults")
    ProductType.objects.filter(code="figure").update(name="Figuras")
    call_command("seed_dev_defaults")
    assert ProductType.objects.get(code="figure").name == "Figuras"
