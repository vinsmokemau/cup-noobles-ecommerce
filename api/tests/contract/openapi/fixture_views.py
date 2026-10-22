"""Two views that give the fuzz runner something to exercise (self-test only)."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView


class PingSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class PingView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(responses=PingSerializer)
    def get(self, request):
        return Response({"ok": True})


class BrokenView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(responses=PingSerializer)
    def get(self, request):
        return Response({"ok": "not-a-boolean"})
