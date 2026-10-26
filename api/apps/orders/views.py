"""The guest order lookup (SPEC.md T6.7b, G35, ADR-0040) and the checkout endpoint (T8.4)."""

import hashlib
import json
from dataclasses import asdict
from typing import Any

from django.db import transaction
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts.identity import get_cart
from apps.carts.models import Cart
from apps.carts.views import CartCsrfAuthentication
from apps.orders.models import Order
from apps.orders.serializers import (
    CheckoutLinesUnavailableSerializer,
    CheckoutRequestSerializer,
    CheckoutResponseSerializer,
    OrderLookupRequestSerializer,
    OrderStatusSerializer,
)
from apps.orders.services import (
    EmptyCart,
    LinesUnavailable,
    ShippingUnavailable,
    create_order_from_cart,
)

EMPTY_CART = "El carrito está vacío."
IDEMPOTENCY_KEY_REUSED = {
    "code": "idempotency_key_reused",
    "detail": "Esa clave ya se usó con otros datos.",
}
IDEMPOTENCY_KEY_MAX_LENGTH = 255
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


def _fingerprint(body: Any) -> str:
    """SHA-256 of the canonical request body (G3): the same JSON in any key order matches."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _checkout_reply(order: Order, code: int) -> Response:
    payment = order.payments.order_by("-id").first()
    checkout_url = payment.raw.get("checkout_url", "") if payment else ""
    data = CheckoutResponseSerializer(
        {
            "order_number": order.number,
            "order_public_id": order.public_id,
            "checkout_url": checkout_url,
        }
    ).data
    return Response(data, status=code)


class CheckoutView(APIView):
    """`POST /api/checkout/`: the cart named by the `cart_token` cookie becomes an order.

    Atomic and safe to repeat (REQ-021). The cart row is locked first, so two requests with the
    same `Idempotency-Key` take turns: the second finds the order the first created. Any refusal
    rolls back, so it leaves no order and no reservation.
    """

    authentication_classes = [CartCsrfAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="checkout_create",
        request=CheckoutRequestSerializer,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                str,
                OpenApiParameter.HEADER,
                required=False,
                description="Repeating the key with the same body returns the same order.",
            )
        ],
        responses={
            200: CheckoutResponseSerializer,
            201: CheckoutResponseSerializer,
            400: OpenApiResponse(
                description="Field errors, an empty cart, or an address with no shipping price."
            ),
            403: OpenApiResponse(description="The CSRF token is missing or wrong."),
            409: OpenApiResponse(
                CheckoutLinesUnavailableSerializer,
                description="A line is unavailable or short of stock; nothing was reserved.",
            ),
            422: OpenApiResponse(
                description="`idempotency_key_reused`: the key was used with a different body."
            ),
        },
    )
    def post(self, request: Request) -> Response:
        data = CheckoutRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key", "").strip() or None
        if key is not None and len(key) > IDEMPOTENCY_KEY_MAX_LENGTH:
            raise ValidationError(
                {"idempotency_key": ["La clave de idempotencia es demasiado larga."]}
            )
        cart = get_cart(request)
        if cart is None:
            return Response({"cart": [EMPTY_CART]}, status=status.HTTP_400_BAD_REQUEST)
        fingerprint = _fingerprint(request.data)
        body = data.validated_data

        try:
            with transaction.atomic():
                Cart.objects.select_for_update().get(pk=cart.pk)
                if key is not None:
                    existing = Order.objects.filter(
                        cart_token=cart.token, idempotency_key=key
                    ).first()
                    if existing is not None:
                        if existing.idempotency_fingerprint != fingerprint:
                            return Response(
                                IDEMPOTENCY_KEY_REUSED,
                                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            )
                        return _checkout_reply(existing, status.HTTP_200_OK)
                order = create_order_from_cart(
                    cart,
                    email=body["email"],
                    fulfillment_method=body["fulfillment_method"],
                    address_or_location=body["address_payload"],
                    phone=body["phone"],
                    customer_note=body["customer_note"],
                    idempotency_key=key,
                    idempotency_fingerprint=fingerprint if key else None,
                )
        except EmptyCart as error:
            return Response({"cart": [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        except ShippingUnavailable as error:
            return Response(
                {"address_payload": {"postal_code": [str(error)]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except LinesUnavailable as error:
            return Response(
                {
                    "code": "lines_unavailable",
                    "line_errors": [asdict(item) for item in error.line_errors],
                },
                status=status.HTTP_409_CONFLICT,
            )
        return _checkout_reply(order, status.HTTP_201_CREATED)

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
