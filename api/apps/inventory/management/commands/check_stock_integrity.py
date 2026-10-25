"""Assert the stock invariants hold for every stock item (SPEC.md §4.8, REQ-011, G24).

Two checks per `stock_item`: the sum of its ledger deltas equals `on_hand` (CR-05), and
`reserved` equals the units in its `held` stock reservations (CR-06). Read-only: it repairs
nothing. It names each failing stock item and exits non-zero, so cron reports the failure.

G24 (ADR-0034): the command lives in Phase 4; Phase 21 only schedules it.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import IntegerField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.inventory.models import InventoryReservation, StockItem, StockLedger


def _total(queryset, field: str, link: str):
    """A correlated `SUM(field)` of `queryset` per stock item, 0 when it has no rows."""
    return Coalesce(
        Subquery(
            queryset.filter(**{link: OuterRef("pk")})
            .order_by()
            .values(link)
            .annotate(total=Sum(field))
            .values("total"),
            output_field=IntegerField(),
        ),
        0,
    )


def find_violations() -> list[str]:
    """One line per broken invariant, naming the stock item."""
    held = InventoryReservation.objects.filter(
        kind=InventoryReservation.Kind.STOCK, state=InventoryReservation.State.HELD
    ).annotate(
        item_id=Subquery(
            StockItem.objects.filter(
                variant_id=OuterRef("variant_id"), location_id=OuterRef("location_id")
            ).values("pk")[:1]
        )
    )
    items = (
        StockItem.objects.select_related("variant", "location")
        .annotate(
            ledger_sum=_total(StockLedger.objects.all(), "delta", "stock_item"),
            held_sum=_total(held, "quantity", "item_id"),
        )
        .order_by("pk")
    )
    problems = []
    for item in items:
        name = f"stock_item {item.pk} ({item.variant.sku} @ {item.location.code})"
        if item.ledger_sum != item.on_hand:
            problems.append(
                f"{name}: ledger sums to {item.ledger_sum} but on_hand is {item.on_hand}"
            )
        if item.held_sum != item.reserved:
            problems.append(
                f"{name}: held reservations total {item.held_sum} but reserved is {item.reserved}"
            )
    return problems


class Command(BaseCommand):
    help = "Check that every stock item's ledger and holds match its counters (SPEC.md §4.8)."

    def handle(self, *args: Any, **options: Any) -> None:
        problems = find_violations()
        if problems:
            raise CommandError("check_stock_integrity failed:\n" + "\n".join(problems))
        self.stdout.write("check_stock_integrity: ok")
