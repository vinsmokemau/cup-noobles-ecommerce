"""Operational endpoints (SPEC.md §4.1, ADR-0028)."""

from django.db import OperationalError, connection
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

HealthSerializer = inline_serializer("Health", {"db": serializers.CharField()})


class HealthView(APIView):
    """`GET /api/health/`: the database answers `SELECT 1`, or the service is unhealthy."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                HealthSerializer, description="The database is reachable."
            ),
            503: OpenApiResponse(
                HealthSerializer, description="The database is unreachable."
            ),
        },
    )
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except OperationalError:
            return Response(
                {"db": "unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response({"db": "ok"})
