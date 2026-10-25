"""The mock provider's checkout and refund (SPEC.md 9.9, ADR-0041, T8.10)."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from apps.core import providers
from apps.payments.mock import MockPaymentProvider
from tests.factories.orders import OrderFactory, OrderLineFactory
from tests.factories.payments import PaymentFactory

pytestmark = pytest.mark.django_db


def _store(settings) -> Path:
    return Path(settings.MOCK_STORE_DIR) / "payments"


def test_p8_v06_registry_returns_the_mock():
    assert isinstance(providers.payment_provider(), MockPaymentProvider)


def test_p8_v06_create_checkout_stores_a_preference(settings):
    settings.SITE_URL = "http://localhost:8080/"
    deadline = timezone.now() + timedelta(hours=4)
    order = OrderFactory(
        subtotal_cents=25000, total_cents=25000, payment_deadline_at=deadline
    )
    OrderLineFactory(order=order, sku="TAZA-1", quantity=2, unit_price_cents=12500)

    session = MockPaymentProvider().create_checkout(order)

    assert session.preference_id.startswith("mock_pref_")
    assert (
        session.url
        == f"http://localhost:8080/dev/payments/checkout/{session.preference_id}/"
    )
    stored = json.loads(
        (_store(settings) / f"{session.preference_id}.json").read_text(encoding="utf-8")
    )
    assert stored["external_reference"] == str(order.public_id)
    assert stored["total_cents"] == 25000
    assert stored["expires_at"] == deadline.isoformat()
    assert [(line["sku"], line["quantity"]) for line in stored["lines"]] == [
        ("TAZA-1", 2)
    ]


def test_p8_v06_writes_leave_no_temporary_files(settings):
    MockPaymentProvider().create_checkout(OrderFactory())
    assert [path.suffix for path in _store(settings).iterdir()] == [".json"]


def test_p8_v06_refund_defaults_to_what_is_left(settings):
    payment = PaymentFactory(amount_cents=10000, refunded_cents=2500)

    result = MockPaymentProvider().refund(payment, None)

    assert result.amount_cents == 7500
    assert result.refund_id.startswith("mock_ref_")
    stored = json.loads(
        (_store(settings) / f"{result.refund_id}.json").read_text(encoding="utf-8")
    )
    assert (stored["payment_id"], stored["amount_cents"]) == (payment.pk, 7500)


@pytest.mark.parametrize("amount", [0, -1, 10001])
def test_p8_v06_refund_never_exceeds_what_was_paid(settings, amount):
    payment = PaymentFactory(amount_cents=10000)
    with pytest.raises(ValueError):
        MockPaymentProvider().refund(payment, amount)
    assert not _store(settings).exists()
