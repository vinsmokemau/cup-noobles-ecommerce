"""The write half of the email outbox (SPEC.md §4.4, G2).

`enqueue_email()` inserts an `email_outbox` row in the caller's transaction, so the email exists
exactly when the change that caused it commits. It never sends or renders anything: `send_outbox`
does that from Phase 11 (T11.1).
"""

from typing import Any

from django.db import IntegrityError, transaction

from apps.notifications.models import EmailOutbox
from apps.orders.models import Order


def enqueue_email(
    to_email: str,
    template: str,
    context: dict[str, Any] | None = None,
    *,
    order: Order | None = None,
    dedupe_key: str | None = None,
) -> EmailOutbox:
    """Queue one email. `context` must be JSON-serialisable.

    With a `dedupe_key`, a second call with the same key returns the first row and writes
    nothing (`email_outbox_dedupe_uq`). The insert runs in a savepoint, so the conflict leaves
    the caller's transaction usable.
    """
    try:
        with transaction.atomic():
            return EmailOutbox.objects.create(
                to_email=to_email,
                template=template,
                context=context or {},
                order=order,
                dedupe_key=dedupe_key,
            )
    except IntegrityError:
        if dedupe_key is None:
            raise
        return EmailOutbox.objects.get(dedupe_key=dedupe_key)
