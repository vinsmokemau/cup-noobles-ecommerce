"""Order numbers: `CN-{YYYY}-{seq:06d}` (T8.3, G5, ADR-0030).

The year is taken in the store timezone. Each year has its own Postgres sequence,
`order_number_seq_<year>`, created on first use; the sequences are not part of
`spec/schema.sql`. The number is never derived from the primary key. A sequence skips
values when a transaction rolls back, so numbers are unique and increasing, not gapless.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import connection, transaction
from django.utils import timezone

STORE_TIMEZONE = ZoneInfo("America/Mexico_City")


def next_order_number(now: datetime | None = None) -> str:
    """Return the next order number for the year of `now` in the store timezone."""
    year = (now or timezone.now()).astimezone(STORE_TIMEZONE).year
    # `year` is an int, so the name is safe to inline in the SQL below.
    sequence = f"order_number_seq_{year}"
    with transaction.atomic(), connection.cursor() as cursor:
        # CREATE SEQUENCE IF NOT EXISTS can still fail when two sessions create the same
        # sequence at once; the transaction-scoped lock serialises that first use.
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [sequence])
        cursor.execute(f'CREATE SEQUENCE IF NOT EXISTS "{sequence}"')
        cursor.execute("SELECT nextval(%s)", [sequence])
        (value,) = cursor.fetchone()
    return f"CN-{year}-{value:06d}"
