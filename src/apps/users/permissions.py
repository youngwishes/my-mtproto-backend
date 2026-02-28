from django.conf import settings
from rest_framework.permissions import BasePermission


class BotAuthToken(BasePermission):
    def has_permission(self, request, view):
        return request.headers.get("Bot-Auth-Token") == settings.BOT_AUTH_TOKEN
