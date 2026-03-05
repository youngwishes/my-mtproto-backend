from django.core.management import BaseCommand
from datetime import timedelta
from apps.vds.models import MTPRotoKey


class Command(BaseCommand):
    def handle(self, *args, **options):
        for key in MTPRotoKey.objects.all():
            key.expired_date = key.created_at + timedelta(days=30)
            key.save(update_fields=["expired_date"])
