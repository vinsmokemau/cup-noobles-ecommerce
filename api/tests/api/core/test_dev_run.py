"""T15.3: the dev command runner `POST /dev/test/run/` (404 where dev tools are off; the
production guard is P15-V11 in tests/integration/demo/test_seed_guards.py)."""

import importlib
from datetime import timedelta
from pathlib import Path

import pytest
from django.urls import clear_url_caches
from django.utils import timezone

from apps.core.devtools.views import RUNNABLE_COMMANDS
from apps.inventory.models import InventoryReservation
from apps.notifications.models import EmailOutbox
from apps.orders.models import Order
from tests.factories.inventory import holding_order, stocked_variant
from tests.factories.orders import STAND_IN_ADDRESS, order_in_state

URL = "/dev/test/run/"


def run(client, command, args=None):
    body = {"command": command} if args is None else {"command": command, "args": args}
    return client.post(URL, body, content_type="application/json")


@pytest.fixture
def pending_order(db):
    """An order waiting for its payment, holding 2 of 5 units for another hour."""
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2, ttl=timedelta(hours=1))
    Order.objects.filter(pk=order.pk).update(
        state="pending_payment",
        shipping_address=STAND_IN_ADDRESS,
        payment_deadline_at=timezone.now() + timedelta(hours=1),
    )
    return order


def test_the_list_is_the_one_in_the_spec():
    assert RUNNABLE_COMMANDS == (
        "expire_reservations",
        "advance_orders",
        "reconcile_payments",
        "sync_shipments",
        "send_outbox",
        "mock_payments expire-order",
        "mock_payments deliver --once",
    )


@pytest.mark.parametrize(
    ("command", "output"),
    [
        ("expire_reservations", "expire_reservations: 0 order(s) released"),
        ("advance_orders", "advance_orders: 0 order(s) moved to preparing"),
        ("reconcile_payments", "reconcile_payments: 0 orders checked"),
        ("sync_shipments", "sync_shipments: 0 shipments checked"),
        ("send_outbox", "send_outbox: 0 sent, 0 failed"),
        ("mock_payments deliver --once", "mock_payments deliver: 0 delivered"),
    ],
)
@pytest.mark.django_db
def test_each_job_runs_and_answers_with_its_output(client, command, output):
    response = run(client, command)

    assert response.status_code == 200
    assert response.json()["command"] == command
    assert response.json()["args"] == []
    assert response.json()["output"].startswith(output)


@pytest.mark.django_db
def test_advance_orders_moves_a_paid_order_to_preparing(client):
    order = order_in_state("paid")

    response = run(client, "advance_orders")

    assert "1 order(s) moved to preparing" in response.json()["output"]
    order.refresh_from_db()
    assert order.state == "preparing"


def test_expire_order_takes_the_order_number_and_send_outbox_sends_its_email(
    client, pending_order, settings
):
    expired = run(client, "mock_payments expire-order", [pending_order.number])

    assert expired.status_code == 200
    assert expired.json()["args"] == [pending_order.number]
    assert "expire_reservations: 1 order(s) released" in expired.json()["output"]
    pending_order.refresh_from_db()
    assert pending_order.state == "expired"
    assert not InventoryReservation.objects.filter(
        order=pending_order, state=InventoryReservation.State.HELD
    ).exists()

    # Nothing is on disk until `send_outbox` runs: the E2E stack has no scheduler (G77).
    emails = Path(settings.EMAIL_FILE_DIR)
    assert not emails.exists() or not list(emails.iterdir())
    queued = EmailOutbox.objects.get(order=pending_order, template="order_expired")
    assert queued.sent_at is None

    sent = run(client, "send_outbox")

    assert sent.json()["output"].startswith("send_outbox: 1 sent, 0 failed")
    queued.refresh_from_db()
    assert queued.sent_at is not None
    assert any("order_expired" in path.name for path in emails.iterdir())


@pytest.mark.django_db
def test_a_command_that_fails_answers_400_with_its_message(client):
    response = run(client, "mock_payments expire-order", ["CN-0000-000000"])

    assert response.status_code == 400
    assert response.json()["detail"] == "There is no order CN-0000-000000"


@pytest.mark.django_db
def test_deliver_cannot_be_made_to_loop(client):
    response = run(client, "mock_payments deliver --once", ["--loop"])

    assert response.status_code == 400
    assert "--loop" in response.json()["detail"]


@pytest.mark.parametrize(
    "command",
    [
        "seed_demo",
        "seed_e2e",
        "flush",
        "process_webhooks",
        "mock_payments",
        "mock_payments reset",
        "mock_payments approve",
        "mock_payments deliver",
        "mock_payments deliver --loop",
        "advance_orders --verbosity 3",
        " advance_orders",
        "",
        None,
        ["advance_orders"],
    ],
)
@pytest.mark.django_db
def test_a_command_off_the_list_is_rejected(client, command):
    order = order_in_state("paid")

    response = run(client, command)

    assert response.status_code == 400
    assert response.json()["commands"] == list(RUNNABLE_COMMANDS)
    order.refresh_from_db()
    assert order.state == "paid"


@pytest.mark.parametrize("args", ["CN-2026-000001", [1], [["x"]], {"order": "x"}, None])
@pytest.mark.django_db
def test_args_must_be_a_list_of_strings(client, args):
    response = client.post(
        URL,
        {"command": "mock_payments expire-order", "args": args},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "args" in response.json()["detail"]


@pytest.mark.parametrize("body", ["not json", "[]", '"advance_orders"', ""])
def test_a_body_that_is_not_an_object_is_rejected(client, body):
    response = client.post(URL, body, content_type="application/json")

    assert response.status_code == 400


def test_run_is_post_only(client):
    assert client.get(URL).status_code == 405


def test_route_is_not_registered_when_dev_tools_are_off(client, settings):
    import config.urls

    settings.DEV_TOOLS_ENABLED = False
    clear_url_caches()
    importlib.reload(config.urls)
    try:
        response = run(client, "advance_orders")
    finally:
        settings.DEV_TOOLS_ENABLED = True
        clear_url_caches()
        importlib.reload(config.urls)

    assert response.status_code == 404
