"""Dev tooling for the mock payment provider (SPEC.md 9.11, 9.12a). Refuses to run in production."""

import json
import time
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from apps.core import providers
from apps.inventory.models import InventoryReservation
from apps.orders.models import Order
from apps.payments.base import NormalizedStatus, PaymentNotFound
from apps.payments.devtools import delivery, outcomes

POLL_SECONDS = 0.5
# `drop --outcome` -> the simulator outcome it records.
DROP_OUTCOMES = {"approve": "card", "reject": "reject", "pending": "oxxo"}


def _mock() -> Any:
    """The mock provider, which has the dev methods the `PaymentProvider` protocol does not."""
    return providers.payment_provider()


class Command(BaseCommand):
    help = "Drive the mock payment provider (SPEC.md 9.11, 9.12a)."

    def add_arguments(self, parser: CommandParser) -> None:
        actions = parser.add_subparsers(dest="action", required=True)
        deliver = actions.add_parser(
            "deliver", help="Send the queued notifications to the webhook."
        )
        mode = deliver.add_mutually_exclusive_group()
        mode.add_argument(
            "--once",
            action="store_true",
            help="Send everything queued now, ignoring the delay, then exit (the default).",
        )
        mode.add_argument(
            "--loop",
            action="store_true",
            help="Keep sending, each notification after MOCK_WEBHOOK_DELAY_SECONDS.",
        )
        deliver.add_argument(
            "--base-url",
            default=None,
            help="Where to POST; defaults to SITE_URL. In compose: http://proxy:8080.",
        )

        approve = actions.add_parser(
            "approve", help="Approve an order's payment, as the button does."
        )
        approve.add_argument("order", help="Order number, for example CN-2026-000123.")
        approve.add_argument("--installments", type=int, default=None)
        approve.add_argument(
            "--amount-cents",
            type=int,
            default=None,
            help="Record a different amount, to exercise the amount guard.",
        )
        actions.add_parser("reject", help="Reject an order's payment.").add_argument(
            "order"
        )
        for name, help_text in (
            ("pay-voucher", "Complete an OXXO or SPEI payment."),
            ("expire-voucher", "Lapse an OXXO or SPEI payment."),
            ("chargeback", "Charge a payment back; the webhook raises an alert."),
        ):
            actions.add_parser(name, help=help_text).add_argument(
                "payment", help="Mock payment id, mock_pay_…"
            )
        drop = actions.add_parser(
            "drop",
            help="Record an outcome without a notification; only reconciliation finds it.",
        )
        drop.add_argument("order")
        drop.add_argument("--outcome", required=True, choices=sorted(DROP_OUTCOMES))
        actions.add_parser(
            "expire-order",
            help="Move the order's deadline and holds into the past, then expire them.",
        ).add_argument("order")
        listing = actions.add_parser("list", help="Show the mock store.")
        listing.add_argument("--order", default=None, help="Only this order number.")
        actions.add_parser("reset", help="Clear the mock store.")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ENABLED:
            raise CommandError("mock_payments runs only where DEV_TOOLS_ENABLED is on")
        if _mock().code != "mock":
            raise CommandError("mock_payments needs PAYMENT_PROVIDER=mock")
        action = options["action"]
        if action == "deliver":
            self._deliver(
                options["base_url"] or str(settings.SITE_URL), options["loop"]
            )
        elif action == "approve":
            self._approve(options)
        elif action == "reject":
            self._record(options["order"], "reject")
        elif action == "drop":
            self._record(
                options["order"], DROP_OUTCOMES[options["outcome"]], notify=False
            )
        elif action in ("pay-voucher", "expire-voucher"):
            self._voucher(options["payment"], action)
        elif action == "chargeback":
            self._chargeback(options["payment"])
        elif action == "expire-order":
            self._expire_order(options["order"])
        elif action == "list":
            self._list(options["order"])
        else:
            removed = _mock().reset()
            self.stdout.write(f"mock_payments reset: {removed} records removed")

    @staticmethod
    def _order(number: str) -> Order:
        try:
            return Order.objects.get(number=number)
        except Order.DoesNotExist:
            raise CommandError(f"There is no order {number}") from None

    def _preference(self, number: str) -> dict[str, Any]:
        """The order's latest checkout: the one the customer would be looking at."""
        order = self._order(number)
        found = _mock().find_preferences(str(order.public_id))
        if not found:
            raise CommandError(f"Order {number} has no checkout in the mock store")
        return found[-1]

    def _approve(self, options: dict[str, Any]) -> None:
        installments = options["installments"]
        if (
            installments is not None
            and installments not in settings.PAYMENT_INSTALLMENT_OPTIONS
        ):
            raise CommandError(
                f"Installments must be one of {list(settings.PAYMENT_INSTALLMENT_OPTIONS)}"
            )
        self._record(
            options["order"],
            "installments" if installments else "card",
            installments=installments,
            amount_cents=options["amount_cents"],
        )

    def _record(
        self,
        number: str,
        outcome: str,
        *,
        notify: bool = True,
        installments: int | None = None,
        amount_cents: int | None = None,
    ) -> None:
        payment_id = outcomes.record_outcome(
            _mock(),
            self._preference(number),
            outcome,
            installments=installments,
            amount_cents=amount_cents,
            notify=notify,
        )
        queued = "notification queued" if notify else "no notification queued"
        self.stdout.write(f"mock_payments: {payment_id} for {number}, {queued}")

    def _voucher(self, payment_id: str, action: str) -> None:
        provider = _mock()
        try:
            payment = provider.fetch_payment(payment_id)
        except PaymentNotFound:
            raise CommandError(f"There is no mock payment {payment_id}") from None
        if payment.method not in ("oxxo", "spei"):
            raise CommandError(f"{payment_id} is not an OXXO or SPEI payment")
        outcomes.settle_voucher(
            provider, payment_id, "received" if action == "pay-voucher" else "expired"
        )
        self.stdout.write(f"mock_payments: {action} {payment_id}")

    def _chargeback(self, payment_id: str) -> None:
        provider = _mock()
        try:
            provider.update_payment(
                payment_id,
                status=NormalizedStatus.CHARGED_BACK.value,
                status_detail="charged_back",
            )
        except PaymentNotFound:
            raise CommandError(f"There is no mock payment {payment_id}") from None
        provider.queue_notification(payment_id)
        self.stdout.write(
            f"mock_payments: chargeback {payment_id}, notification queued"
        )

    def _expire_order(self, number: str) -> None:
        order = self._order(number)
        past = timezone.now() - timedelta(minutes=1)
        Order.objects.filter(pk=order.pk).update(payment_deadline_at=past)
        InventoryReservation.objects.filter(
            order=order,
            kind=InventoryReservation.Kind.STOCK,
            state=InventoryReservation.State.HELD,
        ).update(expires_at=past)
        call_command("expire_reservations", stdout=self.stdout)

    def _list(self, number: str | None) -> None:
        reference = str(self._order(number).public_id) if number else None
        records = _mock().list_records(reference)
        self.stdout.write(json.dumps(records, indent=2, default=str))

    def _deliver(self, base_url: str, loop: bool) -> None:
        transport = delivery.http_transport(base_url)
        if not loop:
            result = delivery.deliver(transport, honour_delay=False)
            self._report(result)
            return
        self.stdout.write(
            f"mock_payments deliver: watching the queue, posting to {base_url}"
        )
        while True:
            result = delivery.deliver(transport, honour_delay=True)
            if result.delivered or result.failed:
                self._report(result)
            time.sleep(POLL_SECONDS)

    def _report(self, result: delivery.DeliveryResult) -> None:
        self.stdout.write(
            f"mock_payments deliver: {result.delivered} delivered, "
            f"{result.failed} failed, {result.waiting} waiting"
        )
