from django.urls import path

from apps.users.api.v1.views import FirstMonthFreeView

urlpatterns = [
    path("first-month-free/", FirstMonthFreeView.as_view(), name="first-month-free")
]
