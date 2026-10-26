"""Payment contract scenarios PAY-01 to PAY-08 (SPEC.md 9.13, T9.13a). T9.13b adds PAY-09 to PAY-19.

Each scenario is written against `PaymentDriver` and goes through the real webhook endpoint, real
`webhook_event` rows and the real state machine. Only the driver differs between providers.
Sockets stay disabled (CR-41).
"""

from datetime import timedelta

from django.core.management import call_command

from apps.inventory.models import InventoryReservation, StockItem, StockLedger
from apps.notifications.models import EmailOutbox
from apps.orders.models import Order
from apps.payments.models import Payment, WebhookEvent
from tests.contract.payments.conftest import CHECKOUT
from tests.contract.payments.driver import Outcome

CARD_WINDOW = timedelta(minutes=30)
GRACE = timedelta(hours=2)  # D6: an OXXO order outlives its voucher by this much (9.5)


def play(driver, order, outcome, **opts):
    """Check out, play `outcome`, and deliver what the provider queued. Returns the payment id."""
    payment_id = driver.complete(driver.checkout(order), outcome, **opts)
    driver.deliver_pending_notifications()
    return payment_id


def reload(order):
    return Order.objects.get(pk=order.pk)


def payments(order):
    """The provider's payments for `order`. The `initiated` row that checkout opens for the
    preference stays beside them (it has no provider payment id)."""
    return Payment.objects.filter(order=order).exclude(status="initiated")


def holds(order):
    return InventoryReservation.objects.filter(order=order)


def release_due():
    call_command("expire_reservations")


def event_names(order):
    return list(order.events.order_by("pk").values_list("event", flat=True))


def test_pay_01_card_approved(driver, order, variant):
    play(driver, order, Outcome.APPROVED)

    assert reload(order).state == "paid"
    payment = payments(order).get()
    assert (payment.status, payment.method) == ("approved", "credit_card")
    assert payment.amount_cents == order.total_cents
    # Stock committed: the units left the shelf and are no longer held.
    assert {r.state for r in holds(order)} == {"committed"}
    item = StockItem.objects.get(variant=variant)
    assert (item.on_hand, item.reserved) == (10 - 2, 0)
    sale = StockLedger.objects.get(order=order, reason="sale_online")
    assert (sale.delta, sale.balance_after) == (-2, 8)
    # The confirmation email is queued, once.
    assert (
        EmailOutbox.objects.filter(order=order, template="order_confirmation").count()
        == 1
    )


def test_pay_02_approved_with_installments(driver, order, variant):
    play(driver, order, Outcome.APPROVED_IN_INSTALLMENTS, installments=6)

    assert reload(order).state == "paid"
    payment = payments(order).get()
    assert (payment.status, payment.installments) == ("approved", 6)
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockLedger.objects.filter(order=order, reason="sale_online").count() == 1
    assert EmailOutbox.objects.filter(
        order=order, template="order_confirmation"
    ).exists()


def test_pay_03_oxxo_pending(driver, order, shop):
    payment_id = play(driver, order, Outcome.OXXO_VOUCHER)

    # Not paid yet; the voucher is stored and shown.
    assert reload(order).state == "pending_payment"
    payment = payments(order).get()
    assert (payment.status, payment.method) == ("pending", "oxxo")
    assert payment.provider_payment_id == payment_id
    assert payment.voucher_url
    assert payment.voucher_expires_at is not None
    assert EmailOutbox.objects.filter(order=order, template="oxxo_voucher").exists()
    # The holds and the deadline stretch to the voucher's expiry plus the grace, together.
    deadline = payment.voucher_expires_at + GRACE
    assert reload(order).payment_deadline_at == deadline
    assert {r.expires_at for r in holds(order)} == {deadline}
    assert {r.state for r in holds(order)} == {"held"}

    # The card window is long gone, and the job still leaves the holds alone.
    shop.travel(CHECKOUT + CARD_WINDOW + timedelta(minutes=1))
    release_due()
    assert reload(order).state == "pending_payment"
    assert {r.state for r in holds(order)} == {"held"}


