"""Deliver the mock provider's queued notifications to the webhook (SPEC.md 9.11).

The simulator never calls the webhook itself: it queues a notification of ids only. This module
signs each one at send time, so its timestamp is fresh, and POSTs it to the same endpoint
production traffic reaches. The transport is a parameter: the command sends real HTTP through
Caddy, the tests send through the Django test client.
"""

import json
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone

from apps.core import providers
from apps.payments import signing

WEBHOOK_PATH = "/api/webhooks/payments/mock/"


def webhook_path(provider_code: str) -> str:
    """The endpoint a provider's notifications reach (9.B)."""
    return f"/api/webhooks/payments/{provider_code}/"


# (body, headers) -> HTTP status; a connection that fails raises OSError.
Transport = Callable[[bytes, dict[str, str]], int]


@dataclass(frozen=True)
class DeliveryResult:
    delivered: int = 0
    failed: int = 0
    waiting: int = 0


def http_transport(base_url: str, path: str = WEBHOOK_PATH) -> Transport:
    """POST to `base_url` + `path` (the mock webhook by default), with the `Host` of `SITE_URL`.

    Inside compose the proxy is reached as `http://proxy:8080`, a host Django does not allow, so
    the `Host` header names the public one, as the browser's request does.
    """
    host = urlsplit(str(settings.SITE_URL)).netloc

    def send(body: bytes, headers: dict[str, str]) -> int:
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=body,
            headers={**headers, "Content-Type": "application/json", "Host": host},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return int(response.status)
        except urllib.error.HTTPError as error:
            return error.code

    return send


def _signed(notification: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    """The body (ids only) and headers of `notification`, signed now."""
    body = json.dumps(
        {
            "id": notification["id"],
            "type": notification["type"],
            "data": notification["data"],
        }
    ).encode()
    request_id = uuid.uuid4().hex
    signature = signing.sign(
        settings.MOCK_PAYMENT_WEBHOOK_SECRET,
        resource_id=notification["data"]["id"],
        request_id=request_id,
        ts=int(time.time()),
    )
    return body, {"x-request-id": request_id, "x-signature": signature}


def deliver(
    transport: Transport, *, honour_delay: bool, now: datetime | None = None
) -> DeliveryResult:
    """Send the queued notifications, oldest first.

    A notification leaves the queue when the endpoint answers 2xx; any other answer, or a
    connection that fails, leaves it for the next pass. With `honour_delay`, one queued less than
    `MOCK_WEBHOOK_DELAY_SECONDS` ago waits.
    """
    provider: Any = providers.payment_provider()
    if provider.code != "mock":
        raise CommandError(
            "There is no mock queue to deliver: PAYMENT_PROVIDER is not mock"
        )
    moment = now or timezone.now()
    delivered = failed = waiting = 0
    for notification in provider.queued_notifications():
        age = (
            moment - datetime.fromisoformat(notification["queued_at"])
        ).total_seconds()
        if honour_delay and age < settings.MOCK_WEBHOOK_DELAY_SECONDS:
            waiting += 1
            continue
        body, headers = _signed(notification)
        try:
            status = transport(body, headers)
        except OSError:
            failed += 1
            continue
        if 200 <= status < 300:
            provider.discard_notification(notification["id"])
            delivered += 1
        else:
            failed += 1
    return DeliveryResult(delivered=delivered, failed=failed, waiting=waiting)
