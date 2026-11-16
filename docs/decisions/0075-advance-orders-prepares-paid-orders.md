# ADR-0075: `advance_orders` moves paid delivery orders to preparing

## Status

accepted (2026-11-15)

## Context

Nothing fired T7 (`paid` to `preparing`, event `auto`) by itself. Its only caller was the admin
button "Pasar a preparación", so an order stayed `paid` after its payment until staff pressed it
(G75, found while building T15.1). The spec read both ways: the transition is named `auto`, and
P15-V01 and P10-V02 read "pay, then `preparing`"; P13-V01 (ADR-0067), P15-V03 and the seeded
order of 15.A say `paid` after a payment, as the code does.

Alternatives considered:

- T7 fires in the payment mapping, right after T2: no order ever rests in `paid`. Nine Verify
  rows name `paid` as the state after a payment (P8-V01, P8-V04, P8-V06, PAY-01, PAY-04, PAY-14,
  P9-V04, P13-V01, P15-V03), ADR-0067 would be amended, and many payment tests rewritten, right
  before local acceptance.
- T7 stays a staff action only: no code change, but one more click for every order, and with
  one person packing the click tells nobody anything.

## Decision

`advance_orders`, which runs every 5 minutes (§4.8), fires T7 through `apply_event` for every
`paid` delivery order. The admin button stays, for staff who want to start before the job runs.
An order is `paid` right after its payment and `preparing` after the job's next run.

A pickup order (Release 2, T8) is not touched. One order that fails does not stop the ones after
it, as for T12 (G47).

Checked by `test_g75_paid_delivery_orders_move_to_preparing`,
`test_g75_only_paid_delivery_orders_are_moved`,
`test_g75_an_order_the_job_moved_can_still_be_cancelled_refunded_or_shipped` and
`test_g75_one_failing_order_does_not_stop_the_run`
(`api/tests/integration/orders/test_advance.py`). P15-V01 asserts `paid` after the payment and
`preparing` after `run("advance_orders")`.

## Consequences

- No click per order. A customer who looks at the order in the first minutes sees it as paid.
- Staff can add a shipment only once the order is `preparing`: up to 5 minutes after the
  payment, or at once with the button. The demo script (15.B step 6) says so.
- T16, T17 and T10 start from `preparing` as well as `paid`, so cancelling, refunding and
  shipping are unaffected.
- The E2E journeys trigger the job through the command runner (15.3), which already lists
  `advance_orders`.
- Release 2 decides what the job does with a `paid` pickup order (T8).
- Changing it later touches `prepare_paid_orders` in
  `api/apps/orders/management/commands/advance_orders.py`, its tests, and the spec passages
  listed in the change log row for version 1.78.

## Source

OA-98; G75 (SPEC.md §2.4); 8.A (T7); §4.8; ADR-0067.
