"""Product search (SPEC.md T5.1): full-text over `product.search_tsv`, with a trigram fallback.

`search_tsv` is a generated column that lives in the migration's `RunSQL`, so the model has no
field for it; `SEARCH_VECTOR` names the column. A product matches when its vector matches the
query, or when the query is close enough to part of its name to be a typo.
"""

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVectorField,
    TrigramWordSimilarity,
)
from django.db.models import BooleanField, Func, Q, QuerySet
from django.db.models.expressions import RawSQL
from django.db.models.lookups import GreaterThan

from apps.catalog.models import Product

SEARCH_CONFIG = "spanish"

# `word_similarity(q, name)`: how much of the query's trigrams one stretch of the name covers.
# One wrong letter in "nendoroid" still scores above this; unrelated words do not.
TRIGRAM_THRESHOLD = 0.5

SEARCH_VECTOR = RawSQL('"product"."search_tsv"', (), output_field=SearchVectorField())


class TextMatch(Func):
    """`vector @@ query`, so Postgres can use the GIN index on `search_tsv`."""

    arg_joiner = " @@ "
    template = "(%(expressions)s)"
    output_field = BooleanField()


def _query(text: str) -> SearchQuery:
    return SearchQuery(text, config=SEARCH_CONFIG, search_type="websearch")


def _name_closeness(text: str) -> TrigramWordSimilarity:
    return TrigramWordSimilarity(text, "name")


def matching(queryset: QuerySet[Product], text: str) -> QuerySet[Product]:
    """Products whose text matches `text` or whose name is close to it."""
    return queryset.filter(
        Q(TextMatch(SEARCH_VECTOR, _query(text)))
        | Q(GreaterThan(_name_closeness(text), TRIGRAM_THRESHOLD))
    )


def ranked(queryset: QuerySet[Product], text: str) -> QuerySet[Product]:
    """`matching`, best first: text rank (a name outweighs a description), then name closeness."""
    return (
        matching(queryset, text)
        .annotate(
            rank=SearchRank(SEARCH_VECTOR, _query(text)),
            name_similarity=_name_closeness(text),
        )
        .order_by("-rank", "-name_similarity", "-id")
    )
