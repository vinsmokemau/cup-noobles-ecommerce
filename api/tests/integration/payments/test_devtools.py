"""The `webhooks` dev commands and the dev tools' absence in production (SPEC.md 9.12b)."""

import importlib
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import clear_url_caches
from rest_framework.test import APIClient

from apps.payments.devtools import delivery
from apps.payments.models import WebhookEvent
from tests.factories.orders import order_in_state
from tests.factories.payments import WebhookEventFactory, mock_payment_for

COMMANDS = (
    ("replay",),
    ("tamper",),
    ("stale",),
    ("duplicate", "--count", "2"),
)


def run(*args) -> str:
    out = StringIO()
    call_command("webhooks", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def in_process(monkeypatch):
    """Send through the Django test client, a new one per delivery, instead of over HTTP."""

    def transport_for(base_url, path=delivery.WEBHOOK_PATH):
        def send(body, headers):
            return (
                APIClient()
                .post(path, data=body, content_type="application/json", headers=headers)
                .status_code
            )

        return send

    monkeypatch.setattr(delivery, "http_transport", transport_for)


@pytest.fixture
def stored(db, in_process):
    """An approved mock payment and its notification, stored and not yet processed."""
    order = order_in_state("pending_payment")
    payment_id = mock_payment_for(order, status="approved")
    event = WebhookEventFactory(
        provider="mock",
        external_id="mock_ntf_replay",
        payload={
            "ref": {
                "topic": "payment",
                "notification_id": "mock_ntf_replay",
                "resource_id": payment_id,
            },
            "body": {
                "id": "mock_ntf_replay",
                "type": "payment",
                "data": {"id": payment_id},
            },
        },
    )
    return order, event


@pytest.mark.parametrize("args", COMMANDS)
def test_p9_v03_devtools_absent_in_prod(args, client, settings, stored):
    import config.urls

    _, event = stored
    # prod.py forces DEV_TOOLS_ENABLED to False whatever the environment says.
    settings.DEV_TOOLS_ENABLED = False
    clear_url_caches()
    importlib.reload(config.urls)
    try:
        page = client.get("/dev/payments/voucher/mock_pay_x/")
        with pytest.raises(CommandError, match="DEV_TOOLS_ENABLED"):
            call_command("mock_payments", "list")
        with pytest.raises(CommandError, match="DEV_TOOLS_ENABLED"):
            call_command("webhooks", args[0], event.pk, *args[1:])
    finally:
        settings.DEV_TOOLS_ENABLED = True
        clear_url_caches()
        importlib.reload(config.urls)

    assert page.status_code == 404


def test_replay_of_a_processed_notification_is_a_no_op(stored):
    order, event = stored
    assert "200" in run("duplicate", str(event.pk), "--count", "1")
    order.refresh_from_db()
    assert order.state == "paid"
    stored_event = WebhookEvent.objects.get(external_id="mock_ntf_replay")

    output = run("replay", str(stored_event.pk))

    assert "200 (expected 200)" in output
    order.refresh_from_db()
    assert order.state == "paid"
    assert order.events.filter(event="payment_approved").count() == 1
    assert WebhookEvent.objects.filter(external_id="mock_ntf_replay").count() == 1
    assert (
        WebhookEvent.objects.get(pk=stored_event.pk).attempts == stored_event.attempts
    )


def test_tamper_is_refused_and_recorded_unverified(stored):
    order, event = stored

    output = run("tamper", str(event.pk))

    assert "401 (expected 401)" in output
    assert WebhookEvent.objects.filter(provider="mock", signature_ok=False).count() == 1
    order.refresh_from_db()
    assert order.state == "pending_payment"


def test_stale_is_refused(stored):
    order, event = stored

    assert "401 (expected 401)" in run("stale", str(event.pk))

    order.refresh_from_db()
    assert order.state == "pending_payment"


def test_an_unverified_row_cannot_be_replayed(stored):
    unverified = WebhookEventFactory(provider="mock", signature_ok=False)
    with pytest.raises(CommandError, match="nothing to replay"):
        run("replay", str(unverified.pk))


def test_an_unknown_row_is_an_error(stored):
    with pytest.raises(CommandError, match="There is no webhook_event"):
        run("replay", "0")


def test_a_wrong_expectation_is_a_command_error(stored, monkeypatch):
    _, event = stored
    monkeypatch.setattr(
        delivery,
        "http_transport",
        lambda base_url, path=None: lambda body, headers: 500,
    )
    with pytest.raises(CommandError, match="expected 200, got 500"):
        run("replay", str(event.pk))
