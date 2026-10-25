"""P5-V05: full-text search with a trigram fallback (T5.1)."""

import pytest

pytestmark = pytest.mark.django_db

URL = "/api/catalog/search/"


def search(api_client, q):
    response = api_client.get(URL, {"q": q})
    assert response.status_code == 200
    return [row["slug"] for row in response.json()]


def test_p5_v05_fulltext_and_trigram(api_client, search_corpus):
    exact = search(api_client, "nendoroid zelda")
    typo = search(api_client, "nendorid zelda")

    assert search_corpus.by_name.slug in exact
    assert search_corpus.by_name.slug in typo
    assert search_corpus.unrelated.slug not in exact
    assert search_corpus.unrelated.slug not in typo


def test_trigram_fallback_finds_a_typo_the_stemmer_cannot(api_client, search_corpus):
    # "nendorid" stems like "nendoroid" in Spanish, so it proves nothing; a dropped letter does.
    assert search(api_client, "nendroid zelda") == [search_corpus.by_name.slug]


def test_p5_v05_a_name_match_ranks_above_a_description_match(api_client, search_corpus):
    assert search(api_client, "nendoroid zelda") == [
        search_corpus.by_name.slug,
        search_corpus.by_description.slug,
    ]


def test_search_uses_spanish_stemming(api_client, search_corpus):
    assert search(api_client, "sobre") == [search_corpus.unrelated.slug]


def test_search_never_returns_a_draft(api_client, search_corpus):
    assert search_corpus.draft.slug not in search(api_client, "zelda borrador")


def test_search_with_no_match_is_empty(api_client, search_corpus):
    assert search(api_client, "xylofono") == []


def test_search_punctuation_is_harmless(api_client, search_corpus):
    assert search(api_client, "'; DROP TABLE product;--") == []
    assert search(api_client, '"nendoroid zelda" -pokemon') == [
        search_corpus.by_name.slug,
        search_corpus.by_description.slug,
    ]


@pytest.mark.parametrize("query", [{}, {"q": ""}, {"q": "x" * 101}])
def test_search_needs_a_reasonable_q(api_client, query):
    assert api_client.get(URL, query).status_code == 400


def test_list_q_filters_with_the_same_matching(api_client, search_corpus):
    response = api_client.get("/api/catalog/products/", {"q": "nendroid zelda"})

    assert [r["slug"] for r in response.json()["results"]] == [
        search_corpus.by_name.slug
    ]
