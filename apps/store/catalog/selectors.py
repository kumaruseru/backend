"""
Store Catalog - Selectors (Read-Only Queries with Caching).

This module contains all READ operations for the catalog.
Following the Selector Pattern to separate read from write logic.

CACHING STRATEGY:
- Category tree: Cache 5 mins (rarely changes)
- Featured/Bestsellers/Sales: Cache 2 mins (changes with data)
- Product detail: Cache 1 min (invalidated on save via signals)
- Search suggestions: No cache (real-time autocomplete)
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from functools import wraps
from django.core.cache import cache
from django.db.models import Q, Min, Max

from apps.common.core.exceptions import NotFoundError
from .models import Category, Brand, Product, ProductTag

logger = logging.getLogger('apps.catalog')


# ==================== Cache Helpers ====================

def cached(key_template: str, timeout: int = 300):
    """
    Decorator for caching selector results.
    
    Args:
        key_template: Cache key template with {arg} placeholders
        timeout: Cache timeout in seconds (default: 5 mins)
    
    Example:
        @cached('catalog:featured:{limit}', timeout=120)
        def get_featured_products(limit: int = 12):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from template and kwargs
            cache_key = key_template.format(**kwargs) if kwargs else key_template
            
            # Try cache first
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return result
            
            # Cache miss - execute query
            logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


