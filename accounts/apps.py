from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        # Import signals so the @receiver decorators get registered.
        # Importing inside ready() avoids circular-import issues during app loading.
        from . import signals  # noqa: F401
