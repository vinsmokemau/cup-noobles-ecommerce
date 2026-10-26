"""The payment webhook endpoint (SPEC.md 9.B, T9.3)."""

from django.http import Http404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.providers import payment_provider
from apps.payments.webhooks import receive_notification

TOO_MANY = {"detail": "Too many requests."}


@method_decorator(
    ratelimit(key="ip", rate="300/m", method="POST", block=False), name="dispatch"
)
class PaymentWebhookView(APIView):
    """`POST /api/webhooks/payments/<provider>/`.

    Unauthenticated and so CSRF-exempt: the HMAC signature is the credential. The body is read raw,
    because the signature covers the notification the provider sent, not what a parser makes of it.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(self, request: Request, provider: str) -> Response:
        if provider != payment_provider().code:
            raise Http404
        if getattr(request, "limited", False):
            return Response(TOO_MANY, status=429)
        outcome = receive_notification(provider, request.headers, request.body)
        return Response(status=outcome.value)
