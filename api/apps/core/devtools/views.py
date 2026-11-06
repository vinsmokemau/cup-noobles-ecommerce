"""Test helpers for the end-to-end specs. Routed only when `DEV_TOOLS_ENABLED` (404 elsewhere).

`POST /dev/test/prelaunch/` switches pre-launch mode (G32, ADR-0038) so a spec can see the
storefront both ways (T12.15). It takes `{"on": true|false}` and answers with the new state.

`GET /dev/test/inventory/<sku>/` and `GET /dev/test/orders/?email=<email>` (T13.8) are
read-only: they let a spec assert stock and order effects without scraping the admin.
"""

import json

from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.catalog.models import Variant
from apps.core.models import SiteSetting
from apps.inventory.models import StockItem
from apps.orders.models import Order


@csrf_exempt  # a test helper called by Playwright with no session or CSRF cookie
@require_POST
def prelaunch(request: HttpRequest) -> HttpResponse:
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = None
    on = body.get("on") if isinstance(body, dict) else None
    if not isinstance(on, bool):
        return JsonResponse(
            {"detail": 'Send {"on": true} or {"on": false}.'}, status=400
        )
    SiteSetting.objects.update_or_create(pk=1, defaults={"prelaunch_mode": on})
    return JsonResponse({"prelaunch": on})


@require_GET
def inventory(request: HttpRequest, sku: str) -> HttpResponse:
    """Stock of one SKU: physical units summed over every location, plus pre-order units."""
    variant = Variant.objects.filter(sku=sku).first()
    if variant is None:
        return JsonResponse({"detail": "Unknown SKU."}, status=404)
    totals = StockItem.objects.filter(variant=variant).aggregate(
        on_hand=Sum("on_hand"), reserved=Sum("reserved")
    )
    return JsonResponse(
        {
            "on_hand": totals["on_hand"] or 0,
            "reserved": totals["reserved"] or 0,
            "preorder_committed": variant.preorder_committed,
        }
    )


@require_GET
def orders(request: HttpRequest) -> HttpResponse:
    """The orders placed with one email, newest first, with their number and state."""
    email = request.GET.get("email", "").strip()
    if not email:
        return JsonResponse({"detail": "Send ?email=<email>."}, status=400)
    rows = Order.objects.filter(email=email).order_by("-id").values("number", "state")
    return JsonResponse({"orders": list(rows)})
