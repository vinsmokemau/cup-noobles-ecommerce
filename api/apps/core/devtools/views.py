"""Test helpers for the end-to-end specs. Routed only when `DEV_TOOLS_ENABLED` (404 elsewhere).

`POST /dev/test/prelaunch/` switches pre-launch mode (G32, ADR-0038) so a spec can see the
storefront both ways (T12.15). It takes `{"on": true|false}` and answers with the new state.
"""

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.models import SiteSetting


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
