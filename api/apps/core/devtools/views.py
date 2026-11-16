"""Test helpers for the end-to-end specs. Routed only when `DEV_TOOLS_ENABLED` (404 elsewhere).

`POST /dev/test/prelaunch/` switches pre-launch mode (G32, ADR-0038) so a spec can see the
storefront both ways (T12.15). It takes `{"on": true|false}` and answers with the new state.

`GET /dev/test/inventory/<sku>/` and `GET /dev/test/orders/?email=<email>` (T13.8) are
read-only: they let a spec assert stock and order effects without scraping the admin.

`POST /dev/test/run/` (T15.3) runs one management command from `RUNNABLE_COMMANDS`, so a spec
moves the clock-driven jobs itself: the E2E stack has no scheduler (§4.8, G77). It takes
`{"command": "<an entry of the list>", "args": ["<more arguments>"]}` and answers with the
command's output.
"""

import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.catalog.models import Variant
from apps.core.models import SiteSetting
from apps.inventory.models import StockItem
from apps.orders.models import Order

# Everything the runner may run (SPEC.md 15.3): five jobs of §4.8 and two actions of the mock
# payment provider. An entry is the fixed start of the command line; the request's `args` follow
# it, so `mock_payments expire-order` cannot become another `mock_payments` action.
RUNNABLE_COMMANDS = (
    "expire_reservations",
    "advance_orders",
    "reconcile_payments",
    "sync_shipments",
    "send_outbox",
    "mock_payments expire-order",
    "mock_payments deliver --once",
)


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


@csrf_exempt  # a test helper called by Playwright with no session or CSRF cookie
@require_POST
def run(request: HttpRequest) -> HttpResponse:
    """Run one whitelisted command now and answer with what it printed.

    A command that fails (`CommandError`: an unknown order, an argument it does not take, a job
    that could not finish) answers 400 with its message and the output so far.
    """
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = None
    command = body.get("command") if isinstance(body, dict) else None
    if command not in RUNNABLE_COMMANDS:
        return JsonResponse(
            {
                "detail": "Send a command from the list.",
                "commands": list(RUNNABLE_COMMANDS),
            },
            status=400,
        )
    args = body.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        return JsonResponse({"detail": '"args" is a list of strings.'}, status=400)
    output = StringIO()
    try:
        call_command(*command.split(), *args, stdout=output, stderr=output)
    except CommandError as error:
        return JsonResponse(
            {"detail": str(error), "output": output.getvalue()}, status=400
        )
    return JsonResponse({"command": command, "args": args, "output": output.getvalue()})
