"""Common Locations App Configuration."""
from django.apps import AppConfig


class LocationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common.locations'
    label = 'locations'
    verbose_name = 'Administrative Units'

    def ready(self):
        try:
            from . import signals  # noqa
        except ImportError:
            pass
