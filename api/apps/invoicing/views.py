"""The CFDI catalogs the checkout's "Quiero factura" section offers (SPEC.md T13.11)."""

from django.utils.cache import patch_cache_control
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invoicing import catalogs

CATALOG_MAX_AGE = 60 * 60  # seconds; the file changes only with a deploy


class CfdiCatalogItemSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class CfdiCatalogsSerializer(serializers.Serializer):
    regimen_fiscal = CfdiCatalogItemSerializer(many=True)
    uso_cfdi = CfdiCatalogItemSerializer(many=True)


class CfdiCatalogsView(APIView):
    """`GET /api/invoicing/cfdi-catalogs/`: anonymous, read-only and cacheable."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="invoicing_cfdi_catalogs_retrieve",
        responses=CfdiCatalogsSerializer,
    )
    def get(self, request: Request) -> Response:
        response = Response(catalogs.public_catalogs())
        patch_cache_control(response, public=True, max_age=CATALOG_MAX_AGE)
        return response
