from django.contrib.auth.models import AbstractUser
from django.db import models


class SystemUser(AbstractUser):
    first_month_free_used = models.BooleanField("бесплатный месяц использован", default=False)
