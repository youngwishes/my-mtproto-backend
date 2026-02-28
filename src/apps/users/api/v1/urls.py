from django.urls import path

from apps.users.api.v1.views import CreateFirstMonthFreeView
from apps.users.api.v1.views import CheckFirstMonthFreeView

urlpatterns = [
    path("first-month-free/", CreateFirstMonthFreeView.as_view(), name="first-month-free"),
    path("check-first-month-free/", CheckFirstMonthFreeView.as_view(), name="check-first-month-free"),
]
