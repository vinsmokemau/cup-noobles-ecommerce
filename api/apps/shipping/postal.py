"""Postal-code lookup interface (SPEC.md §4.3)."""

from dataclasses import dataclass
from typing import Protocol

from apps.shipping.models import MxPostalCode


@dataclass(frozen=True)
class PostalCodeInfo:
    postal_code: str
    state_code: str
    state_name: str
    municipality: str
    neighborhoods: tuple[str, ...]


class PostalCodeLookup(Protocol):
    def lookup(self, postal_code: str) -> PostalCodeInfo | None: ...


class DbPostalCodeLookup:
    """Reads `mx_postal_code`; only the loaded data differs between datasets (§4.3)."""

    def lookup(self, postal_code: str) -> PostalCodeInfo | None:
        rows = list(
            MxPostalCode.objects.filter(postal_code=postal_code)
            .select_related("state")
            .order_by("neighborhood")
        )
        if not rows:
            return None
        first = rows[0]
        return PostalCodeInfo(
            postal_code=postal_code,
            state_code=first.state_id,
            state_name=first.state.name,
            municipality=first.municipality,
            neighborhoods=tuple(row.neighborhood for row in rows),
        )
