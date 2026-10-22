"""Invoice interface (SPEC.md §4.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from apps.invoicing.models import InvoiceRequest


@dataclass(frozen=True)
class IssuedInvoice:
    cfdi_uuid: UUID
    folio: str
    pdf: bytes
    xml: bytes


class ManualIssueRequired(Exception):
    """The manual invoicer: staff record the CFDI in the admin."""


class InvoiceProvider(Protocol):
    code: str

    def issue(self, request: InvoiceRequest) -> IssuedInvoice: ...
