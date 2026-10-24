"""Case-insensitive text columns (`citext`, spec/schema.sql).

Django 5.2 removed its own `CITextField`, so these keep the column type the schema names.
"""

from django.db import models


class CITextField(models.TextField):
    def db_type(self, connection) -> str:
        return "citext"


class CIEmailField(models.EmailField):
    def db_type(self, connection) -> str:
        return "citext"


class FixedCharField(models.CharField):
    """`char(n)`, for the schema's `state_code` and `postal_code` columns."""

    def db_type(self, connection) -> str:
        return f"char({self.max_length})"
