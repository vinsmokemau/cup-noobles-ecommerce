"""The public catalog API (SPEC.md T5.1): read-only, anonymous, GET only.

Only `active` products and `is_active` variants are visible. A list never costs a query per row:
the view prefetches variants (with their availability annotated, T5.3) and images.
"""

from typing import Any

from django.contrib.auth import get_user
from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils.cache import patch_cache_control
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import search
from apps.catalog.availability import with_available_units
from apps.catalog.facets import build_facets
from apps.catalog.filters import ProductQuerySerializer, filter_products, parse_query
from apps.catalog.models import (
    Category,
    Product,
    ProductCategory,
    ProductImage,
    Variant,
)
from apps.catalog.pagination import CatalogCursorPagination
from apps.catalog.serializers import (
    CategoryNodeSerializer,
    FacetsSerializer,
    ProductCardSerializer,
    ProductDetailSerializer,
)
from apps.core.models import SiteSetting

CATALOG_MAX_AGE = 60  # seconds; nothing busts it (T5.6), add-to-cart re-checks stock
RELATED_LIMIT = 8  # products shown under a product page (G28, ADR-0030)
SEARCH_LIMIT = 48

BAD_REQUEST = OpenApiResponse(description="A query parameter is invalid.")
PRELAUNCH = OpenApiResponse(
    inline_serializer("Prelaunch", {"prelaunch": serializers.BooleanField()}),
    description="Pre-launch mode is on and the request is anonymous (G32, ADR-0038).",
)
ATTR_PARAMETER = OpenApiParameter(
    "attr.<key>",
    OpenApiTypes.STR,
    description=(
        "Keeps products whose attribute `<key>` equals the value, for example `attr.linea=Nendoroid`. "
        "`<key>` must be in the `filterable_keys` of a product type (of the `type` filter, when "
        "given); any other key is a 400. The facets endpoint lists the keys and their values."
    ),
)


def public_products(*, detail: bool = False) -> QuerySet[Product]:
    variants = with_available_units(Variant.objects.filter(is_active=True)).order_by(
        "position", "id"
    )
    images = ProductImage.objects.order_by("position", "id")
    prefetches: list[Any] = [
        Prefetch("variants", queryset=variants, to_attr="public_variants")
    ]
    if detail:
        prefetches += [
            Prefetch("images", queryset=images.select_related("variant")),
            Prefetch(
                "categories",
                queryset=Category.objects.filter(is_active=True).order_by(
                    "position", "id"
                ),
                to_attr="public_categories",
            ),
        ]
    else:
        prefetches.append(Prefetch("images", queryset=images))
    return (
        Product.objects.filter(status=Product.Status.ACTIVE)
        .select_related("product_type", "brand", "franchise")
        .prefetch_related(*prefetches)
    )


def related_products(product: Product) -> list[Product]:
    """Active products that share the franchise or a category, newest first (G28)."""
    shared = Q()
    if product.franchise_id is not None:
        shared |= Q(franchise_id=product.franchise_id)
    category_ids = [category.pk for category in product.public_categories]  # type: ignore[attr-defined]
    if category_ids:
        shared |= Q(
            Exists(
                ProductCategory.objects.filter(
                    product=OuterRef("pk"), category__in=category_ids
                )
            )
        )
    if not shared:
        return []
    queryset = public_products().exclude(pk=product.pk).filter(shared)
    return list(queryset.order_by("-id")[:RELATED_LIMIT])


def present_params(request: Request) -> dict[str, str]:
    """The query parameters that carry a value: `?q=` is the same as no `q`."""
    return {key: value for key, value in request.query_params.items() if value != ""}


class PrelaunchActive(Exception):
    """Pre-launch mode is on and the request is not from a staff session."""


