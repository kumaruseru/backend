"""Store Catalog - Application Services."""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from django.db import transaction
from django.db.models import F
from django.core.cache import cache
from django.utils import timezone

from apps.common.core.exceptions import NotFoundError, ValidationError
from .models import Category, Brand, Product, ProductImage, ProductStat

logger = logging.getLogger('apps.catalog')


class CatalogService:
    @staticmethod
    def get_product_by_slug(slug: str, increment_view: bool = True) -> Product:
        try:
            product = Product.objects.select_related('category', 'brand').prefetch_related('images', 'tags').get(slug=slug, is_active=True)
            if increment_view:
                CatalogService.increment_product_view_count(product)
            return product
        except Product.DoesNotExist:
            raise NotFoundError(message='Product not found')

    @staticmethod
    def increment_product_view_count(product: Product):
        cache_key = f'product_views:{product.pk}'
        try:
            new_count = cache.incr(cache_key)
            if new_count % 10 == 0:
                ProductStat.objects.filter(product_id=product.pk).update(view_count=F('view_count') + 10)
                cache.set(cache_key, 0, timeout=3600)
        except (ValueError, TypeError):
            cache.set(cache_key, 1, timeout=3600)
            ProductStat.objects.get_or_create(product_id=product.pk)
            ProductStat.objects.filter(product_id=product.pk).update(view_count=F('view_count') + 1)

    @staticmethod
    def increment_product_sold_count(product_id: UUID, quantity: int = 1):
        ProductStat.objects.get_or_create(product_id=product_id)
        ProductStat.objects.filter(product_id=product_id).update(sold_count=F('sold_count') + quantity)

    @staticmethod
    @transaction.atomic
    def create_product(data: dict, images: list = None) -> Product:
        tags = data.pop('tags', [])
        product = Product.objects.create(**data)
        if tags:
            product.tags.set(tags)
        if images:
            for i, img_data in enumerate(images):
                ProductImage.objects.create(
                    product=product,
                    image=img_data.get('image'),
                    alt_text=img_data.get('alt_text', ''),
                    is_primary=i == 0,
                    sort_order=i
                )
        logger.info(f"Product created: {product.id} - {product.name}")
        return product

    @staticmethod
    @transaction.atomic
    def update_product(product: Product, data: dict) -> Product:
        tags = data.pop('tags', None)
        for field, value in data.items():
            setattr(product, field, value)
        product.save()
        if tags is not None:
            product.tags.set(tags)
        logger.info(f"Product updated: {product.id}")
        return product

    @staticmethod
    @transaction.atomic
    def bulk_update_products(product_ids: list, updates: dict) -> int:
        count = Product.objects.filter(id__in=product_ids).update(**updates)
        logger.info(f"Bulk updated {count} products")
        return count

    @staticmethod
    def get_catalog_statistics() -> dict:
        now = timezone.now()
        last_30_days = now - timezone.timedelta(days=30)
        products = Product.objects.all()
        return {
            'total_products': products.count(),
            'active_products': products.filter(is_active=True).count(),
            'on_sale': products.filter(sale_price__isnull=False, sale_price__gt=0).count(),
            'featured': products.filter(is_featured=True).count(),
            'new_this_month': products.filter(created_at__gte=last_30_days).count(),
            'total_categories': Category.objects.filter(is_active=True).count(),
            'total_brands': Brand.objects.filter(is_active=True).count(),
        }
