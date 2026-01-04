"""
Store Catalog - Celery Tasks.

Periodic tasks for catalog maintenance:
- Sync view counts from Redis to DB
- Update effective prices for expired sales
"""
import logging
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('apps.catalog.tasks')


@shared_task(bind=True, max_retries=1)
def sync_view_counts_to_db(self):
    """
    Sync view counts from Redis to Database.
    
    Run every 5-10 minutes via Celery Beat.
    This reduces DB writes and row locking during high traffic.
    """
    from .models import Product
    
    # Get all view count keys from Redis
    keys_pattern = 'product_views:*'
    
    try:
        # Get Redis client from cache
        redis_client = cache.client.get_client()
        keys = redis_client.keys(keys_pattern)
        
        if not keys:
            logger.info("No view counts to sync")
            return 0
        
        updates = []
        for key in keys:
            try:
                product_id = key.decode().split(':')[1]
                count = int(redis_client.get(key) or 0)
                
                if count > 0:
                    updates.append((product_id, count))
                    
            except (ValueError, IndexError):
                continue
        
        if not updates:
            return 0
        
        # Bulk update DB
        synced_count = 0
        with transaction.atomic():
            for product_id, count in updates:
                updated = Product.objects.filter(pk=product_id).update(
                    view_count=models.F('view_count') + count
                )
                if updated:
                    synced_count += 1
                    # Reset Redis counter
                    redis_client.delete(f'product_views:{product_id}')
        
        logger.info(f"Synced view counts for {synced_count} products")
        return synced_count
        
    except Exception as e:
        logger.exception(f"Failed to sync view counts: {e}")
        return 0


@shared_task(bind=True, max_retries=1)
def update_expired_sale_prices(self):
    """
    Update effective_price for products with expired sales.
    
    Run hourly via Celery Beat.
    """
    from .models import Product
    from django.db import models
    
    now = timezone.now()
    
    # Find products with expired sales
    expired_sales = Product.objects.filter(
        sale_end__lt=now,
        sale_price__isnull=False,
        sale_price__gt=0
    ).exclude(
        effective_price=models.F('price')
    )
    
    updated_count = 0
    for product in expired_sales.iterator():
        product.effective_price = product.price
        product.save(update_fields=['effective_price'])
        updated_count += 1
    
    if updated_count > 0:
        logger.info(f"Updated effective_price for {updated_count} products with expired sales")
    
    return updated_count


@shared_task(bind=True, max_retries=1)
def activate_scheduled_sales(self):
    """
    Activate sales that have just started.
    
    Run every 5 minutes via Celery Beat.
    """
    from .models import Product
    from django.db import models
    
    now = timezone.now()
    five_mins_ago = now - timezone.timedelta(minutes=5)
    
    # Find products with sales that just started
    starting_sales = Product.objects.filter(
        sale_start__lte=now,
        sale_start__gt=five_mins_ago,
        sale_price__isnull=False,
        sale_price__gt=0,
        sale_price__lt=models.F('price')
    ).exclude(
        effective_price=models.F('sale_price')
    )
    
    updated_count = 0
    for product in starting_sales.iterator():
        product.effective_price = product.sale_price
        product.save(update_fields=['effective_price'])
        updated_count += 1
    
    if updated_count > 0:
        logger.info(f"Activated sales for {updated_count} products")
    
    return updated_count
