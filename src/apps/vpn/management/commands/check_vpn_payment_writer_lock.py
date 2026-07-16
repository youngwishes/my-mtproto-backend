from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.vpn.factories import get_payment_worker_health_check


class Command(BaseCommand):
    help = "Verify the dedicated worker identity and lifetime lock ownership."

    def handle(self, *args: object, **options: object) -> None:
        if not get_payment_worker_health_check()():
            raise CommandError("VPN payment singleton is not the healthy lock owner")
