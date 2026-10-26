"""Simulator refusals: wrong provider, unknown ids, bad input (SPEC.md 9.10; T9.17 coverage gaps)."""

import pytest

from apps.core import providers
from apps.payments.base import NormalizedStatus
from tests.factories.orders import OrderFactory, OrderLineFactory


@pytest.fixture
def order(db):
    order = OrderFactory(subtotal_cents=116000, total_cents=116000)
    OrderLineFactory(order=order, quantity=1, unit_price_cents=116000)
    return order


@pytest.fixture
def preference_id(order):
    return providers.payment_provider().create_checkout(order).preference_id


@pytest.fixture
def card_payment_id(preference_id):
    return providers.payment_provider().record_payment(
        preference_id, status=NormalizedStatus.APPROVED, method="credit_card"
    )


@pytest.fixture
def voucher_payment_id(preference_id):
    return providers.payment_provider().record_payment(
        preference_id, status=NormalizedStatus.PENDING, method="oxxo"
    )


def test_every_page_is_404_when_the_provider_is_not_the_mock(
    client, preference_id, monkeypatch
):
    class Other:
        code = "mercadopago"

    monkeypatch.setattr(providers, "payment_provider", lambda: Other())

    assert client.get(f"/dev/payments/checkout/{preference_id}/").status_code == 404


def test_an_unknown_outcome_is_404(client, preference_id):
    response = client.post(f"/dev/payments/checkout/{preference_id}/vanish/")

    assert response.status_code == 404


def test_an_installment_plan_that_is_not_a_number_is_a_400(client, preference_id):
    response = client.post(
        f"/dev/payments/checkout/{preference_id}/installments/",
        {"installments": "seis"},
    )

    assert response.status_code == 400


def test_the_voucher_of_an_unknown_payment_is_404(client, db):
    response = client.get("/dev/payments/voucher/mock_pay_" + "0" * 32 + "/")

    assert response.status_code == 404


def test_a_card_payment_has_no_voucher_page(client, card_payment_id):
    response = client.get(f"/dev/payments/voucher/{card_payment_id}/")

    assert response.status_code == 404


def test_an_unknown_voucher_action_is_404(client, voucher_payment_id):
    response = client.post(f"/dev/payments/voucher/{voucher_payment_id}/refund/")

    assert response.status_code == 404


def test_a_voucher_action_on_an_unknown_payment_is_404(client, db):
    response = client.post("/dev/payments/voucher/mock_pay_" + "0" * 32 + "/received/")

    assert response.status_code == 404


def test_a_voucher_action_on_a_card_payment_is_404(client, card_payment_id):
    response = client.post(f"/dev/payments/voucher/{card_payment_id}/received/")

    assert response.status_code == 404
