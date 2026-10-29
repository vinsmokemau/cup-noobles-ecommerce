"""The manual invoicer (SPEC.md §4.3, A8, ADR-0019).

There is no PAC: staff issue the CFDI outside the store and record it in the admin, so `issue()`
never returns an invoice. It is not a mock; `prod.py` accepts it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.invoicing.base import IssuedInvoice, ManualIssueRequired

if TYPE_CHECKING:
    from apps.invoicing.models import InvoiceRequest


class ManualInvoicer:
    code = "manual"

    def issue(self, request: InvoiceRequest) -> IssuedInvoice:
        raise ManualIssueRequired(
            f"CFDI for order {request.order.number} must be recorded by staff"
        )
