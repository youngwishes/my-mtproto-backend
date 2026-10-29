from __future__ import annotations

from django.db.models import TextChoices


class ProxyMode(TextChoices):
    FAKE_TLS = "fake_tls", "FakeTLS"
    WEB = "web", "WEB"
