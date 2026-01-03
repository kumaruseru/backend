"""Users Identity App Configuration."""
from django.apps import AppConfig


class IdentityConfig(AppConfig):
    """User identity and authentication app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.identity'
    label = 'identity'
    verbose_name = 'Identity & Authentication'
    
    def ready(self):
        """Import signals when app is ready."""
        from . import signals  # noqa: F401

