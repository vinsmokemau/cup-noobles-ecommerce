"""T1.13b: the routes the end-to-end stack check reads through the proxy (P1-V01, P1-V02)."""

import json

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_schema_endpoint_serves_openapi(api_client):
    response = api_client.get(
        "/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json"
    )

    assert response.status_code == 200
    assert json.loads(response.content)["openapi"].startswith("3.1")


@pytest.mark.django_db
def test_admin_login_page_renders(api_client):
    response = api_client.get("/admin/login/")

    assert response.status_code == 200
    assert b'name="username"' in response.content


def test_seed_e2e_writes_manifest(settings, tmp_path):
    settings.BASE_DIR = tmp_path

    call_command("seed_e2e")
    call_command("seed_e2e")

    assert json.loads((tmp_path / "var" / "e2e" / "manifest.json").read_text()) == {}
