"""The mock payment store never holds a half-written file (SPEC.md 9.9, P9-V18)."""

import json
from pathlib import Path

import pytest

from apps.payments.base import NormalizedStatus
from apps.payments.mock import MockPaymentProvider
from tests.concurrency import run_concurrently  # type: ignore[attr-defined]  # tests/concurrency/ is also a directory
from tests.factories.orders import OrderFactory

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]

WRITERS = 8
ROUNDS = 25


def test_p9_v18_mock_store_atomic_writes(settings):
    provider = MockPaymentProvider()
    preference_id = provider.create_checkout(OrderFactory()).preference_id
    payment_id = provider.record_payment(
        preference_id, status=NormalizedStatus.PENDING, method="spei"
    )
    path = Path(settings.MOCK_STORE_DIR) / "payments" / f"{payment_id}.json"
    statuses = [NormalizedStatus.APPROVED, NormalizedStatus.REJECTED]

    def hammer(index: int) -> int:
        # Half the racers write, half read: a reader must never see a partial file.
        reads = 0
        for _ in range(ROUNDS):
            if index % 2:
                json.loads(path.read_text(encoding="utf-8"))
                reads += 1
            else:
                provider.update_payment(
                    payment_id, status=statuses[index // 2 % 2].value
                )
        return reads

    outcomes = run_concurrently(hammer, WRITERS)

    assert [outcome.error for outcome in outcomes] == [None] * WRITERS
    assert json.loads(path.read_text(encoding="utf-8"))["status"] in {
        status.value for status in statuses
    }
    assert provider.fetch_payment(payment_id).status in statuses
    assert [p.suffix for p in path.parent.iterdir() if p.suffix == ".tmp"] == []
