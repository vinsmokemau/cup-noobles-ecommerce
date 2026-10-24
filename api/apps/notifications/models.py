"""Transactional email outbox (§4.4, `spec/schema.sql` TRANSACTIONAL EMAIL OUTBOX).

Retry without a broker: a row is written in the same transaction as the event that causes it.
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import json_default
from apps.core.db import NOW
from apps.core.fields import CIEmailField


class EmailOutbox(models.Model):
    to_email = CIEmailField()
    template = models.TextField()
    context = models.JSONField(default=dict, db_default=json_default({}))
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=False,
    )
    dedupe_key = models.TextField(null=True, blank=True)
    attempts = models.IntegerField(default=0, db_default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(default="", db_default="", blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "email_outbox"
        constraints = [
            models.UniqueConstraint(
                fields=["dedupe_key"],
                condition=Q(dedupe_key__isnull=False),
                name="email_outbox_dedupe_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["created_at"],
                condition=Q(sent_at__isnull=True),
                name="email_outbox_pending_idx",
            )
        ]
