"""Store Wishlist App Configuration."""
from django.apps import AppConfig


class WishlistConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.wishlist'
    label = 'wishlist'
    verbose_name = 'Wishlists'
