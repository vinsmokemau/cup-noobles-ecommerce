"""The guest order lookup (SPEC.md T6.7b, G35, ADR-0040)."""

from typing import Any

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.serializers import (
    OrderLookupRequestSerializer,
    OrderStatusSerializer,
)

NOT_FOUND = {"detail": "No encontramos ese pedido."}
TOO_MANY = {"detail": "Demasiados intentos. Inténtalo de nuevo más tarde."}


@method_decorator(
    ratelimit(key="ip", rate="5/h", method="POST", block=False), name="dispatch"
)
class OrderLookupView(APIView):
    """`POST /api/orders/lookup/` with `{number, email}`.

    The email travels in the body so no proxy, CDN or error log records it. A wrong email and a
    missing order return the same 404. Every call counts toward the limit, 5 per hour per IP.
    """

    # Anonymous and read-only: no session is read, so there is no CSRF to enforce.
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="orders_lookup",
        request=OrderLookupRequestSerializer,
        responses={
            200: OrderStatusSerializer,
            400: OpenApiResponse(description="The number or the email is missing."),
            404: OpenApiResponse(
                description="No order has that number and email (the same body for both)."
            ),
            429: OpenApiResponse(
                description="More than 5 lookups in an hour from this IP."
            ),
        },
    )
    def post(self, request: Request) -> Response:
        if getattr(request, "limited", False):
            return Response(TOO_MANY, status=status.HTTP_429_TOO_MANY_REQUESTS)

        data = OrderLookupRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = (
            Order.objects.filter(
                number=data.validated_data["number"],
                email=data.validated_data["email"],
            )
            .prefetch_related("lines", "shipments")
            .first()
        )
        if order is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderStatusSerializer(order).data)

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
