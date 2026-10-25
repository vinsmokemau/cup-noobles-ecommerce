import pytest
from django.db import transaction

from apps.notifications.models import EmailOutbox
from apps.notifications.outbox import enqueue_email
from tests.factories.orders import DraftOrderFactory

pytestmark = pytest.mark.django_db


def test_enqueue_email_writes_a_pending_row_and_sends_nothing():
    order = DraftOrderFactory()

    row = enqueue_email(
        "cliente@example.test", "order_confirmation", {"total": 100}, order=order
    )

    row.refresh_from_db()
    assert (row.to_email, row.template, row.context) == (
        "cliente@example.test",
        "order_confirmation",
        {"total": 100},
    )
    assert row.order_id == order.pk
    assert (row.attempts, row.sent_at, row.dedupe_key) == (0, None, None)


def test_enqueue_email_rolls_back_with_the_callers_transaction():
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            enqueue_email("cliente@example.test", "order_confirmation")
            raise RuntimeError("the business change failed")

    assert not EmailOutbox.objects.exists()


def test_enqueue_email_with_the_same_dedupe_key_returns_the_first_row():
    with transaction.atomic():
        first = enqueue_email("a@example.test", "t", dedupe_key="k")
        second = enqueue_email("b@example.test", "t", dedupe_key="k")
        third = enqueue_email("c@example.test", "t")  # the transaction is still usable

    assert second.pk == first.pk
    assert EmailOutbox.objects.count() == 2
    assert third.pk != first.pk
