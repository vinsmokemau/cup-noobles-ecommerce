"""The simulator end to end: every button, then delivery through the webhook (SPEC.md 9.10, 9.11).

The buttons record an outcome and queue a notification; `mock_payments deliver --once` signs it and
POSTs it to the endpoint. The transport here is the Django test client, the in-process stand-in for
the HTTP request the `mock-webhooks` service makes through Caddy.
"""

import json
from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.core import providers
from apps.payments.devtools import delivery
from apps.payments.models import Payment, WebhookEvent
from tests.factories.orders import order_in_state

CHECKOUT = "/dev/payments/checkout/{}/{}/"
VOUCHER = "/dev/payments/voucher/{}/{}/"


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def order(db):
    return order_in_state("pending_payment")


@pytest.fixture
def preference_id(order):
    return providers.payment_provider().create_checkout(order).preference_id


@pytest.fixture
def in_process(monkeypatch, api_client):
    """Send notifications through the test client, and keep what the endpoint answered."""
    answers: list[int] = []

    def transport_for(base_url):
        def send(body, headers):
            response = api_client.post(
                delivery.WEBHOOK_PATH,
                data=body,
                content_type="application/json",
                headers=headers,
            )
            answers.append(response.status_code)
            return response.status_code

        return send

    monkeypatch.setattr(delivery, "http_transport", transport_for)
    return answers


def deliver_once() -> str:
    out = StringIO()
    call_command("mock_payments", "deliver", "--once", stdout=out)
    return out.getvalue()


def queued(settings) -> list[Path]:
    return sorted((Path(settings.MOCK_STORE_DIR) / "payments").glob("mock_ntf_*.json"))


def events(order) -> list[str]:
    return list(order.events.order_by("pk").values_list("event", flat=True))


def press_checkout(client, preference_id, outcome, **form):
    return client.post(CHECKOUT.format(preference_id, outcome), form)


# button -> (outcome path, form, order state, payment status, method, redirect)
CHECKOUT_BUTTONS = {
    "card": ("card", {}, "paid", "approved", "credit_card", "gracias"),
    "installments": (
        "installments",
        {"installments": 6},
        "paid",
        "approved",
        "credit_card",
        "gracias",
    ),
    "oxxo": ("oxxo", {}, "pending_payment", "pending", "oxxo", "pendiente"),
    "spei": ("spei", {}, "pending_payment", "pending", "spei", "pendiente"),
    "reject": ("reject", {}, "pending_payment", "rejected", "credit_card", "error"),
}


@pytest.mark.parametrize(
    "button",
    [*CHECKOUT_BUTTONS, "expire", "voucher_received", "voucher_expired"],
)
def test_p9_v02_each_button_outcome(
    button, client, settings, order, preference_id, in_process
):
    expected_events = None  # None: only the last event is checked
    if button in CHECKOUT_BUTTONS:
        outcome, form, state, status, method, back = CHECKOUT_BUTTONS[button]
        response = press_checkout(client, preference_id, outcome, **form)
        assert response["Location"].endswith(f"/pedido/{order.public_id}/{back}")
        assert len(queued(settings)) == 1
        deliver_once()
        payment = Payment.objects.get()
        assert (payment.status, payment.method) == (status, method)
        if button == "installments":
            assert payment.installments == 6
        if state == "paid":
            expected_events = ["payment_approved"]
    elif button == "expire":
        response = press_checkout(client, preference_id, "expire")
        assert response["Location"].endswith(f"/pedido/{order.public_id}/error")
        assert queued(settings) == []  # nothing happened, so nothing is sent
        deliver_once()
        state, expected_events = "pending_payment", []
        assert not Payment.objects.exists()
        assert not WebhookEvent.objects.exists()
    else:
        press_checkout(client, preference_id, "oxxo")
        deliver_once()
        payment = Payment.objects.get()
        assert payment.status == "pending"
        action = "received" if button == "voucher_received" else "expired"
        response = client.post(VOUCHER.format(payment.provider_payment_id, action))
        assert response.status_code == 302
        assert len(queued(settings)) == 1
        deliver_once()
        payment.refresh_from_db()
        if action == "received":
            assert payment.status == "approved"
            state = "paid"
        else:
            assert payment.status == "cancelled"
            state = "pending_payment"

    order.refresh_from_db()
    assert order.state == state
    if expected_events is not None:
        assert events(order) == expected_events
    elif state == "paid":
        assert events(order)[-1] == "payment_approved"
    else:
        assert "payment_approved" not in events(order)
    assert queued(settings) == []
    assert set(in_process) <= {200}


