from django.urls import path

from apps.tribute.api.views.tribute_webhook import TributeWebhookView

urlpatterns = [
    path("webhook/", TributeWebhookView.as_view(), name="tribute-webhook"),
]
