from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.db import transaction
from django.utils import timezone

from apps.core import providers
from apps.notifications.models import EmailOutbox
from apps.notifications.outbox import enqueue_email
from apps.notifications.sending import MAX_ATTEMPTS, next_attempt_at, send_pending
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


@pytest.fixture
def queued(template_context, settings, tmp_path):
    """`queued(template)` enqueues a row for a factory order; emails go to `tmp_path`."""
    settings.EMAIL_FILE_DIR = str(tmp_path)

    def enqueue(template="order_confirmation"):
        context, order = template_context(template)
        return enqueue_email("cliente@example.test", template, context, order=order)

    return enqueue


def test_p11_v02_failure_then_recovery(queued, settings, tmp_path):
    rows = [queued("order_confirmation"), queued("order_expired")]

    settings.EMAIL_MOCK_FAIL = True
    assert send_pending() == (0, 2)
    for row in rows:
        row.refresh_from_db()
        assert (row.attempts, row.sent_at) == (1, None)
        assert "EMAIL_MOCK_FAIL" in row.last_error
    assert list(tmp_path.iterdir()) == []

    settings.EMAIL_MOCK_FAIL = False
    # the next run, once the first backoff has elapsed
    assert send_pending(now=timezone.now() + timedelta(hours=1)) == (2, 0)
    for row in rows:
        row.refresh_from_db()
        assert row.sent_at is not None
    names = sorted(p.name for p in tmp_path.iterdir())
    assert len(names) == 4
    assert {n.rsplit(".", 1)[1] for n in names} == {"html", "txt"}
    assert all(f"-{row.pk}." in " ".join(names) for row in rows)


def test_p11_v05_backoff_and_give_up(queued, settings, monkeypatch):
    settings.EMAIL_MOCK_FAIL = True
    reporter = MagicMock()
    monkeypatch.setattr(providers, "error_reporter", lambda: reporter)
    row = queued()

    delays = []
    for attempt in range(MAX_ATTEMPTS):
        row.refresh_from_db()
        due = next_attempt_at(row)
        delays.append(due - row.created_at)
        # a run just before the backoff elapsed leaves the row alone
        assert send_pending(now=due - timedelta(seconds=1)) == (0, 0)
        assert send_pending(now=due) == (0, 1)
        row.refresh_from_db()
        assert row.attempts == attempt + 1

    # the gap between attempts doubles each time
    steps = [b - a for a, b in zip(delays, delays[1:], strict=False)]
    assert delays[0] == timedelta(0)
    assert all(
        later == earlier * 2 for earlier, later in zip(steps, steps[1:], strict=False)
    )
    reporter.capture_message.assert_called_once()
    assert str(row.pk) in reporter.capture_message.call_args.args[0]

    # after the 6th failure there are no more attempts
    assert send_pending(now=timezone.now() + timedelta(days=30)) == (0, 0)
    row.refresh_from_db()
    assert (row.attempts, row.sent_at) == (MAX_ATTEMPTS, None)
    reporter.capture_message.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_p11_v06_outbox_rolls_back_with_transaction():
    order = DraftOrderFactory()

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            enqueue_email("cliente@example.test", "order_confirmation", order=order)
            raise RuntimeError("the state change failed")

    assert not EmailOutbox.objects.exists()


def test_send_pending_sets_outbox_id_and_reply_to(queued, settings, monkeypatch):
    settings.EMAIL_REPLY_TO = "tienda@cupnoobles.test"
    sender = MagicMock()
    sender.send.return_value = "id"
    monkeypatch.setattr(providers, "email_sender", lambda: sender)
    row = queued("order_shipped")

    assert send_pending() == (1, 0)

    message = sender.send.call_args.args[0]
    assert message.reply_to == "tienda@cupnoobles.test"
    assert message.outbox_id == row.pk
    assert (message.to, message.template) == ("cliente@example.test", "order_shipped")
    assert message.html and message.text and message.subject
