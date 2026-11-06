"""The order-status token (SPEC.md T13.9, G21, ADR-0065).

A signed value that names one order and carries its own expiry, the order's
`payment_deadline_at`. It rides in the provider's `back_urls` as `?t=<token>`, so the landing pages
can read the order without the guest lookup. Changing the lifetime touches `issue` only.
"""

from datetime import UTC, datetime

from django.core import signing

from apps.orders.models import Order

SALT = "orders.status-token"


def issue(order: Order) -> str:
    """A token for `order`, valid until its `payment_deadline_at`."""
    deadline = order.payment_deadline_at
    exp = int(deadline.timestamp()) if deadline else 0
    return signing.dumps({"o": str(order.public_id), "exp": exp}, salt=SALT)


def is_valid(token: str | None, public_id: str, now: datetime | None = None) -> bool:
    """True when `token` is untampered, names `public_id` and has not expired."""
    if not token:
        return False
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return False
    if not isinstance(data, dict) or data.get("o") != str(public_id):
        return False
    exp = data.get("exp")
    if not isinstance(exp, int):
        return False
    return (now or datetime.now(UTC)).timestamp() < exp
