"""Store Reviews App Configuration."""
from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.reviews'
    label = 'reviews'
    verbose_name = 'Product Reviews'
