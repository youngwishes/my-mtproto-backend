from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from apps.vds.models import MTPRotoKey


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_user_key_service

    one_month_ago = timezone.now() - timedelta(days=30)
    queryset = MTPRotoKey.objects.active().filter(
        created_at__lt=one_month_ago
    )
    service = get_remove_user_key_service()
    service(keys=queryset)
