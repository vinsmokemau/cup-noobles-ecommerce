"""The mock payment provider (SPEC.md §4.3, 9.9). `MOCK_STORE_DIR/payments/` holds its state.

T8.10 builds `create_checkout` and `refund`; T9.9 completes the class. State lives in JSON files,
one per preference and per refund, outside the database on purpose: a real provider's state is
outside our transactions. Ids carry a `mock_` prefix so they are never mistaken for real ones.
"""

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.orders.models import Order
from apps.payments.base import CheckoutSession, RefundResult
from apps.payments.models import Payment


class MockPaymentProvider:
    code = "mock"

    def create_checkout(self, order: Order) -> CheckoutSession:
        preference_id = f"mock_pref_{uuid.uuid4().hex}"
        deadline = order.payment_deadline_at
        self._write(
            preference_id,
            {
                "id": preference_id,
                "external_reference": str(order.public_id),
                "total_cents": order.total_cents,
                "lines": [
                    {
                        "sku": line.sku,
                        "name": line.product_name,
                        "quantity": line.quantity,
                        "unit_price_cents": line.unit_price_cents,
                    }
                    for line in order.lines.order_by("id")
                ],
                "expires_at": deadline.isoformat() if deadline else None,
            },
        )
        site_url = str(settings.SITE_URL).rstrip("/")
        return CheckoutSession(
            preference_id=preference_id,
            url=f"{site_url}/dev/payments/checkout/{preference_id}/",
        )

    def refund(self, payment: Payment, amount_cents: int | None) -> RefundResult:
        """Refund `amount_cents`, or what is left of the payment when it is `None` (REQ-032)."""
        remaining = payment.amount_cents - payment.refunded_cents
        amount = remaining if amount_cents is None else amount_cents
        if not 0 < amount <= remaining:
            raise ValueError(
                f"A refund of {amount} centavos is outside 1..{remaining}, "
                "what is left to refund"
            )
        refund_id = f"mock_ref_{uuid.uuid4().hex}"
        self._write(
            refund_id,
            {
                "id": refund_id,
                "payment_id": payment.pk,
                "provider_payment_id": payment.provider_payment_id,
                "amount_cents": amount,
            },
        )
        return RefundResult(refund_id=refund_id, amount_cents=amount)

    def _write(self, record_id: str, record: dict[str, Any]) -> None:
        """Write the record atomically: a temporary file in the same folder, then a rename."""
        folder = Path(settings.MOCK_STORE_DIR) / "payments"
        folder.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle)
            os.replace(temp_path, folder / f"{record_id}.json")
        except BaseException:
            os.unlink(temp_path)
            raise
