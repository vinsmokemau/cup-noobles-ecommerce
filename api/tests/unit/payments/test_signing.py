"""HMAC signing helpers (SPEC.md 9.2, CR-13)."""

import hmac

import time_machine

from apps.payments import signing
from apps.payments.signing import sign, verify

SECRET = "test-only-webhook-secret"
NOW = 1_700_000_000


def _headers(resource_id="123", request_id="req-1", ts=NOW, secret=SECRET):
    return {
        "x-signature": sign(
            secret, resource_id=resource_id, request_id=request_id, ts=ts
        ),
        "x-request-id": request_id,
    }


@time_machine.travel(NOW, tick=False)
def test_p9_v20_sign_verify():
    headers = _headers()
    assert headers["x-signature"].startswith(f"ts={NOW},v1=")
    assert verify(SECRET, headers, "123", max_age=300)

    # case-insensitive header names, as an HTTP stack may deliver them
    assert verify(
        SECRET,
        {"X-Signature": headers["x-signature"], "X-Request-Id": "req-1"},
        "123",
        max_age=300,
    )

    # a one-byte change anywhere fails
    assert not verify(SECRET, headers, "124", max_age=300)
    assert not verify(SECRET, {**headers, "x-request-id": "req-2"}, "123", max_age=300)
    assert not verify("other-secret", headers, "123", max_age=300)
    signature = headers["x-signature"]
    flipped = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    assert not verify(SECRET, {**headers, "x-signature": flipped}, "123", max_age=300)
    shifted = signature.replace(f"ts={NOW}", f"ts={NOW + 1}")
    assert not verify(SECRET, {**headers, "x-signature": shifted}, "123", max_age=300)


@time_machine.travel(NOW, tick=False)
def test_p9_v20_comparison_is_constant_time(monkeypatch):
    calls = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(signing.hmac, "compare_digest", spy)
    assert verify(SECRET, _headers(), "123", max_age=300)
    assert len(calls) == 1


def test_p9_v20_stale_and_future_timestamps_fail():
    headers = _headers(ts=NOW)
    with time_machine.travel(NOW + 300, tick=False):
        assert verify(SECRET, headers, "123", max_age=300)
    with time_machine.travel(NOW + 301, tick=False):
        assert not verify(SECRET, headers, "123", max_age=300)
    with time_machine.travel(NOW - 301, tick=False):
        assert not verify(SECRET, headers, "123", max_age=300)


@time_machine.travel(NOW, tick=False)
def test_p9_v20_malformed_headers_fail_without_raising():
    good = _headers()
    assert not verify(SECRET, {}, "123", max_age=300)
    assert not verify(SECRET, {"x-request-id": "req-1"}, "123", max_age=300)
    assert not verify(SECRET, {"x-signature": good["x-signature"]}, "123", max_age=300)
    for bad in ("", "garbage", "ts=abc,v1=ff", f"ts={NOW}", "v1=ff", f"ts={NOW},v1="):
        assert not verify(
            SECRET, {"x-signature": bad, "x-request-id": "req-1"}, "123", max_age=300
        )


def test_p9_v20_sign_is_deterministic():
    assert sign(SECRET, resource_id="1", request_id="r", ts=NOW) == sign(
        SECRET, resource_id="1", request_id="r", ts=NOW
    )
