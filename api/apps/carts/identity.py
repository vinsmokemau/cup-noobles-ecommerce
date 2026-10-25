"""Cart identity (T7.2a, ADR-0011): an opaque `cart_token` cookie names the cart.

A request without a valid token has no cart. The cart is created on the first write
(`get_or_create_cart`), and the cookie is set on that response with `set_cart_cookie`.
Reads never create a cart.
"""

import uuid

from django.conf import settings
from django.http import HttpResponseBase
from rest_framework.request import Request

from apps.carts.models import Cart

CART_COOKIE_NAME = "cart_token"
CART_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def get_cart(request: Request) -> Cart | None:
    """The open cart the request's token names, or None.

    A malformed token, an unknown token and the token of a converted cart (one that
    already became an order) are all treated as no token.
    """
    raw = request.COOKIES.get(CART_COOKIE_NAME)
    if not raw:
        return None
    try:
        token = uuid.UUID(raw)
    except ValueError:
        return None
    return Cart.objects.filter(token=token, converted_order__isnull=True).first()


def get_or_create_cart(request: Request) -> tuple[Cart, bool]:
    """The request's cart, creating a new one when it has no valid token."""
    cart = get_cart(request)
    if cart is not None:
        return cart, False
    return Cart.objects.create(), True


def set_cart_cookie(response: HttpResponseBase, cart: Cart) -> None:
    """Attach the `cart_token` cookie: HttpOnly, SameSite=Lax, 30 days.

    `Secure` follows the session cookie, so it is on in production and off in dev and test.
    """
    response.set_cookie(
        CART_COOKIE_NAME,
        str(cart.token),
        max_age=CART_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
