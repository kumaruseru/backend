from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class WishlistConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.wishlist'
    verbose_name = _('Wishlist')

    def ready(self):
        try:
            import apps.store.wishlist.signals
        except ImportError:
            pass
