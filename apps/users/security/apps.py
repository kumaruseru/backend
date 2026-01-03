"""Users Security App Configuration."""
from django.apps import AppConfig


class SecurityConfig(AppConfig):
    """User security and 2FA app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.security'
    label = 'security'
    verbose_name = 'Security & 2FA'
