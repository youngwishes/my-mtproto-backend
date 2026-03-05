from django.urls import path

from apps.users.api.v1.views import CreateFirstFreeLinkView
from apps.users.api.v1.views import CheckFirstFreeLinkView

urlpatterns = [
    path("first-free-link/", CreateFirstFreeLinkView.as_view(), name="first-free-link"),
    path("check-first-free-link/", CheckFirstFreeLinkView.as_view(), name="check-first-free-link"),
]
