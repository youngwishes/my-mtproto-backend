import hashlib
import hmac
import json
from django.conf import settings


class TributeSignMixin:
    def get_sign_headers(self, payload: dict) -> dict:
        computed_hmac = hmac.new(
            key=settings.TRIBUTE_API_KEY.encode("utf-8"),
            msg=json.dumps(
                payload,
                separators=(",", ":")
            ).encode("utf-8"),
            digestmod=hashlib.sha256,
        )
        return {"Trbt-Signature": computed_hmac.hexdigest(),}
