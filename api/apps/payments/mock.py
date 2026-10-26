"""The mock payment provider (SPEC.md §4.3, 9.9). `MOCK_STORE_DIR/payments/` holds its state.

State lives in JSON files, one per preference, payment, refund and queued notification, outside
the database on purpose: a real provider's state is outside our transactions, and a mock that
shared them would hide the bugs reconciliation exists to catch. Every write is atomic (temp file +
rename). Ids carry a `mock_` prefix so they are never mistaken for real ones.
"""

import fcntl
import json
import os
import re
import tempfile
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.orders.models import Order
from apps.payments import signing
from apps.payments.base import (
    CheckoutSession,
    NormalizedStatus,
    PaymentNotFound,
    ProviderPayment,
    RefundNotSupported,
    RefundResult,
    WebhookRef,
)
from apps.payments.models import Payment
from apps.payments.money import cents_to_pesos, pesos_to_cents

_PAYMENT_ID = re.compile(r"mock_pay_[0-9a-f]{32}")
_PREFERENCE_ID = re.compile(r"mock_pref_[0-9a-f]{32}")
_OXXO_REFUND_MESSAGE = "OXXO payments are refunded by hand, not by the provider"


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
                "order_number": order.number,
                "back_urls": self._back_urls(order),
                "total_cents": order.total_cents,
                "total": str(cents_to_pesos(order.total_cents)),
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

    def get_preference(self, preference_id: str) -> dict[str, Any] | None:
        """The stored preference, or `None`. For the simulator pages."""
        return self._read(preference_id, _PREFERENCE_ID)

    @staticmethod
    def _back_urls(order: Order) -> dict[str, str]:
        """Where the provider sends the browser after paying (SPEC.md 16.2: `/pedido/{id}/…`)."""
        base = f"{str(settings.SITE_URL).rstrip('/')}/pedido/{order.public_id}"
        return {
            "success": f"{base}/gracias",
            "pending": f"{base}/pendiente",
            "failure": f"{base}/error",
        }

    def fetch_payment(self, provider_payment_id: str) -> ProviderPayment:
        stored = self._read(provider_payment_id, _PAYMENT_ID)
        if stored is None:
            raise PaymentNotFound(provider_payment_id)
        return self._to_provider_payment(stored)

    def find_payments(self, external_reference: str) -> list[ProviderPayment]:
        found = []
        for path in self._folder().glob("mock_pay_*.json"):
            stored = json.loads(path.read_text(encoding="utf-8"))
            if stored["external_reference"] == external_reference:
                found.append(stored)
        found.sort(key=lambda stored: (stored["created_at"], stored["id"]))
        return [self._to_provider_payment(stored) for stored in found]

    def cancel_payment(self, provider_payment_id: str) -> None:
        """End the stored payment as `cancelled`; one already cancelled is left alone."""
        with self._locked():
            stored = self._read(provider_payment_id, _PAYMENT_ID)
            if stored is None:
                raise PaymentNotFound(provider_payment_id)
            if stored["status"] == NormalizedStatus.CANCELLED.value:
                return
            stored["status"] = NormalizedStatus.CANCELLED.value
            stored["status_detail"] = NormalizedStatus.CANCELLED.value
            self._write(provider_payment_id, stored)

    def verify_webhook(
        self, headers: Mapping[str, str], body: bytes
    ) -> WebhookRef | None:
        """The notification's ids when it is well formed and correctly signed, else `None`."""
        try:
            data = json.loads(body)
            ref = WebhookRef(
                topic=data["type"],
                notification_id=data["id"],
                resource_id=data["data"]["id"],
            )
        except (ValueError, KeyError, TypeError):
            return None
        if not all(
            isinstance(value, str) and value
            for value in (ref.topic, ref.notification_id, ref.resource_id)
        ):
            return None
        signed = signing.verify(
            settings.MOCK_PAYMENT_WEBHOOK_SECRET,
            headers,
            ref.resource_id,
            max_age=settings.WEBHOOK_MAX_AGE_SECONDS,
        )
        return ref if signed else None

    def refund(self, payment: Payment, amount_cents: int | None) -> RefundResult:
        """Refund `amount_cents`, or what is left of the payment when it is `None` (REQ-032).

        A payment that lives in the store also gets the refund appended, its status updated and a
        notification queued. One that does not (the Phase 8 callers) only gets the refund record.
        """
        if payment.method == "oxxo":
            raise RefundNotSupported(_OXXO_REFUND_MESSAGE)
        remaining = payment.amount_cents - payment.refunded_cents
        amount = remaining if amount_cents is None else amount_cents
        if not 0 < amount <= remaining:
            raise ValueError(
                f"A refund of {amount} centavos is outside 1..{remaining}, "
                "what is left to refund"
            )
        refund_id = f"mock_ref_{uuid.uuid4().hex}"
        provider_payment_id = payment.provider_payment_id
        if provider_payment_id and _PAYMENT_ID.fullmatch(provider_payment_id):
            with self._locked():
                stored = self._read(provider_payment_id, _PAYMENT_ID)
                if stored is not None:
                    if stored["method"] == "oxxo":
                        raise RefundNotSupported(_OXXO_REFUND_MESSAGE)
                    stored["refunds"].append(
                        {"id": refund_id, "amount": str(cents_to_pesos(amount))}
                    )
                    refunded = sum(
                        pesos_to_cents(refund["amount"]) for refund in stored["refunds"]
                    )
                    full = refunded == pesos_to_cents(stored["amount"])
                    stored["status"] = (
                        NormalizedStatus.REFUNDED
                        if full
                        else NormalizedStatus.PARTIALLY_REFUNDED
                    ).value
                    self._write(provider_payment_id, stored)
                    self.queue_notification(provider_payment_id)
        self._write(
            refund_id,
            {
                "id": refund_id,
                "payment_id": payment.pk,
                "provider_payment_id": provider_payment_id,
                "amount_cents": amount,
            },
        )
        return RefundResult(refund_id=refund_id, amount_cents=amount)

    def record_payment(
        self,
        preference_id: str,
        *,
        status: NormalizedStatus,
        method: str,
        amount_cents: int | None = None,
        installments: int | None = None,
        voucher_url: str | None = None,
        voucher_expires_at: datetime | None = None,
        status_detail: str = "",
    ) -> str:
        """Record what a customer did on the provider's page; returns the `mock_pay_…` id.

        The amount defaults to the preference's total. For the simulator and the dev commands.
        """
        preference = self._read(preference_id, _PREFERENCE_ID)
        if preference is None:
            raise PaymentNotFound(preference_id)
        payment_id = f"mock_pay_{uuid.uuid4().hex}"
        total = preference["total_cents"] if amount_cents is None else amount_cents
        self._write(
            payment_id,
            {
                "id": payment_id,
                "preference_id": preference_id,
                "external_reference": preference["external_reference"],
                "status": status.value,
                "status_detail": status_detail or status.value,
                "method": method,
                "amount": str(cents_to_pesos(total)),
                "refunds": [],
                "installments": installments,
                "voucher_url": voucher_url,
                "voucher_expires_at": (
                    voucher_expires_at.isoformat() if voucher_expires_at else None
                ),
                "created_at": timezone.now().isoformat(),
            },
        )
        return payment_id

    def update_payment(self, provider_payment_id: str, **fields: Any) -> None:
        """Change fields of a stored payment (for example `status`) under the store lock."""
        with self._locked():
            stored = self._read(provider_payment_id, _PAYMENT_ID)
            if stored is None:
                raise PaymentNotFound(provider_payment_id)
            stored.update(fields)
            self._write(provider_payment_id, stored)

    def queue_notification(self, provider_payment_id: str) -> str:
        """Queue a notification that carries ids only (9.A rule 2); returns its `mock_ntf_…` id."""
        notification_id = f"mock_ntf_{uuid.uuid4().hex}"
        self._write(
            notification_id,
            {
                "id": notification_id,
                "type": "payment",
                "data": {"id": provider_payment_id},
                "queued_at": timezone.now().isoformat(),
            },
        )
        return notification_id

    @staticmethod
    def _to_provider_payment(stored: dict[str, Any]) -> ProviderPayment:
        """Build the value through `pesos_to_cents`, so the conversion path matches production."""
        expires = stored["voucher_expires_at"]
        return ProviderPayment(
            provider_payment_id=stored["id"],
            external_reference=stored["external_reference"],
            status=NormalizedStatus(stored["status"]),
            status_detail=stored["status_detail"],
            method=stored["method"],
            amount_cents=pesos_to_cents(stored["amount"]),
            refunded_cents=sum(
                pesos_to_cents(refund["amount"]) for refund in stored["refunds"]
            ),
            installments=stored["installments"],
            voucher_url=stored["voucher_url"],
            voucher_expires_at=datetime.fromisoformat(expires) if expires else None,
            raw=stored,
        )

    @staticmethod
    def _folder() -> Path:
        return Path(settings.MOCK_STORE_DIR) / "payments"

    def _read(self, record_id: str, shape: re.Pattern[str]) -> dict[str, Any] | None:
        """The stored record, or `None`. An id outside `shape` never reaches the file system."""
        if not shape.fullmatch(record_id):
            return None
        try:
            return json.loads(
                (self._folder() / f"{record_id}.json").read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            return None

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Serialise read-modify-write across processes; a plain write is atomic and needs none."""
        lock_path = Path(settings.MOCK_STORE_DIR) / "payments.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def _write(self, record_id: str, record: dict[str, Any]) -> None:
        """Write the record atomically: a temporary file in the same folder, then a rename."""
        folder = self._folder()
        folder.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle)
            os.replace(temp_path, folder / f"{record_id}.json")
        except BaseException:
            os.unlink(temp_path)
            raise
