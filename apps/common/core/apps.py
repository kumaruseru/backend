"""Common Core App Configuration."""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Core infrastructure app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common.core'
    label = 'core'
    verbose_name = 'Core Infrastructure'