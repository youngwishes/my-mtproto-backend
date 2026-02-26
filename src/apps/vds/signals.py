from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.vds.models import MTPRotoKey
from apps.vds.services import get_remove_user_key_service


@receiver(pre_save, sender=MTPRotoKey)
def track_product_activation(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.is_active == instance.is_active:
                return
            if instance.is_active:
                return
            user = getattr(instance, "user", None)
            if not user:
                return
            username = getattr(user, "username", None)
            if not username:
                return
            with transaction.atomic():
                keys = MTPRotoKey.objects.filter(pk=instance.pk)
                get_remove_user_key_service()(keys=keys)
                keys.update(was_deleted=True)

        except sender.DoesNotExist:
            pass
