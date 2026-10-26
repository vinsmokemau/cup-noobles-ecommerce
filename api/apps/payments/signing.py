"""HMAC signing of payment notifications (SPEC.md 9.2, CR-13).

Header shape: `x-signature: ts=<unix>,v1=<hex>` plus `x-request-id`, modelled on Mercado Pago's
documented scheme. The signed manifest is `id:<resource_id>;request-id:<request_id>;ts:<ts>;`.
Phase 16 confirms the exact manifest against current Mercado Pago documentation.
"""

import hashlib
import hmac
import time
from collections.abc import Mapping


def _manifest(resource_id: str, request_id: str, ts: int) -> bytes:
    return f"id:{resource_id};request-id:{request_id};ts:{ts};".encode()


def _digest(secret: str, resource_id: str, request_id: str, ts: int) -> str:
    return hmac.new(
        secret.encode(), _manifest(resource_id, request_id, ts), hashlib.sha256
    ).hexdigest()


def sign(secret: str, *, resource_id: str, request_id: str, ts: int) -> str:
    """The `x-signature` header value for a notification."""
    return f"ts={ts},v1={_digest(secret, resource_id, request_id, ts)}"


def verify(
    secret: str, headers: Mapping[str, str], resource_id: str, *, max_age: int
) -> bool:
    """True only for a well-formed, fresh, correctly signed notification. Never raises on input."""
    lowered = {name.lower(): value for name, value in headers.items()}
    signature = lowered.get("x-signature")
    request_id = lowered.get("x-request-id")
    if not signature or not request_id:
        return False

    parts: dict[str, str] = {}
    for item in signature.split(","):
        key, separator, value = item.partition("=")
        if separator:
            parts[key.strip()] = value.strip()
    try:
        ts = int(parts["ts"])
        received = parts["v1"]
    except (KeyError, ValueError):
        return False

    if abs(time.time() - ts) > max_age:  # stale, or too far in the future
        return False
    expected = _digest(secret, resource_id, request_id, ts)
    return hmac.compare_digest(expected.encode(), received.encode())
