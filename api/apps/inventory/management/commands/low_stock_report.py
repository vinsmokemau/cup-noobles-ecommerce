"""Email the owner the variants at or below their safety stock (SPEC.md §4.8, G2, G38).

A stock item is listed when `available <= safety_stock`, with `available` as CR-04 defines it
(`on_hand - reserved - safety_stock`, never negative). The email is queued in the outbox, not
sent (Phase 11), addressed to `OWNER_ALERT_EMAIL`. Nothing is queued when no item qualifies.
Running it twice the same day queues one email: the outbox row's dedupe key carries the date.
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.inventory.models import StockItem
from apps.notifications.outbox import enqueue_email

TEMPLATE = "low_stock_report"


def low_stock_items() -> list[dict[str, Any]]:
    """One entry per stock item with `available <= safety_stock`, by SKU."""
    rows = (
        StockItem.objects.select_related("variant", "location")
        .annotate(net=F("on_hand") - F("reserved") - F("safety_stock"))
        .filter(net__lte=F("safety_stock"))
        .order_by("variant__sku", "location__code")
    )
    return [
        {
            "sku": str(row.variant.sku),
            "location": str(row.location.code),
            "available": max(0, row.net),
            "safety_stock": row.safety_stock,
        }
        for row in rows
    ]


class Command(BaseCommand):
    help = "Queue an email to the owner listing variants at or below safety stock (SPEC.md §4.8)."

    def handle(self, *args: Any, **options: Any) -> None:
        items = low_stock_items()
        if not items:
            self.stdout.write("low_stock_report: nothing at or below safety stock")
            return
        with transaction.atomic():
            enqueue_email(
                settings.OWNER_ALERT_EMAIL,
                TEMPLATE,
                {"items": items},
                dedupe_key=f"{TEMPLATE}:{timezone.localdate().isoformat()}",
            )
        self.stdout.write(f"low_stock_report: queued {len(items)} item(s)")
