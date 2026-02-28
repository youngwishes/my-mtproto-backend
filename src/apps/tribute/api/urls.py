from django.urls import path, include

urlpatterns = [
    path("v1/tribute/", include("apps.tribute.api.v1.urls")),
]
