import time
from unittest.mock import MagicMock

import pytest

from apps.core import providers
from apps.notifications.models import EmailOutbox
from apps.notifications.outbox import enqueue_email
from apps.notifications.sending import send_pending
from tests.concurrency import run_concurrently  # type: ignore[attr-defined]  # tests/concurrency/ is also a directory
from tests.factories.orders import STAND_IN_ADDRESS, OrderFactory

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]


def test_p11_v10_overlapping_send_outbox_runs(monkeypatch):
    for _ in range(3):
        enqueue_email(
            "cliente@example.test",
            "order_expired",
            {},
            order=OrderFactory(state="paid", shipping_address=STAND_IN_ADDRESS),
        )
    sent_ids = []

    def slow_send(message):
        time.sleep(0.3)  # long enough for the other run to read the same rows
        sent_ids.append(message.outbox_id)
        return "id"

    sender = MagicMock()
    sender.send.side_effect = slow_send
    monkeypatch.setattr(providers, "email_sender", lambda: sender)

    outcomes = run_concurrently(lambda _i: send_pending(), 2)

    assert [o.error for o in outcomes] == [None, None]
    assert sorted(sent_ids) == sorted(EmailOutbox.objects.values_list("pk", flat=True))
