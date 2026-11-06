"""T13.11: the read-only CFDI catalog endpoint behind the checkout's "Quiero factura" section."""

import json

import pytest

from apps.invoicing.catalogs import CATALOG_PATH

URL = "/api/invoicing/cfdi-catalogs/"


def test_t13_11_serves_the_fixture_codes_and_names(api_client):
    response = api_client.get(URL)

    assert response.status_code == 200
    fixture = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert response.json() == {
        "regimen_fiscal": fixture["regimen_fiscal"],
        "uso_cfdi": fixture["uso_cfdi"],
    }


def test_t13_11_is_cacheable_and_read_only(api_client):
    response = api_client.get(URL)

    assert "public" in response["Cache-Control"]
    assert "max-age=" in response["Cache-Control"]
    assert api_client.post(URL, {}, format="json").status_code == 405


@pytest.mark.parametrize("field", ["regimen_fiscal", "uso_cfdi"])
def test_t13_11_every_offered_code_passes_checkout_validation(api_client, field):
    from apps.invoicing import catalogs

    offered = {item["code"] for item in api_client.get(URL).json()[field]}
    accepted = (
        catalogs.tax_regime_codes()
        if field == "regimen_fiscal"
        else catalogs.cfdi_use_codes()
    )
    assert offered == accepted
