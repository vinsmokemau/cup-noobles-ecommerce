"""Purchase limits per customer (SPEC.md T8.8, REQ-061, G31). The limit and the window are D15;
the values here are factory values."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.inventory.models import InventoryReservation
from apps.orders.models import Order
from apps.orders.purchase_limits import normalise_address, normalise_phone
from tests.factories.inventory import stocked_variant
from tests.factories.orders import (
    CHECKOUT_ADDRESS,
    cart_with,
    checkout,
    order_in_state,
    place_order,
)

pytestmark = pytest.mark.django_db

LIMIT = 2
WINDOW_DAYS = 30
OTHER_ADDRESS = {**CHECKOUT_ADDRESS, "street": "Avenida distinta", "ext_number": "99"}


@pytest.fixture(autouse=True)
def window(settings):
    settings.PURCHASE_LIMIT_WINDOW_DAYS = WINDOW_DAYS


@pytest.fixture
def checkout_client(cart_client, dev_defaults):
    return cart_client


@pytest.fixture
def limited():
    return stocked_variant(50, purchase_limit=LIMIT)


def earlier_order(variant, quantity, **fields):
    """A real `pending_payment` order, as an earlier checkout would leave it."""
    fields.setdefault("email", "otra@example.com")
    fields.setdefault("phone", "5511110000")
    fields.setdefault("address_or_location", OTHER_ADDRESS)
    return place_order(cart_with((variant, quantity)), **fields)


def test_p8_v20_purchase_limit_per_customer(checkout_client, dev_defaults, limited):
    earlier_order(limited, 1, email="cliente@example.com")

    over = checkout(checkout_client, cart_with((limited, 2)), phone="5599990000")

    assert over.status_code == 409
    assert over.json() == {
        "code": "lines_unavailable",
        "line_errors": [
            {
                "variant_public_id": str(limited.public_id),
                "sku": limited.sku,
                "code": "purchase_limit_exceeded",
                "requested": 2,
                "available": 1,
            }
        ],
    }
    assert Order.objects.count() == 1
    assert InventoryReservation.objects.count() == 1

    exact = checkout(checkout_client, cart_with((limited, 1)), phone="5599990000")

    assert exact.status_code == 201
    assert Order.objects.count() == 2


@pytest.mark.parametrize(
    ("earlier", "now"),
    [
        pytest.param(
            {"email": "Cliente@Example.com "},
            {"email": "cliente@example.com"},
            id="email",
        ),
        pytest.param(
            {"phone": "+52 55 5555 5555"}, {"phone": "5555555555"}, id="phone"
        ),
        pytest.param(
            {"address_or_location": {**CHECKOUT_ADDRESS, "street": "CALLE de Prueba."}},
            {"address_payload": CHECKOUT_ADDRESS},
            id="address",
        ),
    ],
)
def test_p8_v20_matches_by_email_phone_or_address_alone(
    checkout_client, limited, earlier, now
):
    earlier_order(limited, LIMIT, **earlier)
    other_customer = {
        "email": "nuevo@example.com",
        "phone": "5500000000",
        "address_payload": OTHER_ADDRESS,
    }

    response = checkout(
        checkout_client, cart_with((limited, 1)), **{**other_customer, **now}
    )

    assert response.status_code == 409
    assert response.json()["line_errors"][0]["available"] == 0
    assert Order.objects.count() == 1


def test_p8_v20_a_different_customer_is_not_limited(checkout_client, limited):
    earlier_order(limited, LIMIT)

    response = checkout(
        checkout_client,
        cart_with((limited, LIMIT)),
        email="nuevo@example.com",
        phone="5500000000",
        address_payload=CHECKOUT_ADDRESS,
    )

    assert response.status_code == 201


def test_p8_v20_blank_phones_do_not_match(checkout_client, limited):
    earlier_order(limited, LIMIT, phone="")

    response = checkout(
        checkout_client, cart_with((limited, 1)), email="nuevo@example.com", phone=""
    )

    assert response.status_code == 201


def test_p8_v20_a_variant_without_a_limit_is_never_refused(checkout_client):
    free = stocked_variant(50)
    earlier_order(free, 20, email="cliente@example.com")

    response = checkout(checkout_client, cart_with((free, 20)))

    assert response.status_code == 201


def test_p8_v20_only_the_limited_variant_counts(checkout_client, limited):
    earlier_order(limited, LIMIT, email="cliente@example.com")
    free = stocked_variant(50)

    response = checkout(checkout_client, cart_with((free, 3)))

    assert response.status_code == 201


def test_p8_v20_window_boundary(checkout_client, limited, clock):
    clock.travel("2026-03-01T12:00:00Z")
    earlier_order(limited, LIMIT, email="cliente@example.com")

    clock.travel("2026-03-31T11:59:59Z")  # 30 days minus one second
    inside = checkout(checkout_client, cart_with((limited, 1)))
    assert inside.status_code == 409

    clock.travel("2026-03-31T12:00:01Z")  # 30 days plus one second
    outside = checkout(checkout_client, cart_with((limited, 1)))
    assert outside.status_code == 201


@pytest.mark.parametrize("state", ["paid", "preparing", "shipped", "completed"])
def test_p8_v20_paid_and_later_orders_count(checkout_client, limited, state):
    order_in_state(
        state, email="cliente@example.com", shipping_address=OTHER_ADDRESS
    ).lines.create(
        variant=limited,
        sku=limited.sku,
        product_name="x",
        quantity=LIMIT,
        unit_price_cents=100,
        line_total_cents=100 * LIMIT,
    )

    response = checkout(checkout_client, cart_with((limited, 1)))

    assert response.status_code == 409


@pytest.mark.parametrize("state", ["draft", "cancelled", "expired", "refunded"])
def test_p8_v20_orders_that_gave_the_units_back_do_not_count(
    checkout_client, limited, state
):
    order_in_state(
        state, email="cliente@example.com", shipping_address=OTHER_ADDRESS
    ).lines.create(
        variant=limited,
        sku=limited.sku,
        product_name="x",
        quantity=LIMIT,
        unit_price_cents=100,
        line_total_cents=100 * LIMIT,
    )

    response = checkout(checkout_client, cart_with((limited, LIMIT)))

    assert response.status_code == 201


def test_p8_v20_stock_failure_is_listed_before_a_limit_failure(
    checkout_client, limited
):
    earlier_order(limited, LIMIT, email="cliente@example.com")
    short = stocked_variant(1)

    response = checkout(checkout_client, cart_with((limited, 1), (short, 3)))

    assert response.status_code == 409
    assert [error["code"] for error in response.json()["line_errors"]] == [
        "insufficient_stock",
        "purchase_limit_exceeded",
    ]


def test_p8_v20_a_limit_without_a_window_is_a_configuration_error(
    checkout_client, limited, settings
):
    settings.PURCHASE_LIMIT_WINDOW_DAYS = None

    with pytest.raises(ImproperlyConfigured, match="PURCHASE_LIMIT_WINDOW_DAYS"):
        checkout(checkout_client, cart_with((limited, 1)))


def test_p8_v20_no_window_needed_while_no_variant_is_limited(checkout_client, settings):
    settings.PURCHASE_LIMIT_WINDOW_DAYS = None

    response = checkout(checkout_client, cart_with((stocked_variant(5), 1)))

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+52 (55) 5555-5555", "5555555555"),
        ("5555555555", "5555555555"),
        ("044 55 5555 5555", "5555555555"),
        ("", ""),
        ("n/a", ""),
    ],
)
def test_p8_v20_phone_normalisation(raw, expected):
    assert normalise_phone(raw) == expected


def test_p8_v20_address_normalisation_ignores_case_accents_and_recipient():
    a = {**CHECKOUT_ADDRESS, "street": "Calle Ñandú", "recipient_name": "Ana"}
    b = {**CHECKOUT_ADDRESS, "street": "calle  nandu.", "recipient_name": "Beto"}

    assert normalise_address(a) == normalise_address(b) != ""
    assert normalise_address({"street": "Calle", "postal_code": ""}) == ""
    assert normalise_address(None) == ""
