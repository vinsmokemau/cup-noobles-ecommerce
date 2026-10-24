# ADR-0032: States are loaded in production by a separate seed command

## Status

accepted (2026-10-23)

## Context

T2.7 seeds `mx_state` through `manage.py seed_dev_defaults`, the Part A command for the §2.5 stand-ins. The 32 states are real reference data that production needs too, and `seed_dev_defaults` is a dev command whose rows `check_placeholders` treats as stand-ins. No task loaded the states in production. Loading them with a data migration was ruled out: the test suite's `transaction=True` tests flush tables, which would wipe rows a migration inserted.

## Decision

1. A `manage.py seed_states` command runs `apps.shipping.seeds.seed_states`. It is idempotent.
2. The deploy step runs it. `seed_dev_defaults` keeps calling the same function.
3. T22.3 builds and runs the command as part of the launch data.

## Consequences

- Production and development load the states from one function, with one list of codes.
- The deploy step gains one command. Running it twice changes nothing.
- Moving the seed into a data migration later would touch the test fixtures that flush tables.

## Source

G41; OA-29 (2026-10-23); T2.7.
