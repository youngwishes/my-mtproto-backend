from django.urls import path, include

urlpatterns = [
    path("v1/users/", include("apps.users.api.v1.urls")),
]
