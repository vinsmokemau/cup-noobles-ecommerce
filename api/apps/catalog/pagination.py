"""Cursor pagination for the public catalog (SPEC.md T5.1, P5-V12)."""

from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import CursorPagination


class CatalogCursorPagination(CursorPagination):
    """Newest rows first on `id`: unique and never changed, so a walk sees each product once
    even when a product is published midway (a publish moves nothing already passed).
    """

    ordering = "-id"
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 48

    def decode_cursor(self, request):
        try:
            return super().decode_cursor(request)
        except NotFound as error:
            raise ValidationError({self.cursor_query_param: [error.detail]}) from error