class CatalogView:
    """Anonymous and cacheable: a successful response may be kept by the CDN for a minute.

    While pre-launch mode is on (G32, ADR-0038) an anonymous request gets `503 {"prelaunch": true}`
    with `no-store`, and a staff session gets the catalog with `private`, so the CDN never keeps
    the hidden catalog (R-19).
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    prelaunch_staff = False

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)  # type: ignore[misc]
        if SiteSetting.prelaunch_active():
            # DRF authentication is off here and DRF overwrites `request.user` with an anonymous
            # user, so read the logged-in user from the session itself.
            user = get_user(request._request)  # noqa: SLF001
            if not (user.is_authenticated and user.is_active and user.is_staff):
                raise PrelaunchActive
            self.prelaunch_staff = True

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, PrelaunchActive):
            return Response(
                {"prelaunch": True}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return super().handle_exception(exc)  # type: ignore[misc]

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)  # type: ignore[misc]
        if response.status_code == 503 and response.data == {"prelaunch": True}:
            patch_cache_control(response, no_store=True)
        elif self.prelaunch_staff:
            patch_cache_control(response, private=True)
        elif response.status_code == 200:
            patch_cache_control(response, public=True, max_age=CATALOG_MAX_AGE)
        return response


class ProductListView(CatalogView, generics.ListAPIView):
    """`GET /api/catalog/products/`"""

    serializer_class = ProductCardSerializer
    pagination_class = CatalogCursorPagination

    def get_queryset(self) -> QuerySet[Product]:
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        params = parse_query(present_params(self.request))
        return filter_products(public_products(), params)

    @extend_schema(
        operation_id="catalog_products_list",
        parameters=[ProductQuerySerializer, ATTR_PARAMETER],
        responses={
            200: ProductCardSerializer(many=True),
            400: BAD_REQUEST,
            503: PRELAUNCH,
        },
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)


class FacetsView(CatalogView, APIView):
    """`GET /api/catalog/facets/`: the filter values of the products the query matches."""

    @extend_schema(
        operation_id="catalog_facets_retrieve",
        parameters=[ProductQuerySerializer, ATTR_PARAMETER],
        responses={200: FacetsSerializer, 400: BAD_REQUEST, 503: PRELAUNCH},
    )
    def get(self, request: Request) -> Response:
        params = parse_query(present_params(request))
        products = filter_products(
            Product.objects.filter(status=Product.Status.ACTIVE), params
        )
        return Response({"facets": build_facets(products, params)})


class ProductDetailView(CatalogView, APIView):
    """`GET /api/catalog/products/{slug}/`: a draft or archived product is a 404."""

    @extend_schema(
        operation_id="catalog_products_retrieve",
        responses={
            200: ProductDetailSerializer,
            404: OpenApiResponse(description="No active product has this slug."),
            503: PRELAUNCH,
        },
    )
    def get(self, request: Request, slug: str) -> Response:
        product = get_object_or_404(public_products(detail=True), slug=slug)
        product.related_products = related_products(product)  # type: ignore[attr-defined]
        return Response(ProductDetailSerializer(product).data)


class CategoryTreeView(CatalogView, APIView):
    """`GET /api/catalog/categories/`: active categories, nested by parent."""

    @extend_schema(
        operation_id="catalog_categories_list",
        responses={200: CategoryNodeSerializer(many=True), 503: PRELAUNCH},
    )
    def get(self, request: Request) -> Response:
        categories = list(
            Category.objects.filter(is_active=True).order_by("position", "id")
        )
        for category in categories:
            category.active_children = []  # type: ignore[attr-defined]
        by_id = {category.pk: category for category in categories}
        roots = []
        for category in categories:
            if category.parent_id is None:
                roots.append(category)
            elif (
                category.parent_id in by_id
            ):  # a child of an inactive category is hidden
                by_id[category.parent_id].active_children.append(category)  # type: ignore[attr-defined]
        return Response(CategoryNodeSerializer(roots, many=True).data)


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=100)


class SearchView(CatalogView, APIView):
    """`GET /api/catalog/search/?q=`: best match first, at most `SEARCH_LIMIT` products."""

    @extend_schema(
        operation_id="catalog_search_list",
        parameters=[
            OpenApiParameter(
                "q", OpenApiTypes.STR, required=True, description="Words to find."
            )
        ],
        responses={
            200: ProductCardSerializer(many=True),
            400: BAD_REQUEST,
            503: PRELAUNCH,
        },
    )
    def get(self, request: Request) -> Response:
        query = SearchQuerySerializer(data=present_params(request))
        query.is_valid(raise_exception=True)
        products = search.ranked(public_products(), query.validated_data["q"])
        return Response(ProductCardSerializer(products[:SEARCH_LIMIT], many=True).data)
