from django.urls import path

from apps.payments.api.v1.views import (
    ProductAPIView,
    CreatePaymentView,
)

urlpatterns = [
    path("", ProductAPIView.as_view(), name="product"),
    path("buy/", CreatePaymentView.as_view(), name="product-buy"),
]
