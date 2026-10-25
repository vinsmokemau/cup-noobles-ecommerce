"""P6-V14, P6-V18: the guest order lookup (T6.7b, G35, ADR-0040)."""

import pytest
from django.core.cache import cache

from tests.factories.orders import OrderFactory, OrderLineFactory, ShipmentFactory

pytestmark = pytest.mark.django_db

URL = "/api/orders/lookup/"


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def order():
    order = OrderFactory(
        number="CN-2026-000123",
        email="Ana.Lopez@Example.com",
        phone="5555550100",
        state="paid",
        shipping_address={"postal_code": "06700", "street": "Calle Ejemplo 1"},
        subtotal_cents=25000,
        total_cents=25000,
        internal_note="no mostrar",
    )
    OrderLineFactory(
        order=order,
        sku="NDR-001",
        product_name="Nendoroid Link",
        quantity=2,
        unit_price_cents=12500,
        unit_cost_cents=7000,
    )
    return order


def lookup(client, number, email, **extra):
    return client.post(URL, {"number": number, "email": email}, format="json", **extra)


def test_p6_v14_guest_lookup(api_client, order):
    response = lookup(api_client, "CN-2026-000123", "ana.lopez@example.com")

    assert response.status_code == 200
    body = response.json()
    assert body["number"] == "CN-2026-000123"
    assert body["state"] == "paid"
    assert body["total_cents"] == 25000
    assert [line["sku"] for line in body["lines"]] == ["NDR-001"]
    assert body["lines"][0]["quantity"] == 2
    assert body["shipments"] == []
    assert response["Cache-Control"] == "no-store"
    # The status view never carries contact data, costs or staff notes.
    flat = response.content.decode().lower()
    for private in (
        "5555550100",
        "ana.lopez",
        "no mostrar",
        "unit_cost",
        "internal_note",
    ):
        assert private not in flat, private

    missing = lookup(api_client, "CN-2026-999999", "ana.lopez@example.com")
    wrong_email = lookup(api_client, "CN-2026-000123", "otra@example.com")
    assert missing.status_code == wrong_email.status_code == 404
    assert missing.content == wrong_email.content
    assert missing["Cache-Control"] == "no-store"


def test_p6_v14_lookup_shows_the_tracking_link(api_client, order):
    ShipmentFactory(
        order=order,
        carrier="manual",
        tracking_number="ABC123",
        tracking_url="https://carrier.example/track/ABC123",
    )

    shipment = lookup(api_client, order.number, order.email).json()["shipments"][0]

    assert shipment["tracking_number"] == "ABC123"
    assert shipment["tracking_url"] == "https://carrier.example/track/ABC123"


@pytest.mark.parametrize(
    "body", [{}, {"number": "CN-2026-000123"}, {"email": "a@b.co"}]
)
def test_p6_v14_lookup_requires_both_fields(api_client, order, body):
    response = api_client.post(URL, body, format="json")

    assert response.status_code == 400
    assert set(response.json()) == {"number", "email"} - set(body)


def test_p6_v14_the_email_in_the_url_is_not_accepted(api_client, order):
    response = api_client.get(f"{URL}?number={order.number}&email={order.email}")

    assert response.status_code == 405


def test_p6_v18_guest_lookup_rate_limit(api_client, order, clock):
    clock.travel("2026-10-25T12:00:00Z")
    for attempt in range(5):
        assert (
            lookup(api_client, "CN-2026-999999", "x@example.com").status_code == 404
        ), attempt

    limited = lookup(api_client, order.number, order.email)
    assert limited.status_code == 429
    assert "email" not in limited.json()

    clock.travel("2026-10-25T13:00:01Z")
    assert lookup(api_client, order.number, order.email).status_code == 200


def test_p6_v18_the_limit_is_per_ip(api_client, order):
    for _ in range(5):
        lookup(
            api_client,
            "CN-2026-999999",
            "x@example.com",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
        )

    assert (
        lookup(
            api_client, order.number, order.email, HTTP_X_FORWARDED_FOR="203.0.113.7"
        ).status_code
        == 429
    )
    assert (
        lookup(
            api_client, order.number, order.email, HTTP_X_FORWARDED_FOR="203.0.113.8"
        ).status_code
        == 200
    )


def test_p6_v18_a_forged_forwarded_for_does_not_reset_the_limit(api_client, order):
    """Our proxy appends the real address last; a caller-supplied prefix cannot dodge it."""
    for n in range(5):
        lookup(
            api_client,
            "CN-2026-999999",
            "x@example.com",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{n}, 203.0.113.7",
        )

    assert (
        lookup(
            api_client,
            order.number,
            order.email,
            HTTP_X_FORWARDED_FOR="10.9.9.9, 203.0.113.7",
        ).status_code
        == 429
    )


@pytest.mark.parametrize("forwarded", ["not-an-ip", "", ",", "999.1.1.1"])
def test_p6_v18_an_unusable_address_is_limited_not_a_server_error(
    api_client, forwarded
):
    response = lookup(
        api_client, "CN-2026-999999", "x@example.com", HTTP_X_FORWARDED_FOR=forwarded
    )

    assert response.status_code == 404
