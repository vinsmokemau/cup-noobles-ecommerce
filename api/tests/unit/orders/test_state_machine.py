"""The state machine's table and its simplest rejection (SPEC.md 8.A, T8.1)."""

import re
from pathlib import Path

import pytest

from apps.orders.models import ORDER_STATES
from apps.orders.state_machine import TRANSITIONS, IllegalTransition, apply_event
from tests.factories.orders import order_in_state

SPEC_CANDIDATES = (Path("/repo/SPEC.md"), Path(__file__).parents[4] / "SPEC.md")
SPEC = next(path for path in SPEC_CANDIDATES if path.exists())
TABLE_HEADER = "| # | From | Event | To | Guard | Side effects | Release |"

# "any post-`paid` state" in rows T17 and T18. G26 and G27 decide whether `completed`,
# `partially_refunded` and the other terminal states join; until then the table has these.
POST_PAID = {"paid", "preparing", "shipped", "delivered"}


def names_in(cell: str) -> set[str]:
    return set(re.findall(r"`(\w+)`", cell))


def release_one_rows() -> dict[tuple[str, str], str]:
    """The Release 1 rows of the 8.A table in SPEC.md, as {(from, event): to}."""
    table = SPEC.read_text(encoding="utf-8").split(TABLE_HEADER)[1]
    rows = {}
    for line in table.splitlines()[2:]:
        if not line.startswith("| T"):
            break
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        sources, event, target, release = cells[1], cells[2], cells[3], cells[6]
        if not release.startswith("R1"):
            continue
        if release != "R1":  # T16: "R1 from `paid` and `preparing`; R2 from ..."
            from_states = names_in(release.split(";")[0])
        elif "any post-" in sources:
            from_states = POST_PAID
        else:
            from_states = names_in(sources)
        for state in from_states:
            rows[(state, event.strip("`"))] = names_in(target).pop()
    return rows


def test_transitions_equal_the_release_one_rows_of_the_table():
    expected = release_one_rows()
    assert len(expected) == 19
    actual = {key: t.to_state for key, t in TRANSITIONS.items()}
    assert actual == expected


def test_every_state_in_the_table_is_a_known_state():
    known = set(ORDER_STATES)
    assert {state for state, _ in TRANSITIONS} <= known
    assert {t.to_state for t in TRANSITIONS.values()} <= known


@pytest.mark.django_db
def test_p8_v02_delivered_on_pending_payment_illegal():
    order = order_in_state("pending_payment")
    with pytest.raises(IllegalTransition) as raised:
        apply_event(order, "marked_delivered")
    assert (raised.value.from_state, raised.value.event) == (
        "pending_payment",
        "marked_delivered",
    )
    order.refresh_from_db()
    assert order.state == "pending_payment"
