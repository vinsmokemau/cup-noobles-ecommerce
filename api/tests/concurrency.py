"""Race tests: `n` threads released together, each on its own connection (SPEC.md §4.6)."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import connections

BARRIER_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Outcome:
    """What one thread produced: a return value, or the exception it raised."""

    value: Any = None
    error: BaseException | None = None


def run_concurrently(fn: Callable[[int], Any], n: int) -> list[Outcome]:
    """Call `fn(index)` in `n` threads that all start at the same moment.

    Every thread waits on a `threading.Barrier`, runs `fn` on its own database
    connection, and closes that connection on exit. Outcomes come back in index
    order; an exception raised by `fn` is returned, not re-raised, so a test
    can assert which racer lost. Use it with `django_db(transaction=True)`.
    """
    barrier = threading.Barrier(n, timeout=BARRIER_TIMEOUT_SECONDS)
    outcomes: list[Outcome] = [Outcome()] * n

    def worker(index: int) -> None:
        try:
            barrier.wait()
            outcomes[index] = Outcome(value=fn(index))
        except BaseException as error:  # noqa: BLE001 - reported to the caller
            outcomes[index] = Outcome(error=error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return outcomes
