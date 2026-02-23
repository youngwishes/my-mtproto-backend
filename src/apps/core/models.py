from django.db import models

class ActiveQuerySet(models.QuerySet):
    def active(self) -> "ActiveQuerySet":
        return self.filter(is_active=True)


class BaseDjangoModel(models.Model):
    is_active = models.BooleanField("активность", default=True)
    created_at = models.DateTimeField("дата создания", auto_now_add=True, null=True)
    updated_at = models.DateTimeField("дата обновления", auto_now=True, null=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        abstract = True
