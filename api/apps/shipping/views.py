"""The postal-code lookup (SPEC.md T6.6): anonymous, read-only, GET only."""

import re
from typing import Any

from django.utils.cache import patch_cache_control
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import providers

POSTAL_CODE_MAX_AGE = 60 * 60 * 24  # seconds; the dataset changes only on a manual load
POSTAL_CODE = re.compile(r"[0-9]{5}")


class PostalCodeSerializer(serializers.Serializer):
    state_code = serializers.CharField()
    state_name = serializers.CharField()
    municipality = serializers.CharField()
    neighborhoods = serializers.ListField(child=serializers.CharField())


class PostalCodeView(APIView):
    """`GET /api/postal-codes/{cp}/`: 400 for a malformed code, 404 for an unknown one."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="postal_codes_retrieve",
        responses={
            200: PostalCodeSerializer,
            400: OpenApiResponse(description="The postal code is not 5 digits."),
            404: OpenApiResponse(description="The postal code is not in the dataset."),
        },
    )
    def get(self, request: Request, cp: str) -> Response:
        if not POSTAL_CODE.fullmatch(cp):
            return Response(
                {"detail": "El código postal debe tener 5 dígitos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        info = providers.postal_code_lookup().lookup(cp)
        if info is None:
            return Response(
                {"detail": "Código postal no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "state_code": info.state_code,
                "state_name": info.state_name,
                "municipality": info.municipality,
                "neighborhoods": list(info.neighborhoods),
            }
        )

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            patch_cache_control(response, public=True, max_age=POSTAL_CODE_MAX_AGE)
        return response
