"""`manage.py load_postal_codes` (T6.6, §4.3): file in, rows out, no network."""

import pytest
from django.core.management import CommandError, call_command

from apps.shipping.models import MxPostalCode

pytestmark = pytest.mark.django_db

HEADER = "postal_code,neighborhood,municipality,state_code\n"


def all_rows():
    return list(MxPostalCode.objects.order_by("postal_code", "neighborhood").values())


def test_sample_loads_without_a_path_and_a_rerun_changes_nothing():
    call_command("seed_states")

    call_command("load_postal_codes")
    first = all_rows()
    call_command("load_postal_codes")

    assert len(first) >= 40
    assert all_rows() == first


def test_a_rerun_updates_a_changed_row(tmp_path):
    call_command("seed_states")
    path = tmp_path / "cp.csv"
    path.write_text(
        HEADER + "# a comment\n06700,Roma Norte,Cuauhtémoc,CMX\n", encoding="utf-8"
    )
    call_command("load_postal_codes", str(path))
    path.write_text(HEADER + "06700,Roma Norte,Otro,CMX\n", encoding="utf-8")

    call_command("load_postal_codes", str(path))

    assert MxPostalCode.objects.get(postal_code="06700").municipality == "Otro"


def test_sepomex_needs_a_path(settings):
    settings.POSTAL_CODE_DATASET = "sepomex"

    with pytest.raises(CommandError, match="needs the path"):
        call_command("load_postal_codes")


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("06700,Roma Norte,Cuauhtémoc,ZZZ\n", "unknown state_code"),
        ("6700,Roma Norte,Cuauhtémoc,CMX\n", "malformed"),
        ("06700,,Cuauhtémoc,CMX\n", "malformed"),
    ],
)
def test_a_bad_row_loads_nothing(tmp_path, body, message):
    call_command("seed_states")
    path = tmp_path / "cp.csv"
    path.write_text(
        HEADER + "97000,Mérida Centro,Mérida,YUC\n" + body, encoding="utf-8"
    )

    with pytest.raises(CommandError, match=message):
        call_command("load_postal_codes", str(path))

    assert MxPostalCode.objects.count() == 0


def test_wrong_columns_and_missing_file(tmp_path):
    path = tmp_path / "cp.csv"
    path.write_text("cp,colonia\n06700,Roma\n", encoding="utf-8")

    with pytest.raises(CommandError, match="expected the columns"):
        call_command("load_postal_codes", str(path))
    with pytest.raises(CommandError, match="no such file"):
        call_command("load_postal_codes", str(tmp_path / "nope.csv"))
