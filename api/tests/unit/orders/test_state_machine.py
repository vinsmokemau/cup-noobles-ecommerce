"""The state machine's table and its simplest rejection (SPEC.md 8.A, T8.1)."""

import re
from pathlib import Path

import pytest

from apps.orders.models import ORDER_STATES, Order
from apps.orders.state_machine import TRANSITIONS, IllegalTransition, apply_event
from tests.factories.orders import order_in_state

SPEC_CANDIDATES = (Path("/repo/SPEC.md"), Path(__file__).parents[4] / "SPEC.md")
SPEC = next(path for path in SPEC_CANDIDATES if path.exists())
TABLE_HEADER = "| # | From | Event | To | Guard | Side effects | Release |"

REFUND_PARAGRAPH = "**Refunds are payment records"


def names_in(cell: str) -> set[str]:
    return set(re.findall(r"`(\w+)`", cell))


def refund_states_after_close() -> set[str]:
    """The states named in "From `completed`, `expired` and `cancelled`, both ..." (G27)."""
    paragraph = (
        SPEC.read_text(encoding="utf-8").split(REFUND_PARAGRAPH)[1].splitlines()[0]
    )
    return names_in(paragraph.split("From ")[1].split(", both")[0])


def release_one_rows() -> dict[tuple[str, str], str]:
    """The Release 1 rows of the 8.A table in SPEC.md, as {(from, event): to}. "(unchanged)"
    is the source state itself; T17 and T18 also hold from the states the refund paragraph
    names."""
    text = SPEC.read_text(encoding="utf-8")
    table = text.split(TABLE_HEADER)[1]
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
        else:
            from_states = names_in(sources)
        event = event.strip("`")
        for state in from_states:
            rows[(state, event)] = (
                state if "(unchanged)" in target else names_in(target).pop()
            )
        if event in ("refund_issued", "partial_refund_issued"):
            for state in refund_states_after_close():
                rows[(state, event)] = state
    return rows


def test_transitions_equal_the_release_one_rows_of_the_table():
    expected = release_one_rows()
    assert len(expected) == 25
    actual = {
        (state, event): t.target(Order(state=state))
        for (state, event), t in TRANSITIONS.items()
    }
    assert actual == expected


def test_every_state_in_the_table_is_a_known_state():
    known = set(ORDER_STATES)
    assert {state for state, _ in TRANSITIONS} <= known
    assert {
        t.target(Order(state=state)) for (state, _), t in TRANSITIONS.items()
    } <= known


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
