"""Delete the carts that were never converted and sat untouched for 60 days (SPEC.md §4.8, P7-V15).

A cart is stale when `updated_at < now() - 60 days`: at exactly 60 days it is kept. Every cart
write bumps `updated_at`. A converted cart (`converted_order_id` set) is never deleted, and its
lines go with a purged cart through `ON DELETE CASCADE`. The delete is one statement, so running
the command twice, or two copies at once, purges each cart once.
"""

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.carts.models import Cart

STALE_AFTER = timedelta(days=60)


class Command(BaseCommand):
    help = "Delete unconverted carts untouched for 60 days (SPEC.md §4.8)."

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone.now() - STALE_AFTER
        purged, _ = Cart.objects.filter(
            converted_order__isnull=True, updated_at__lt=cutoff
        ).delete()
        self.stdout.write(f"purge_stale_carts: {purged} object(s) purged")
