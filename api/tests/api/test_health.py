"""P1-V11, P1-V17: the health endpoint (ADR-0028)."""

from unittest import mock

import pytest
from django.db import OperationalError


@pytest.mark.django_db
def test_p1_v11_health_ok(api_client):
    response = api_client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"db": "ok"}


def test_p1_v17_health_503_when_db_down(api_client):
    with mock.patch("apps.core.views.connection") as connection:
        connection.cursor.side_effect = OperationalError("connection refused")
        response = api_client.get("/api/health/")

    assert response.status_code == 503
