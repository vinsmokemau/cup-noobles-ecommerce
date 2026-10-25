from django.urls import path

from apps.shipping import views

urlpatterns = [
    path("<str:cp>/", views.PostalCodeView.as_view(), name="postal-code"),
]
