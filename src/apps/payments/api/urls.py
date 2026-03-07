from django.urls import path, include

urlpatterns = [
    path("v1/payments/", include("apps.payments.api.v1.urls")),
]
