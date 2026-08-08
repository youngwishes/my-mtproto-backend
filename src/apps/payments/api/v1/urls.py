from __future__ import annotations

from django.urls import path

from apps.payments.api.v1.views import (
    ActivateGiftCertificateView,
    CreateCryptoInvoiceView,
    CryptoPayWebhookView,
    CreatePaymentView,
    CreatePlategaInvoiceView,
    CreateGiftCertificateView,
    ProductAPIView,
)

urlpatterns = [
    path("", ProductAPIView.as_view(), name="product"),
    path("products/<str:code>/", ProductAPIView.as_view(), name="product-by-code"),
    path("buy/", CreatePaymentView.as_view(), name="product-buy"),
    path(
        "crypto/invoices/",
        CreateCryptoInvoiceView.as_view(),
        name="crypto-invoice-create",
    ),
    path(
        "platega/invoices/",
        CreatePlategaInvoiceView.as_view(),
        name="platega-invoice-create",
    ),
    path(
        "crypto/webhooks/<str:webhook_secret>/",
        CryptoPayWebhookView.as_view(),
        name="crypto-pay-webhook",
    ),
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
