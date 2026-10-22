"""Error-tracking interface (SPEC.md §4.3)."""

from typing import Any, Protocol


class ErrorReporter(Protocol):
    def capture_exception(self, exc: BaseException, **context: Any) -> None: ...

    def capture_message(
        self, message: str, *, level: str = "error", **context: Any
    ) -> None: ...
