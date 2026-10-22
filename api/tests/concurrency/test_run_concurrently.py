"""The race helper itself: threads really hold separate connections (§4.6)."""

import pytest
from django.db import connection

from tests.concurrency import run_concurrently

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]


def backend_pid(_index: int = 0) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        return cursor.fetchone()[0]


def test_threads_hold_separate_connections():
    outcomes = run_concurrently(backend_pid, 2)

    assert [o.error for o in outcomes] == [None, None]
    pids = {o.value for o in outcomes}
    assert len(pids) == 2
    assert backend_pid() not in pids


def test_threads_start_together_behind_the_barrier():
    outcomes = run_concurrently(lambda i: i, 4)

    assert [o.value for o in outcomes] == [0, 1, 2, 3]


def test_connections_are_closed_on_exit():
    seen = []

    def grab(index):
        backend_pid(index)  # opens this thread's connection
        seen.append(connection.connection)

    run_concurrently(grab, 2)

    assert len(seen) == 2
    assert all(conn.closed for conn in seen)


def test_an_exception_is_returned_not_raised():
    def fail_odd(index):
        if index % 2:
            raise ValueError(index)
        return index

    outcomes = run_concurrently(fail_odd, 2)

    assert outcomes[0].value == 0
    assert isinstance(outcomes[1].error, ValueError)
