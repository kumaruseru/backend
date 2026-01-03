"""Users Social App Configuration."""
from django.apps import AppConfig


class SocialConfig(AppConfig):
    """Social OAuth app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.social'
    label = 'social'
    verbose_name = 'Social Authentication'
