from django.apps import AppConfig


class VdsConfig(AppConfig):
    name = 'apps.vds'

    def ready(self):
        from apps.vds import signals
