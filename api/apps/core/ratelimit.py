"""Rate-limit helpers (django-ratelimit, SPEC.md T6.7b)."""

import ipaddress

from django.http import HttpRequest

UNKNOWN_CLIENT = "0.0.0.0"  # one shared bucket for a request with no usable address


def _valid(address: str) -> bool:
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return False
    return True


def client_ip(request: HttpRequest) -> str:
    """The client address as our own proxy saw it.

    Caddy, the single proxy in front of the API (§4.1), appends the address it received the
    connection from as the last `X-Forwarded-For` entry, so that entry cannot be forged by the
    caller. Without the header (direct access, tests) the socket address is used. A value that is
    not an IP address never reaches the limiter, and a request with none shares one bucket.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").rsplit(",", 1)[-1].strip()
    for candidate in (forwarded, request.META.get("REMOTE_ADDR", "")):
        if _valid(candidate):
            return candidate
    return UNKNOWN_CLIENT
