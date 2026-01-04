"""
Catalog Signals.

Auto-index products to Meilisearch on save/delete.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

logger = logging.getLogger('apps.catalog')


def should_index():
    """Check if Meilisearch indexing is enabled."""
    return getattr(settings, 'USE_MEILISEARCH', True)


@receiver(post_save, sender='catalog.Product')
def index_product_on_save(sender, instance, created, **kwargs):
    """Index product to Meilisearch on save."""
    if not should_index():
        return
    
    # Only index active products
    if not instance.is_active:
        # If product became inactive, remove from index
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
    """Remove product from Meilisearch on delete."""
    if not should_index():
        return
    
    try:
        from .search import MeilisearchGateway
        MeilisearchGateway.delete_product(instance.id)
    except Exception as e:
        logger.warning(f"Failed to delete product from index: {e}")