def test_pay_04_oxxo_pending_then_paid(driver, order, variant):
    payment_id = play(driver, order, Outcome.OXXO_VOUCHER)
    assert reload(order).state == "pending_payment"

    play_voucher = driver.complete(
        driver.checkout(order), Outcome.VOUCHER_PAID, payment_id=payment_id
    )
    driver.deliver_pending_notifications()

    # One payment, two notifications (`pending`, then `approved`), both processed.
    assert play_voucher == payment_id
    assert reload(order).state == "paid"
    payment = payments(order).get()
    assert (payment.status, payment.provider_payment_id) == ("approved", payment_id)
    events = WebhookEvent.objects.filter(topic="payment")
    assert events.count() == 2
    assert not events.filter(processed_at__isnull=True).exists()
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockItem.objects.get(variant=variant).on_hand == 10 - 2
    assert event_names(order).count("payment_approved") == 1


def test_pay_05_oxxo_voucher_expires(driver, order, variant, shop):
    payment_id = play(driver, order, Outcome.OXXO_VOUCHER)
    deadline = reload(order).payment_deadline_at

    driver.complete(
        driver.checkout(order), Outcome.VOUCHER_LAPSED, payment_id=payment_id
    )
    driver.deliver_pending_notifications()

    # The provider ends the voucher; the order waits out its grace, then the job expires it.
    assert payments(order).get().status == "cancelled"
    assert reload(order).state == "pending_payment"
    shop.travel(deadline + timedelta(minutes=1))
    release_due()

    assert reload(order).state == "expired"
    assert {r.state for r in holds(order)} == {"released"}
    item = StockItem.objects.get(variant=variant)
    assert (item.on_hand, item.reserved) == (10, 0)
    assert not StockLedger.objects.filter(order=order, reason="sale_online").exists()
    assert EmailOutbox.objects.filter(order=order, template="order_expired").exists()


def test_pay_06_spei_pending_then_paid(driver, order, variant, settings):
    payment_id = play(driver, order, Outcome.SPEI_TRANSFER)

    payment = payments(order).get()
    assert (payment.status, payment.method) == ("pending", "spei")
    assert reload(order).state == "pending_payment"
    # SPEI deadlines: the holds and the order move to the SPEI window together.
    deadline = CHECKOUT + timedelta(hours=settings.RESERVATION_TTL_SPEI_HOURS)
    assert reload(order).payment_deadline_at == deadline
    assert {r.expires_at for r in holds(order)} == {deadline}

    driver.complete(driver.checkout(order), Outcome.VOUCHER_PAID, payment_id=payment_id)
    driver.deliver_pending_notifications()

    assert reload(order).state == "paid"
    assert payments(order).get().status == "approved"
    events = WebhookEvent.objects.filter(topic="payment")
    assert events.count() == 2
    assert not events.filter(processed_at__isnull=True).exists()
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockItem.objects.get(variant=variant).on_hand == 10 - 2


def test_pay_07_rejected_then_retried(driver, order, variant):
    play(driver, order, Outcome.REJECTED)

    # The order stays open, with its stock held.
    assert reload(order).state == "pending_payment"
    assert payments(order).get().status == "rejected"
    assert {r.state for r in holds(order)} == {"held"}
    assert "payment_rejected" in event_names(order)

    # Before the deadline the customer pays again, on a fresh checkout.
    play(driver, order, Outcome.APPROVED)

    assert reload(order).state == "paid"
    assert sorted(payments(order).values_list("status", flat=True)) == [
        "approved",
        "rejected",
    ]
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockItem.objects.get(variant=variant).on_hand == 10 - 2


def test_pay_08_no_payment_then_expiry(driver, order, variant, shop):
    deadline = reload(order).payment_deadline_at

    # The customer leaves the provider's page: nothing is paid, nothing is sent.
    assert play(driver, order, Outcome.ABANDONED) == ""
    assert not WebhookEvent.objects.exists()
    shop.travel(deadline + timedelta(minutes=1))
    release_due()

    assert reload(order).state == "expired"
    assert {r.state for r in holds(order)} == {"released"}
    item = StockItem.objects.get(variant=variant)
    assert (item.on_hand, item.reserved) == (10, 0)
    assert EmailOutbox.objects.filter(order=order, template="order_expired").exists()
