"""The cart endpoints (SPEC.md T7.1, ADR-0011).

The cart is named by the `cart_token` cookie (T7.2a), not by a session, so every view runs
anonymous. DRF views are CSRF-exempt by default, so `CartCsrfAuthentication` enforces the check
on unsafe methods (P7-V18), and a read hands out the `csrftoken` cookie the storefront echoes
back in `X-CSRFToken`.
"""

from typing import Any

from django.db import transaction
from django.middleware.csrf import get_token
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts.identity import get_cart, get_or_create_cart, set_cart_cookie
from apps.carts.models import Cart, CartLine
from apps.carts.serializers import (
    POSTAL_CODE,
    CartFulfillmentSerializer,
    CartLineQuantitySerializer,
    CartLineWriteSerializer,
    CartSerializer,
    cart_totals,
)
from apps.catalog.models import Variant

NOT_FOUND_LINE = {"detail": "No encontramos esa línea del carrito."}


class CartCsrfAuthentication(SessionAuthentication):
    """Never authenticates anyone; only enforces CSRF on POST, PATCH and DELETE."""

    def authenticate(self, request: Request) -> None:
        self.enforce_csrf(request)
        return None


class CartCsrfAuthenticationScheme(OpenApiAuthenticationExtension):
    """Documents the CSRF header in the OpenAPI schema."""

    target_class = CartCsrfAuthentication
    name = "csrfToken"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "header", "name": "X-CSRFToken"}


class CartView(APIView):
    authentication_classes = [CartCsrfAuthentication]
    permission_classes = [AllowAny]

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @staticmethod
    def reply(
        cart: Cart,
        created: bool = False,
        code: int = status.HTTP_200_OK,
        postal_code: str | None = None,
    ) -> Response:
        data = CartSerializer(cart, context={"postal_code": postal_code}).data
        response = Response(data, status=code)
        if created:
            set_cart_cookie(response, cart)
        return response

    @staticmethod
    def touch(cart: Cart) -> None:
        """Line changes count as activity for the stale-cart purge (T7.8)."""
        cart.save(update_fields=["updated_at"])


class CartDetailView(CartView):
    @staticmethod
    def requested_postal_code(request: Request) -> str | None:
        """The optional `postal_code` query parameter; a malformed one is a 400."""
        value = request.query_params.get("postal_code")
        if value is not None and not POSTAL_CODE.fullmatch(value):
            raise ValidationError(
                {"postal_code": ["El código postal debe tener 5 dígitos."]}
            )
        return value

    @extend_schema(
        operation_id="cart_retrieve",
        parameters=[
            OpenApiParameter(
                "postal_code",
                str,
                description="With a delivery cart, quotes shipping to this 5-digit code.",
            )
        ],
        responses={
            200: CartSerializer,
            400: OpenApiResponse(
                description="The postal code is malformed or not in the dataset."
            ),
        },
    )
    def get(self, request: Request) -> Response:
        """An unknown or missing token reads as an empty cart; a read never creates one."""
        get_token(request)  # the storefront reads `csrftoken` before its first write
        cart = get_cart(request)
        if cart is None:
            return Response(
                {
                    "fulfillment_method": None,
                    "lines": [],
                    "shipping_quote": None,
                    "totals": cart_totals([]),
                }
            )
        return self.reply(cart, postal_code=self.requested_postal_code(request))


class CartLineListView(CartView):
    @extend_schema(
        operation_id="cart_lines_create",
        request=CartLineWriteSerializer,
        responses={
            200: CartSerializer,
            201: CartSerializer,
            400: OpenApiResponse(
                description="Quantity outside 1 to 99, or an unknown, inactive or archived variant."
            ),
            403: OpenApiResponse(description="The CSRF token is missing or wrong."),
        },
    )
    def post(self, request: Request) -> Response:
        """Upsert: a variant already in the cart takes the new quantity.

        Quantity is checked against the 1 to 99 bound, and the variant must be sellable (P7-V11).
        Stock is reported on read, never enforced here, so the cart never silently changes a
        quantity (T7.4).
        """
        data = CartLineWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        variant = Variant.objects.get(
            public_id=data.validated_data["variant_public_id"]
        )
        with transaction.atomic():
            cart, created_cart = get_or_create_cart(request)
            _, created_line = CartLine.objects.update_or_create(
                cart=cart,
                variant=variant,
                defaults={"quantity": data.validated_data["quantity"]},
            )
            self.touch(cart)
        return self.reply(
            cart,
            created=created_cart,
            code=status.HTTP_201_CREATED if created_line else status.HTTP_200_OK,
        )


class CartLineDetailView(CartView):
    """A line is found only inside the request's own cart, so another cart's id is a 404."""

    def own_line(self, request: Request, line_id: int) -> tuple[Cart, CartLine] | None:
        cart = get_cart(request)
        if cart is None:
            return None
        line = cart.lines.filter(pk=line_id).first()
        return None if line is None else (cart, line)

    @extend_schema(
        operation_id="cart_lines_update",
        request=CartLineQuantitySerializer,
        responses={
            200: CartSerializer,
            400: OpenApiResponse(description="Quantity outside 1 to 99."),
            403: OpenApiResponse(description="The CSRF token is missing or wrong."),
            404: OpenApiResponse(description="The line is not in this cart."),
        },
    )
    def patch(self, request: Request, line_id: int) -> Response:
        data = CartLineQuantitySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        found = self.own_line(request, line_id)
        if found is None:
            return Response(NOT_FOUND_LINE, status=status.HTTP_404_NOT_FOUND)
        cart, line = found
        line.quantity = data.validated_data["quantity"]
        line.save(update_fields=["quantity"])
        self.touch(cart)
        return self.reply(cart)

    @extend_schema(
        operation_id="cart_lines_destroy",
        responses={
            200: CartSerializer,
            403: OpenApiResponse(description="The CSRF token is missing or wrong."),
            404: OpenApiResponse(description="The line is not in this cart."),
        },
    )
    def delete(self, request: Request, line_id: int) -> Response:
        found = self.own_line(request, line_id)
        if found is None:
            return Response(NOT_FOUND_LINE, status=status.HTTP_404_NOT_FOUND)
        cart, line = found
        line.delete()
        self.touch(cart)
        return self.reply(cart)


class CartFulfillmentView(CartView):
    @extend_schema(
        operation_id="cart_fulfillment_set",
        request=CartFulfillmentSerializer,
        responses={
            200: CartSerializer,
            400: OpenApiResponse(
                description="The method is not `delivery`, or the postal code is malformed or unknown."
            ),
            403: OpenApiResponse(description="The CSRF token is missing or wrong."),
        },
    )
    def post(self, request: Request) -> Response:
        """R1 accepts `delivery` only. The quote is computed before anything is saved, so an
        unknown postal code is a 400 that leaves the cart as it was (P7-V09)."""
        data = CartFulfillmentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            cart, created = get_or_create_cart(request)
            cart.fulfillment_method = data.validated_data["method"]
            cart.save(update_fields=["fulfillment_method", "updated_at"])
            return self.reply(
                cart, created=created, postal_code=data.validated_data["postal_code"]
            )
