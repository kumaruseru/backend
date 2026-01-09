from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.reviews'
    verbose_name = _('Reviews')

    def ready(self):
        try:
            import apps.store.reviews.signals
        except ImportError:
            pass
