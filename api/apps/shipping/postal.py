"""Postal-code lookup interface (SPEC.md §4.3)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PostalCodeInfo:
    postal_code: str
    state_code: str
    state_name: str
    municipality: str
    neighborhoods: tuple[str, ...]


class PostalCodeLookup(Protocol):
    def lookup(self, postal_code: str) -> PostalCodeInfo | None: ...
