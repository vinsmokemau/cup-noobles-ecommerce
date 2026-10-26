"""Invoice data at checkout (SPEC.md T8.7, REQ-060, A8)."""

import pytest

from apps.inventory.models import InventoryReservation
from apps.invoicing.models import InvoiceRequest
from apps.orders.models import Order
from tests.factories.inventory import stocked_variant
from tests.factories.orders import cart_with, checkout

pytestmark = pytest.mark.django_db

# Test data only; the codes are in the sample catalog, not the accountant's subset (D16).
INVOICE = {
    "rfc": "XAXX010101000",
    "legal_name": "Cliente de Prueba SA de CV",
    "fiscal_postal_code": "06700",
    "tax_regime": "601",
    "cfdi_use": "G03",
}


@pytest.fixture
def checkout_client(cart_client, dev_defaults):
    return cart_client


def test_p8_v19_invoice_data_at_checkout(checkout_client):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(checkout_client, cart, invoice=INVOICE)

    assert response.status_code == 201
    order = Order.objects.get()
    request = InvoiceRequest.objects.get()
    assert request.order == order
    assert request.status == InvoiceRequest.Status.REQUESTED
    assert (
        request.rfc,
        request.legal_name,
        request.fiscal_postal_code,
        request.tax_regime,
        request.cfdi_use,
    ) == tuple(INVOICE.values())


def test_p8_v19_without_invoice_data_no_request_is_created(checkout_client):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(checkout_client, cart)

    assert response.status_code == 201
    assert not InvoiceRequest.objects.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rfc", "XAXX0101"),
        ("rfc", "XAXX010101000X"),
        ("rfc", "12XX010101000"),
        ("rfc", "XAXX01010A000"),
        ("fiscal_postal_code", "0670"),
        ("fiscal_postal_code", "067000"),
        ("fiscal_postal_code", "0670A"),
        ("tax_regime", "999"),
        ("cfdi_use", "ZZZ"),
        ("legal_name", ""),
    ],
)
def test_p8_v19_invalid_invoice_data_returns_field_errors_and_no_order(
    checkout_client, field, value
):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(checkout_client, cart, invoice={**INVOICE, field: value})

    assert response.status_code == 400
    assert field in response.json()["invoice"]
    assert not Order.objects.exists()
    assert not InvoiceRequest.objects.exists()
    assert not InventoryReservation.objects.exists()


def test_p8_v19_a_missing_invoice_field_is_a_field_error(checkout_client):
    cart = cart_with((stocked_variant(5), 1))
    invoice = {name: value for name, value in INVOICE.items() if name != "rfc"}

    response = checkout(checkout_client, cart, invoice=invoice)

    assert response.status_code == 400
    assert "rfc" in response.json()["invoice"]
    assert not Order.objects.exists()


@pytest.mark.parametrize("rfc", ["XAXX010101000", "MAÑ010101AB1", "A&B010101XY9"])
def test_p8_v19_rfc_accepts_ene_and_ampersand(checkout_client, rfc):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(checkout_client, cart, invoice={**INVOICE, "rfc": rfc})

    assert response.status_code == 201
    assert InvoiceRequest.objects.get().rfc == rfc


def test_p8_v19_a_lowercase_rfc_is_stored_uppercase(checkout_client):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(
        checkout_client, cart, invoice={**INVOICE, "rfc": " xaxx010101000 "}
    )

    assert response.status_code == 201
    assert InvoiceRequest.objects.get().rfc == "XAXX010101000"


def test_p8_v19_a_stock_failure_leaves_no_invoice_request(checkout_client):
    cart = cart_with((stocked_variant(1), 3))

    response = checkout(checkout_client, cart, invoice=INVOICE)

    assert response.status_code == 409
    assert not InvoiceRequest.objects.exists()


def test_p8_v19_a_replay_does_not_create_a_second_request(checkout_client):
    cart = cart_with((stocked_variant(5), 1))

    first = checkout(checkout_client, cart, invoice=INVOICE, idempotency_key="k")
    second = checkout(checkout_client, cart, invoice=INVOICE, idempotency_key="k")

    assert (first.status_code, second.status_code) == (201, 200)
    assert InvoiceRequest.objects.count() == 1