def test_deliver_once_sends_each_notification_signed_and_with_ids_only(
    client, settings, order, preference_id, monkeypatch
):
    sent = []

    def capture(base_url):
        def send(body, headers):
            sent.append((json.loads(body), headers))
            return 200

        return send

    monkeypatch.setattr(delivery, "http_transport", capture)
    press_checkout(client, preference_id, "card")
    notification = json.loads(queued(settings)[0].read_text(encoding="utf-8"))

    deliver_once()

    ((body, headers),) = sent
    assert body == {
        "id": notification["id"],
        "type": "payment",
        "data": {"id": notification["data"]["id"]},
    }
    assert set(headers) == {"x-request-id", "x-signature"}
    assert queued(settings) == []


def test_a_notification_the_endpoint_refuses_stays_queued(
    client, settings, order, preference_id, monkeypatch
):
    monkeypatch.setattr(delivery, "http_transport", lambda base_url: lambda b, h: 503)
    press_checkout(client, preference_id, "card")

    out = deliver_once()

    assert "0 delivered, 1 failed" in out
    assert len(queued(settings)) == 1


def test_a_connection_that_fails_leaves_the_notification_queued(
    client, settings, order, preference_id, monkeypatch
):
    def refuse(body, headers):
        raise ConnectionRefusedError

    monkeypatch.setattr(delivery, "http_transport", lambda base_url: refuse)
    press_checkout(client, preference_id, "card")

    out = deliver_once()

    assert "0 delivered, 1 failed" in out
    assert len(queued(settings)) == 1


def test_the_loop_waits_out_the_delay_and_once_ignores_it(
    client, settings, order, preference_id
):
    settings.MOCK_WEBHOOK_DELAY_SECONDS = 2
    press_checkout(client, preference_id, "card")
    sent = []

    def send(body, headers):
        sent.append(body)
        return 200

    now = timezone.now()
    early = delivery.deliver(send, honour_delay=True, now=now + timedelta(seconds=1))
    on_time = delivery.deliver(send, honour_delay=True, now=now + timedelta(seconds=3))

    assert (early.delivered, early.waiting) == (0, 1)
    assert (on_time.delivered, on_time.waiting) == (1, 0)
    assert len(sent) == 1

    press_checkout(client, preference_id, "reject")
    immediate = delivery.deliver(send, honour_delay=False)
    assert immediate.delivered == 1


def test_http_transport_posts_to_the_proxy_with_the_public_host(monkeypatch, settings):
    settings.SITE_URL = "http://localhost:8080"
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["host"] = request.get_header("Host")
        captured["method"] = request.get_method()
        return Response()

    monkeypatch.setattr(delivery.urllib.request, "urlopen", fake_urlopen)

    status = delivery.http_transport("http://proxy:8080/")(b"{}", {"x-request-id": "r"})

    assert status == 200
    assert captured == {
        "url": "http://proxy:8080/api/webhooks/payments/mock/",
        "host": "localhost:8080",
        "method": "POST",
    }


def test_the_command_refuses_to_run_without_dev_tools(settings, db):
    settings.DEV_TOOLS_ENABLED = False

    with pytest.raises(CommandError, match="DEV_TOOLS_ENABLED"):
        call_command("mock_payments", "deliver", "--once")
