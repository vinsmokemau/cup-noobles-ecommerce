"""P13-V26, V27: the token edges the happy paths do not reach (T13.9, T13.10, G21, G22)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.core import signing
from django.core.cache import cache

from apps.orders import status_token

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_counters():
    cache.clear()
    yield
    cache.clear()


def _forge(public_id, exp):
    """A correctly signed token, for an order or an expiry the server never issued."""
    return signing.dumps({"o": str(public_id), "exp": exp}, salt=status_token.SALT)


def _future():
    return int((datetime.now(UTC) + timedelta(minutes=30)).timestamp())


def test_p13_v26_a_signed_token_for_a_missing_order_is_the_same_404(api_client):
    ghost = uuid.uuid4()
    token = _forge(ghost, _future())

    response = api_client.get(f"/api/orders/{ghost}/status/?t={token}")
    unsigned = api_client.get(f"/api/orders/{ghost}/status/")

    assert response.status_code == 404
    assert response.json() == unsigned.json()


def test_p13_v26_a_token_without_an_integer_expiry_is_refused():
    public_id = uuid.uuid4()
    assert status_token.is_valid(_forge(public_id, _future()), str(public_id))
    assert not status_token.is_valid(_forge(public_id, "soon"), str(public_id))
    assert not status_token.is_valid(_forge(public_id, None), str(public_id))


def test_p13_v27_a_signed_token_for_a_missing_order_is_the_same_404(api_client):
    ghost = uuid.uuid4()
    token = _forge(ghost, _future())

    response = api_client.post(f"/api/orders/{ghost}/pay/?t={token}")
    unsigned = api_client.post(f"/api/orders/{ghost}/pay/")

    assert response.status_code == 404
    assert response.json() == unsigned.json()
