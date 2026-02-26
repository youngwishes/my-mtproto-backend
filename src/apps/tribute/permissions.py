import hashlib
import hmac

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class IsTributeSign(BasePermission):
    def has_permission(self, request, view):
        if request.method != "POST":
            return True

        signature = request.headers.get("Trbt-Signature")
        if not signature:
            raise PermissionDenied("Signature verification failed")

        computed_hmac = hmac.new(
            key=settings.TRIBUTE_API_KEY.encode("utf-8"),
            msg=request.body,
            digestmod=hashlib.sha256,
        )

        if not hmac.compare_digest(signature, computed_hmac.hexdigest()):
            raise PermissionDenied("Signature verification failed")

        return True
