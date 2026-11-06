"""The guest order lookup (SPEC.md T6.7b, G35, ADR-0040) and the checkout endpoint (T8.4)."""

import hashlib
import json
from dataclasses import asdict
from typing import Any

from django.db import transaction
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts.identity import get_cart_token
from apps.carts.models import Cart
from apps.carts.views import CartCsrfAuthentication
from apps.core.providers import payment_provider
from apps.orders import status_token
from apps.orders.models import Order
from apps.orders.serializers import (
    CheckoutLinesUnavailableSerializer,
    CheckoutRequestSerializer,
    CheckoutResponseSerializer,
    CheckoutTotalChangedSerializer,
    OrderLookupRequestSerializer,
    OrderStatusSerializer,
    PayRetryResponseSerializer,
)
from apps.orders.services import (
    EmptyCart,
    LinesUnavailable,
    ShippingUnavailable,
    TotalChanged,
    create_order_from_cart,
)
from apps.payments.models import Payment

EMPTY_CART = "El carrito está vacío."
IDEMPOTENCY_KEY_REUSED = {
    "code": "idempotency_key_reused",
    "detail": "Esa clave ya se usó con otros datos.",
}
IDEMPOTENCY_KEY_MAX_LENGTH = 255
NOT_FOUND = {"detail": "No encontramos ese pedido."}
NOT_PAYABLE = {
    "code": "order_not_payable",
    "detail": "Este pedido ya no admite un nuevo intento de pago.",
}
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
            .prefetch_related("lines", "shipments", "payments")
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


class OrderStatusTokenView(APIView):
    """`GET /api/orders/{public_id}/status/?t=<token>` (G21, ADR-0065).

    Read-only and not subject to the guest-lookup limit. A missing order, an expired token and a
    tampered token return the same 404, so the response says nothing about which one it was.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="orders_status",
        parameters=[OpenApiParameter("t", str, OpenApiParameter.QUERY, required=True)],
        responses={
            200: OrderStatusSerializer,
            404: OpenApiResponse(
                description="No such order, or the token is missing, expired or tampered."
            ),
        },
    )
    def get(self, request: Request, public_id: str) -> Response:
        if not status_token.is_valid(request.query_params.get("t"), public_id):
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        order = (
            Order.objects.filter(public_id=public_id)
            .prefetch_related("lines", "shipments", "payments")
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


class OrderPayRetryView(APIView):
    """`POST /api/orders/{public_id}/pay/?t=<token>` (G22, ADR-0066).

    Authorised by the order-status token alone, so it carries no session and no CSRF. While the
    order is `pending_payment` it returns a fresh `checkout_url`; the reservations and the
    `payment_deadline_at` are untouched. Any other state returns 409. A missing order and a bad
    token return the same 404 as the status endpoint.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="orders_pay",
        request=None,
        parameters=[OpenApiParameter("t", str, OpenApiParameter.QUERY, required=True)],
        responses={
            200: PayRetryResponseSerializer,
            404: OpenApiResponse(
                description="No such order, or the token is missing, expired or tampered."
            ),
            409: OpenApiResponse(description="The order is not `pending_payment`."),
        },
    )
    def post(self, request: Request, public_id: str) -> Response:
        if not status_token.is_valid(request.query_params.get("t"), public_id):
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            # Locked so a retry cannot race the payment webhook or the deadline job.
            order = (
                Order.objects.select_for_update().filter(public_id=public_id).first()
            )
            if order is None:
                return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            if order.state != "pending_payment":
                return Response(NOT_PAYABLE, status=status.HTTP_409_CONFLICT)
            provider = payment_provider()
            session = provider.create_checkout(order)
            Payment.objects.create(
                order=order,
                provider=provider.code,
                provider_preference_id=session.preference_id,
                status="initiated",
                amount_cents=order.total_cents,
                raw={"checkout_url": session.url},
            )
        return Response({"checkout_url": session.url})

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
                PolymorphicProxySerializer(
                    component_name="CheckoutConflict",
                    serializers=[
                        CheckoutLinesUnavailableSerializer,
                        CheckoutTotalChangedSerializer,
                    ],
                    resource_type_field_name="code",
                ),
                description="`lines_unavailable`: a line is unavailable or short of stock. "
                "`total_changed`: the fresh total differs from `expected_total_cents`, and "
                "`totals` holds the fresh ones. Either way nothing was reserved.",
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
        token = get_cart_token(request)
        if token is None:
            return Response({"cart": [EMPTY_CART]}, status=status.HTTP_400_BAD_REQUEST)
        fingerprint = _fingerprint(request.data)
        body = data.validated_data

        try:
            with transaction.atomic():
                # The cart row is locked when it exists, converted or not, so a replay waits for
                # the first request to commit and then finds its order (ADR-0049).
                cart = Cart.objects.select_for_update().filter(token=token).first()
                if cart is None:
                    return Response(
                        {"cart": [EMPTY_CART]}, status=status.HTTP_400_BAD_REQUEST
                    )
                if key is not None:
                    existing = Order.objects.filter(
                        cart_token=token, idempotency_key=key
                    ).first()
                    if existing is not None:
                        if existing.idempotency_fingerprint != fingerprint:
                            return Response(
                                IDEMPOTENCY_KEY_REUSED,
                                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            )
                        return _checkout_reply(existing, status.HTTP_200_OK)
                if cart.converted_order_id is not None:
                    return Response(
                        {"cart": [EMPTY_CART]}, status=status.HTTP_400_BAD_REQUEST
                    )
                order = create_order_from_cart(
                    cart,
                    email=body["email"],
                    fulfillment_method=body["fulfillment_method"],
                    address_or_location=body["address_payload"],
                    phone=body["phone"],
                    customer_note=body["customer_note"],
                    idempotency_key=key,
                    idempotency_fingerprint=fingerprint if key else None,
                    expected_total_cents=body.get("expected_total_cents"),
                    invoice=body.get("invoice"),
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
        except TotalChanged as error:
            return Response(
                {"code": "total_changed", "totals": asdict(error.totals)},
                status=status.HTTP_409_CONFLICT,
            )
        return _checkout_reply(order, status.HTTP_201_CREATED)

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
