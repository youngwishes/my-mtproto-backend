from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "apps.users"

    def ready(self) -> None:
        import apps.users.services  # noqa: F401
