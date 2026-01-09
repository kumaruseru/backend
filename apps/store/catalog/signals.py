"""Store Catalog - Signals for cache invalidation."""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

logger = logging.getLogger('apps.catalog')


def should_index():
    return getattr(settings, 'USE_MEILISEARCH', False)


@receiver(post_save, sender='catalog.Product')
def index_product_on_save(sender, instance, created, **kwargs):
    try:
        from .selectors import CatalogSelector
        CatalogSelector.invalidate_product_caches(product_id=str(instance.id), product_slug=instance.slug)
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    if not should_index():
        return
    if not instance.is_active:
        try:
            from .search import MeilisearchGateway
            MeilisearchGateway.delete_product(instance.id)
        except Exception as e:
            logger.warning(f"Failed to remove inactive product from index: {e}")
        return
    try:
        from .search import MeilisearchGateway
        MeilisearchGateway.index_product(instance)
    except Exception as e:
        logger.warning(f"Failed to index product on save: {e}")


@receiver(post_delete, sender='catalog.Product')
def delete_product_from_index(sender, instance, **kwargs):
    if not should_index():
        return
    try:
        from .search import MeilisearchGateway
        MeilisearchGateway.delete_product(instance.id)
    except Exception as e:
        logger.warning(f"Failed to delete product from index: {e}")


@receiver(post_save, sender='catalog.Category')
def invalidate_category_cache(sender, instance, **kwargs):
    try:
        from .selectors import CatalogSelector
        CatalogSelector.invalidate_category_caches()
    except Exception as e:
        logger.warning(f"Failed to invalidate category cache: {e}")


@receiver(post_save, sender='catalog.Brand')
def invalidate_brand_cache(sender, instance, **kwargs):
    try:
        from .selectors import CatalogSelector
        CatalogSelector.invalidate_category_caches()
    except Exception as e:
        logger.warning(f"Failed to invalidate brand cache: {e}")
