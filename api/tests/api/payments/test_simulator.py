"""T9.10: the payment simulator pages. Verify is `[no-test]`; T9.11's test drives every button
once delivery exists. These tests cover what T9.10 itself adds: the routing gate, the pages, and
what each button records and queues."""

import importlib
import json
from pathlib import Path

import pytest
from django.urls import clear_url_caches

from apps.core import providers
from apps.payments.base import NormalizedStatus
from tests.factories.orders import OrderFactory, OrderLineFactory

BANNER = "SIMULADOR — ningún pago es real"


@pytest.fixture
def order(db):
    order = OrderFactory(subtotal_cents=116000, total_cents=116000)
    OrderLineFactory(order=order, quantity=1, unit_price_cents=116000)
    return order


@pytest.fixture
def preference_id(order):
    return providers.payment_provider().create_checkout(order).preference_id


def _checkout_url(preference_id: str) -> str:
    return f"/dev/payments/checkout/{preference_id}/"


def _store(settings) -> Path:
    return Path(settings.MOCK_STORE_DIR) / "payments"


def _records(settings, prefix: str) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(_store(settings).glob(f"{prefix}*.json"))
    ]


def test_checkout_page_shows_the_order_and_every_button(client, order, preference_id):
    response = client.get(_checkout_url(preference_id))

    html = response.content.decode()
    assert response.status_code == 200
    assert BANNER in html
    assert order.number in html
    assert "$1,160.00 MXN" in html
    for label in (
        "Aprobar con tarjeta",
        "Aprobar a meses sin intereses",
        "Pagar en OXXO",
        "Pagar por SPEI",
        "Rechazar",
        "Dejar expirar",
    ):
        assert label in html


def test_unknown_preference_is_404(client, db):
    response = client.get(_checkout_url("mock_pref_" + "0" * 32))

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("outcome", "status", "method", "back"),
    [
        ("card", NormalizedStatus.APPROVED, "credit_card", "gracias"),
        ("oxxo", NormalizedStatus.PENDING, "oxxo", "pendiente"),
        ("spei", NormalizedStatus.PENDING, "spei", "pendiente"),
        ("reject", NormalizedStatus.REJECTED, "credit_card", "error"),
    ],
)
def test_outcome_records_a_payment_queues_a_notification_and_redirects(
    client, settings, order, preference_id, outcome, status, method, back
):
    response = client.post(f"{_checkout_url(preference_id)}{outcome}/")

    payments = _records(settings, "mock_pay_")
    assert len(payments) == 1
    assert payments[0]["status"] == status.value
    assert payments[0]["method"] == method
    assert payments[0]["external_reference"] == str(order.public_id)
    notifications = _records(settings, "mock_ntf_")
    assert [n["data"] for n in notifications] == [{"id": payments[0]["id"]}]
    assert response.status_code == 302
    assert response["Location"].endswith(f"/pedido/{order.public_id}/{back}")


def test_installments_use_the_configured_options(client, settings, preference_id):
    settings.PAYMENT_INSTALLMENT_OPTIONS = [3, 6]

    client.post(f"{_checkout_url(preference_id)}installments/", {"installments": 6})
    rejected = client.post(
        f"{_checkout_url(preference_id)}installments/", {"installments": 12}
    )

    payments = _records(settings, "mock_pay_")
    assert [(p["status"], p["installments"]) for p in payments] == [("approved", 6)]
    assert rejected.status_code == 400
    assert len(_records(settings, "mock_ntf_")) == 1


def test_expire_records_nothing_and_queues_nothing(
    client, settings, order, preference_id
):
    response = client.post(f"{_checkout_url(preference_id)}expire/")

    assert _records(settings, "mock_pay_") == []
    assert _records(settings, "mock_ntf_") == []
    assert response["Location"].endswith(f"/pedido/{order.public_id}/error")


@pytest.mark.parametrize("outcome", ["oxxo", "spei"])
def test_pending_payment_carries_a_voucher_that_expires_with_the_order(
    client, settings, order, preference_id, outcome
):
    client.post(f"{_checkout_url(preference_id)}{outcome}/")

    payment = _records(settings, "mock_pay_")[0]
    assert payment["voucher_url"].endswith(f"/dev/payments/voucher/{payment['id']}/")
    assert payment["voucher_expires_at"] == (
        order.payment_deadline_at.isoformat() if order.payment_deadline_at else None
    )


@pytest.mark.parametrize(
    ("outcome", "text"), [("oxxo", "Ficha de pago OXXO"), ("spei", "CLABE")]
)
def test_voucher_page_shows_the_instructions_and_both_buttons(
    client, settings, preference_id, outcome, text
):
    client.post(f"{_checkout_url(preference_id)}{outcome}/")
    payment_id = _records(settings, "mock_pay_")[0]["id"]

    response = client.get(f"/dev/payments/voucher/{payment_id}/")

    html = response.content.decode()
    assert response.status_code == 200
    assert BANNER in html
    assert text in html
    assert "Simular pago recibido" in html
    assert "Simular vencimiento" in html


@pytest.mark.parametrize(
    ("action", "status"), [("received", "approved"), ("expired", "cancelled")]
)
def test_voucher_buttons_move_the_payment_and_queue_a_notification(
    client, settings, preference_id, action, status
):
    client.post(f"{_checkout_url(preference_id)}oxxo/")
    payment_id = _records(settings, "mock_pay_")[0]["id"]

    client.post(f"/dev/payments/voucher/{payment_id}/{action}/")

    assert _records(settings, "mock_pay_")[0]["status"] == status
    assert len(_records(settings, "mock_ntf_")) == 2


def test_voucher_buttons_do_nothing_once_the_payment_is_settled(
    client, settings, preference_id
):
    client.post(f"{_checkout_url(preference_id)}oxxo/")
    payment_id = _records(settings, "mock_pay_")[0]["id"]
    client.post(f"/dev/payments/voucher/{payment_id}/received/")

    client.post(f"/dev/payments/voucher/{payment_id}/expired/")

    assert _records(settings, "mock_pay_")[0]["status"] == "approved"
    assert len(_records(settings, "mock_ntf_")) == 2


def test_forms_post_with_their_csrf_token(settings, preference_id):
    from rest_framework.test import APIClient

    strict = APIClient(enforce_csrf_checks=True)
    page = strict.get(_checkout_url(preference_id))
    token = page.cookies["csrftoken"].value

    refused = strict.post(f"{_checkout_url(preference_id)}card/")
    accepted = strict.post(
        f"{_checkout_url(preference_id)}card/", {"csrfmiddlewaretoken": token}
    )

    assert refused.status_code == 403
    assert accepted.status_code == 302
    assert len(_records(settings, "mock_pay_")) == 1


def test_routes_are_not_registered_when_dev_tools_are_off(
    client, settings, preference_id
):
    import config.urls

    settings.DEV_TOOLS_ENABLED = False
    clear_url_caches()
    importlib.reload(config.urls)
    try:
        response = client.get(_checkout_url(preference_id))
    finally:
        settings.DEV_TOOLS_ENABLED = True
        clear_url_caches()
        importlib.reload(config.urls)

    assert response.status_code == 404
