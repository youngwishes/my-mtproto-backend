from django.urls import path

from apps.payments.api.v1.views import (
    ActivateGiftCertificateView,
    CreatePaymentView,
    CreateGiftCertificateView,
    ProductAPIView,
)

urlpatterns = [
    path("", ProductAPIView.as_view(), name="product"),
    path("products/<str:code>/", ProductAPIView.as_view(), name="product-by-code"),
    path("buy/", CreatePaymentView.as_view(), name="product-buy"),
    path(
        "gift-certificates/buy/",
        CreateGiftCertificateView.as_view(),
        name="gift-certificate-buy",
    ),
    path(
        "gift-certificates/activate/",
        ActivateGiftCertificateView.as_view(),
        name="gift-certificate-activate",
    ),
]
