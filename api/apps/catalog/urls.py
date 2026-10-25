from django.urls import path

from apps.catalog import views

urlpatterns = [
    path("products/", views.ProductListView.as_view(), name="catalog-products"),
    path(
        "products/<str:slug>/",
        views.ProductDetailView.as_view(),
        name="catalog-product",
    ),
    path("categories/", views.CategoryTreeView.as_view(), name="catalog-categories"),
    path("search/", views.SearchView.as_view(), name="catalog-search"),
]
