"""Commerce Returns App Configuration."""
from django.apps import AppConfig


class ReturnsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.returns'
    label = 'returns'
    verbose_name = 'Returns & Refunds'
