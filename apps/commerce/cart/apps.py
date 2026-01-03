"""Commerce Cart App Configuration."""
from django.apps import AppConfig


class CartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.cart'
    label = 'cart'
    verbose_name = 'Shopping Cart'
