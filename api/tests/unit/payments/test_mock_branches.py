"""Mock provider branches the other suites do not reach: races on the store and bad ids
(SPEC.md 9.9; T9.17 coverage gaps)."""

from pathlib import Path

import pytest

from apps.payments.base import NormalizedStatus, PaymentNotFound, RefundNotSupported
from apps.payments.mock import MockPaymentProvider
from tests.factories.orders import OrderFactory, OrderLineFactory
from tests.factories.payments import PaymentFactory


@pytest.fixture
def provider():
    return MockPaymentProvider()


@pytest.fixture
def preference(provider, db):
    order = OrderFactory(subtotal_cents=116000, total_cents=116000)
    OrderLineFactory(order=order, quantity=1, unit_price_cents=116000)
    return order, provider.create_checkout(order).preference_id


def _vanish_on_read(monkeypatch, prefix: str):
    """Make every stored file whose name starts with `prefix` disappear between list and read."""
    read_text = Path.read_text

    def read(self, *args, **kwargs):
        if self.name.startswith(prefix):
            raise FileNotFoundError(self)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)


def test_a_record_removed_while_listing_is_skipped(provider, preference, monkeypatch):
    assert provider.list_records()["preferences"]
    _vanish_on_read(monkeypatch, "mock_pref_")

    assert provider.list_records()["preferences"] == []


def test_a_notification_taken_while_listing_is_skipped(
    provider, preference, monkeypatch
):
    _, preference_id = preference
    payment_id = provider.record_payment(
        preference_id, status=NormalizedStatus.APPROVED, method="credit_card"
    )
    provider.queue_notification(payment_id)
    assert len(provider.queued_notifications()) == 1
    _vanish_on_read(monkeypatch, "mock_ntf_")

    assert provider.queued_notifications() == []


def test_a_stored_oxxo_payment_cannot_be_refunded_even_if_the_row_says_otherwise(
    provider, preference
):
    order, preference_id = preference
    payment_id = provider.record_payment(
        preference_id, status=NormalizedStatus.APPROVED, method="oxxo"
    )
    payment = PaymentFactory(
        order=order,
        provider="mock",
        provider_payment_id=payment_id,
        method="credit_card",
        status="approved",
        amount_cents=116000,
    )

    with pytest.raises(RefundNotSupported):
        provider.refund(payment, None)


def test_a_refund_of_a_payment_missing_from_the_store_only_records_the_refund(
    provider, db
):
    payment = PaymentFactory(
        provider="mock",
        provider_payment_id="mock_pay_" + "a" * 32,
        method="credit_card",
        status="approved",
        amount_cents=10000,
    )

    result = provider.refund(payment, 4000)

    assert result.amount_cents == 4000
    assert provider.queued_notifications() == []


def test_recording_a_payment_for_an_unknown_preference_fails(provider, db):
    with pytest.raises(PaymentNotFound):
        provider.record_payment(
            "mock_pref_" + "0" * 32,
            status=NormalizedStatus.APPROVED,
            method="credit_card",
        )


def test_updating_an_unknown_payment_fails(provider, db):
    with pytest.raises(PaymentNotFound):
        provider.update_payment("mock_pay_" + "0" * 32, status="approved")


def test_discarding_a_notification_with_a_malformed_id_touches_nothing(
    provider, preference, settings
):
    _, preference_id = preference
    folder = Path(settings.MOCK_STORE_DIR) / "payments"
    before = sorted(path.name for path in folder.glob("*.json"))

    provider.discard_notification("../" + preference_id)

    assert sorted(path.name for path in folder.glob("*.json")) == before
