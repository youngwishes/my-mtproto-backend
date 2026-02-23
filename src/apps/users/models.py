from django.contrib.auth.models import AbstractUser
from apps.core import ActiveQuerySet


class SystemUser(AbstractUser):
    email = None

    objects = ActiveQuerySet.as_manager()