class CatalogSelector:
    """
    Read-only queries for catalog data with Redis caching.
    
    All methods are stateless and have no side effects.
    Cache invalidation happens via signals in signals.py.
    """
    
    # ==================== Cache Keys ====================
    
    CACHE_KEYS = {
        'category_tree': 'catalog:category_tree',
        'category_filters': 'catalog:category:{slug}:filters',
        'product_detail': 'catalog:product:{slug}',
        'featured': 'catalog:featured:{limit}',
        'new_arrivals': 'catalog:new_arrivals:{limit}:{days}',
        'bestsellers': 'catalog:bestsellers:{limit}',
        'on_sale': 'catalog:on_sale:{limit}',
        'related': 'catalog:related:{product_id}:{limit}',
        'all_brands': 'catalog:brands:all',
    }
    
    # ==================== Cache Invalidation ====================
    
    @staticmethod
    def invalidate_product_caches(product_id: str = None, product_slug: str = None):
        """Invalidate product-related caches. Called from signals."""
        keys_to_delete = [
            'catalog:featured:*',
            'catalog:new_arrivals:*',
            'catalog:bestsellers:*',
            'catalog:on_sale:*',
        ]
        
        # Specific product cache
        if product_slug:
            cache.delete(f'catalog:product:{product_slug}')
        if product_id:
            cache.delete_pattern(f'catalog:related:{product_id}:*')
        
        # Pattern-based invalidation (if Redis supports it)
        for pattern in keys_to_delete:
            try:
                cache.delete_pattern(pattern)
            except (AttributeError, NotImplementedError):
                # Fallback: delete known keys
                for limit in [8, 12, 20]:
                    cache.delete(f'catalog:featured:{limit}')
                    cache.delete(f'catalog:bestsellers:{limit}')
                    cache.delete(f'catalog:on_sale:{limit}')
                    for days in [7, 14, 30]:
                        cache.delete(f'catalog:new_arrivals:{limit}:{days}')
                break
    
    @staticmethod
    def invalidate_category_caches():
        """Invalidate category-related caches. Called from signals."""
        cache.delete('catalog:category_tree')
        cache.delete('catalog:brands:all')
        # Pattern match for category filters
        try:
            cache.delete_pattern('catalog:category:*:filters')
        except (AttributeError, NotImplementedError):
            pass  # Will expire naturally
    
    # ==================== Categories ====================
    
    @staticmethod
    def get_category_tree() -> List[Category]:
        """Get all active categories with hierarchy. Cached 5 mins."""
        cache_key = 'catalog:category_tree'
        result = cache.get(cache_key)
        
        if result is None:
            result = list(
                Category.objects.filter(is_active=True)
                .select_related('parent')
                .order_by('parent_id', 'sort_order', 'name')
            )
            cache.set(cache_key, result, 300)  # 5 mins
        
        return result
    
    @staticmethod
    def get_category_by_slug(slug: str) -> Category:
        """Get category by slug. Not cached (use get_category_tree for lists)."""
        try:
            return Category.objects.get(slug=slug, is_active=True)
        except Category.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy danh mục')
    
    @staticmethod
    def get_category_filters(category: Category) -> Dict[str, Any]:
        """Get available filters for a category. Cached 3 mins."""
        cache_key = f'catalog:category:{category.slug}:filters'
        result = cache.get(cache_key)
        
        if result is None:
            products = Product.objects.active().filter(
                category_id__in=category.get_all_children_ids()
            )
            
            brands = Brand.objects.filter(
                products__in=products,
                is_active=True
            ).distinct()
            
            price_stats = products.aggregate(
                min_price=Min('price'),
                max_price=Max('price')
            )
            
            tags = ProductTag.objects.filter(
                products__in=products
            ).distinct()
            
            result = {
                'brands': list(brands),
                'price_range': {
                    'min': price_stats['min_price'] or 0,
                    'max': price_stats['max_price'] or 0
                },
                'tags': list(tags),
                'product_count': products.count()
            }
            cache.set(cache_key, result, 180)  # 3 mins
        
        return result
    
    # ==================== Products ====================
    
    @staticmethod
    def get_product_by_slug(slug: str) -> Product:
        """
        Get product by slug. Cached 1 min.
        
        Note: Use CatalogService.get_product_by_slug() if you need 
        to track views (increment_view_count).
        """
        cache_key = f'catalog:product:{slug}'
        result = cache.get(cache_key)
        
        if result is None:
            try:
                result = Product.objects.select_related(
                    'category', 'brand'
                ).prefetch_related(
                    'images', 'tags', 'stock'
                ).get(slug=slug, is_active=True)
                cache.set(cache_key, result, 60)  # 1 min
            except Product.DoesNotExist:
                raise NotFoundError(message='Không tìm thấy sản phẩm')
        
        return result
    
    @staticmethod
    def get_product_by_id(product_id: UUID) -> Product:
        """Get product by ID. Not cached (use slug version for caching)."""
        try:
            return Product.objects.select_related(
                'category', 'brand'
            ).prefetch_related(
                'images', 'tags', 'stock'
            ).get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy sản phẩm')
    
    @staticmethod
    def get_featured_products(limit: int = 12) -> List[Product]:
        """Get featured products. Cached 2 mins."""
        cache_key = f'catalog:featured:{limit}'
        result = cache.get(cache_key)
        
        if result is None:
            result = list(
                Product.objects.featured().select_related(
                    'category', 'brand'
                ).prefetch_related('images')[:limit]
            )
            cache.set(cache_key, result, 120)  # 2 mins
        
        return result
    
    @staticmethod
    def get_new_arrivals(limit: int = 12, days: int = 30) -> List[Product]:
        """Get new arrival products. Cached 2 mins."""
        cache_key = f'catalog:new_arrivals:{limit}:{days}'
        result = cache.get(cache_key)
        
        if result is None:
            result = list(
                Product.objects.new_arrivals(days).select_related(
                    'category', 'brand'
                ).prefetch_related('images').order_by('-created_at')[:limit]
            )
            cache.set(cache_key, result, 120)  # 2 mins
        
        return result
    
    @staticmethod
    def get_bestsellers(limit: int = 12) -> List[Product]:
        """Get bestselling products. Cached 2 mins."""
        cache_key = f'catalog:bestsellers:{limit}'
        result = cache.get(cache_key)
        
        if result is None:
            result = list(
                Product.objects.active().filter(
                    is_bestseller=True
                ).select_related(
                    'category', 'brand'
                ).prefetch_related('images').order_by('-sold_count')[:limit]
            )
            cache.set(cache_key, result, 120)  # 2 mins
        
        return result
    
    @staticmethod
    def get_on_sale_products(limit: int = 12) -> List[Product]:
        """Get products on sale. Cached 2 mins."""
        cache_key = f'catalog:on_sale:{limit}'
        result = cache.get(cache_key)
        
        if result is None:
            result = list(
                Product.objects.on_sale().select_related(
                    'category', 'brand'
                ).prefetch_related('images').order_by('-discount_percentage')[:limit]
            )
            cache.set(cache_key, result, 120)  # 2 mins
        
        return result
    
    @staticmethod
    def get_related_products(product: Product, limit: int = 8) -> List[Product]:
        """Get related products in same category. Cached 2 mins."""
        cache_key = f'catalog:related:{product.id}:{limit}'
        result = cache.get(cache_key)
        
        if result is None:
            result = list(
                Product.objects.active().filter(
                    category=product.category
                ).exclude(id=product.id).select_related(
                    'category', 'brand'
                ).prefetch_related('images')[:limit]
            )
            cache.set(cache_key, result, 120)  # 2 mins
        
        return result
    
    @staticmethod
    def search_suggestions(query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Get search suggestions for autocomplete.
        NOT CACHED - real-time autocomplete needs fresh data.
        """
        products = Product.objects.active().filter(
            Q(name__icontains=query) | Q(sku__icontains=query)
        ).select_related('brand')[:limit]
        
        categories = Category.objects.filter(
            name__icontains=query,
            is_active=True
        )[:5]
        
        brands = Brand.objects.filter(
            name__icontains=query,
            is_active=True
        )[:5]
        
        return {
            'products': [
                {'id': str(p.id), 'name': p.name, 'slug': p.slug}
                for p in products
            ],
            'categories': [
                {'id': c.id, 'name': c.name, 'slug': c.slug}
                for c in categories
            ],
            'brands': [
                {'id': b.id, 'name': b.name, 'slug': b.slug}
                for b in brands
            ]
        }
    
    # ==================== Brands ====================
    
    @staticmethod
    def get_all_brands() -> List[Brand]:
        """Get all active brands. Cached 5 mins."""
        cache_key = 'catalog:brands:all'
        result = cache.get(cache_key)
        
        if result is None:
            result = list(Brand.objects.filter(is_active=True).order_by('name'))
            cache.set(cache_key, result, 300)  # 5 mins
        
        return result
    
    @staticmethod
    def get_brand_by_slug(slug: str) -> Brand:
        """Get brand by slug. Not cached."""
        try:
            return Brand.objects.get(slug=slug, is_active=True)
        except Brand.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy thương hiệu')
