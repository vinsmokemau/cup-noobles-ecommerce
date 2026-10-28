"""The mock tracking page (SPEC.md 10.10). Routed only when `DEV_TOOLS_ENABLED`.

Each button records the new status in the mock store, then runs `sync_shipments` for that
shipment, so "Entregado" moves the order through the production code path.
"""

from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.core import providers
from apps.orders.models import Shipment
from apps.shipping.carriers.base import ShipmentStatus
from apps.shipping.management.commands.sync_shipments import sync_shipments

# URL segment -> the status the carrier will report.
BUTTONS = {
    "in_transit": ShipmentStatus.IN_TRANSIT,
    "delivered": ShipmentStatus.DELIVERED,
    "exception": ShipmentStatus.EXCEPTION,
}


def _mock() -> Any:
    """The active carrier when it is the mock; the page has nothing to show otherwise."""
    carrier = providers.carrier()
    if carrier.code != "mock":
        raise Http404
    return carrier


@require_GET
def track(request: HttpRequest, tracking_number: str) -> HttpResponse:
    events = _mock().history(tracking_number)
    if events is None:
        raise Http404
    shipment = Shipment.objects.filter(tracking_number=tracking_number).first()
    return render(
        request,
        "shipping_devtools/track.html",
        {
            "tracking_number": tracking_number,
            "order_number": shipment.order.number if shipment else "",
            "events": events,
        },
    )


@require_POST
def report(request: HttpRequest, tracking_number: str, status: str) -> HttpResponse:
    carrier = _mock()
    if status not in BUTTONS:
        raise Http404
    try:
        carrier.record_status(tracking_number, BUTTONS[status])
    except KeyError:
        raise Http404 from None
    shipment_ids = Shipment.objects.filter(tracking_number=tracking_number).values_list(
        "pk", flat=True
    )
    sync_shipments(list(shipment_ids))
    return redirect("dev-carrier-track", tracking_number=tracking_number)
