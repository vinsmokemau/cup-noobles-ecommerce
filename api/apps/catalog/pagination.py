"""Cursor pagination for the public catalog (SPEC.md T5.1, P5-V12)."""

from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.fields import BooleanField
from rest_framework.pagination import CursorPagination


class CatalogCursorPagination(CursorPagination):
    """Newest rows first on `id`: unique and never changed, so a walk sees each product once
    even when a product is published midway (a publish moves nothing already passed).
    """

    ordering = "-id"
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 48

    def get_ordering(self, request, queryset, view):
        # Featured products keep the owner's order (G28); `id` makes it unique for the cursor.
        if request.query_params.get("featured") in BooleanField.TRUE_VALUES:
            return ("featured_position", "id")
        return super().get_ordering(request, queryset, view)

    def decode_cursor(self, request):
        try:
            return super().decode_cursor(request)
        except NotFound as error:
            raise ValidationError({self.cursor_query_param: [error.detail]}) from error
