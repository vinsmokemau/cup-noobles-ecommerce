"""P6-V13: the postal-code lookup (T6.6)."""

import csv
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[3] / "fixtures" / "mx_postal_codes_sample.csv"

pytestmark = pytest.mark.django_db


def sample_rows() -> list[dict[str, str]]:
    with SAMPLE.open(encoding="utf-8") as handle:
        lines = (line for line in handle if not line.startswith("#"))
        return list(csv.DictReader(lines))


def test_p6_v13_postal_lookup(api_client, postal_codes):
    response = api_client.get("/api/postal-codes/06700/")

    assert response.status_code == 200
    assert response.json() == {
        "state_code": "CMX",
        "state_name": "Ciudad de México",
        "municipality": "Cuauhtémoc",
        "neighborhoods": sorted(
            r["neighborhood"] for r in sample_rows() if r["postal_code"] == "06700"
        ),
    }
    assert api_client.get("/api/postal-codes/99999/").status_code == 404
    for malformed in ("0670", "067000", "abcde", "0670a", "٠٦٧٠٠"):
        assert api_client.get(f"/api/postal-codes/{malformed}/").status_code == 400, (
            malformed
        )


def test_p6_v13_every_sample_code_resolves_to_its_state(api_client, postal_codes):
    rows = sample_rows()

    for code in {r["postal_code"] for r in rows}:
        body = api_client.get(f"/api/postal-codes/{code}/").json()
        expected = [r for r in rows if r["postal_code"] == code]
        assert body["state_code"] == expected[0]["state_code"]
        assert len(body["neighborhoods"]) == len(expected)
    assert {"06700", "97000"} <= {r["postal_code"] for r in rows}
    assert {r["state_code"] for r in rows} >= {
        "CMX",
        "MEX",
        "JAL",
        "NLE",
        "YUC",
        "PUE",
    }


def test_p6_v13_found_is_cached_and_missing_is_not(api_client, postal_codes):
    found = api_client.get("/api/postal-codes/97000/")
    missing = api_client.get("/api/postal-codes/99999/")

    assert found["Cache-Control"] == "public, max-age=86400"
    assert "public" not in missing.get("Cache-Control", "")


def test_p6_v13_is_anonymous_and_get_only(api_client, postal_codes):
    api_client.cookies["sessionid"] = "stale"

    assert api_client.get("/api/postal-codes/06700/").status_code == 200
    assert api_client.post("/api/postal-codes/06700/").status_code == 405
