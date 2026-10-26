"""Rebuild and re-send a stored notification (SPEC.md 9.12b).

Provider-agnostic: the request is rebuilt from the `webhook_event` row (its stored body and
resource id) and signed again with the active provider's secret, so Phase 16 uses it unchanged on
captured Mercado Pago notifications.
"""

import json
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connections, transaction

from apps.core import providers
from apps.payments import signing
from apps.payments.devtools.delivery import Transport
from apps.payments.models import WebhookEvent

# Provider code -> the setting holding its webhook secret. Phase 16 defines MP_WEBHOOK_SECRET.
SECRET_SETTINGS = {
    "mock": "MOCK_PAYMENT_WEBHOOK_SECRET",
    "mercadopago": "MP_WEBHOOK_SECRET",
}
STALE_MARGIN_SECONDS = 60
BARRIER_TIMEOUT_SECONDS = 30


def verified_event(event_id: int) -> WebhookEvent:
    """The stored row to replay: one that was verified, of the active provider."""
    event = WebhookEvent.objects.filter(pk=event_id).first()
    if event is None:
        raise CommandError(f"There is no webhook_event {event_id}")
    if not event.signature_ok or "ref" not in event.payload:
        raise CommandError(
            f"webhook_event {event_id} failed its signature check, so there is nothing to replay"
        )
    active = providers.payment_provider().code
    if event.provider != active:
        raise CommandError(
            f"webhook_event {event_id} is from {event.provider!r}, "
            f"but PAYMENT_PROVIDER is {active!r}"
        )
    return event


def _secret(provider_code: str) -> str:
    name = SECRET_SETTINGS.get(provider_code)
    secret = getattr(settings, name, "") if name else ""
    if not secret:
        raise CommandError(
            f"There is no webhook secret configured for {provider_code!r}"
        )
    return str(secret)


def build_request(
    event: WebhookEvent, *, ts: int | None = None, corrupt: bool = False
) -> tuple[bytes, dict[str, str]]:
    """The stored body and freshly signed headers.

    `ts` backdates the signature; `corrupt` breaks it.
    """
    body = json.dumps(event.payload["body"]).encode()
    request_id = uuid.uuid4().hex
    signature = signing.sign(
        _secret(event.provider),
        resource_id=event.payload["ref"]["resource_id"],
        request_id=request_id,
        ts=int(time.time()) if ts is None else ts,
    )
    if corrupt:
        signature = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    return body, {"x-request-id": request_id, "x-signature": signature}


def stale_ts() -> int:
    return int(time.time()) - settings.WEBHOOK_MAX_AGE_SECONDS - STALE_MARGIN_SECONDS


def send_many(
    make_transport: Callable[[], Transport],
    event: WebhookEvent,
    count: int,
    *,
    concurrent: bool,
) -> list[int]:
    """`count` deliveries of one notification, each signed on its own; simultaneous if `concurrent`.

    The row stored under the notification id is removed first, so the deliveries race to insert it
    as a provider's first delivery and its retries would. Dev only.
    """
    with transaction.atomic():
        WebhookEvent.objects.filter(
            provider=event.provider, topic=event.topic, external_id=event.external_id
        ).delete()
    if not concurrent:
        return [make_transport()(*build_request(event)) for _ in range(count)]

    barrier = Barrier(count, timeout=BARRIER_TIMEOUT_SECONDS)

    def deliver() -> int:
        try:
            request = build_request(event)
            barrier.wait()
            return make_transport()(*request)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = [pool.submit(deliver) for _ in range(count)]
        return [future.result() for future in futures]
