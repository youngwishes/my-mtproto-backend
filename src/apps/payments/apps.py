from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = "apps.payments"

    def ready(self) -> None:
        import apps.payments.services  # noqa: F401
