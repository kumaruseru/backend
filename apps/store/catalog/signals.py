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
    """Index product to Meilisearch on save and invalidate caches."""
    # Invalidate selector caches
    try:
        from .selectors import CatalogSelector
        CatalogSelector.invalidate_product_caches(
            product_id=str(instance.id),
            product_slug=instance.slug
        )
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")
    
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


# ==================== Stock Sync ====================

@receiver(post_save, sender='inventory.StockItem')
def reindex_product_on_stock_change(sender, instance, **kwargs):
    """
    Re-index product when stock changes.
    
    This ensures in_stock filter stays accurate in Meilisearch.
    """
    if not should_index():
        return
    
    try:
        from .search import MeilisearchGateway
        from .models import Product
        
        # Fetch full product with relations for indexing
        product = Product.objects.select_related(
            'category', 'brand'
        ).prefetch_related('images', 'tags').get(id=instance.product_id)
        
        if product.is_active:
            MeilisearchGateway.index_product(product)
            logger.debug(f"Re-indexed product {product.id} after stock change")
    except Exception as e:
        logger.warning(f"Failed to re-index product after stock change: {e}")

