"""Commerce Shipping App Configuration."""
from django.apps import AppConfig


class ShippingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.shipping'
    label = 'shipping'
    verbose_name = 'Shipping & Delivery'
