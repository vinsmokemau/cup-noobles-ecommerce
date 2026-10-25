from django.urls import path

from apps.carts import views

urlpatterns = [
    path("", views.CartDetailView.as_view(), name="cart"),
    path("lines/", views.CartLineListView.as_view(), name="cart-lines"),
    path("lines/<int:line_id>/", views.CartLineDetailView.as_view(), name="cart-line"),
    path("fulfillment/", views.CartFulfillmentView.as_view(), name="cart-fulfillment"),
]
