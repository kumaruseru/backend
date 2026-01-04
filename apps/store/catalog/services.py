"""
Store Catalog - Application Services.

Business logic for catalog operations.
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from django.db import transaction
from django.db.models import Min, Max, Count, Q
from django.utils import timezone

from apps.common.core.exceptions import NotFoundError, ValidationError
from .models import Category, Brand, ProductTag, Product, ProductImage

logger = logging.getLogger('apps.catalog')


class CatalogService:
    """
    Catalog service for product management.
    """
    
    # --- Categories ---
    
    @staticmethod
    def get_category_tree(include_empty: bool = False) -> list:
        """
        Get full category tree.
        
        Args:
            include_empty: Include categories with no products
            
        Returns:
            List of root categories with nested children
        """
        queryset = Category.objects.filter(
            is_active=True,
            parent__isnull=True
        ).order_by('sort_order', 'name')
        
        if not include_empty:
            queryset = queryset.annotate(
                prod_count=Count('products', filter=Q(products__is_active=True))
            ).filter(prod_count__gt=0)
        
        return list(queryset.prefetch_related('children'))
    
    @staticmethod
    def get_category_by_slug(slug: str) -> Category:
        """Get category by slug."""
        try:
            return Category.objects.get(slug=slug, is_active=True)
        except Category.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy danh mục')
    
    @staticmethod
    def get_category_filters(category: Category) -> Dict[str, Any]:
        """
        Get available filters for a category.
        
        Returns brands, price range, and attributes in this category.
        """
        products = Product.objects.active().filter(
            category_id__in=category.get_all_children_ids()
        )
        
        # Brands in category
        brands = Brand.objects.filter(
            products__in=products,
            is_active=True
        ).distinct()
        
        # Price range
        price_stats = products.aggregate(
            min_price=Min('price'),
            max_price=Max('price')
        )
        
        # Tags
        tags = ProductTag.objects.filter(
            products__in=products
        ).distinct()
        
        return {
            'brands': list(brands),
            'price_range': {
                'min': price_stats['min_price'] or 0,
                'max': price_stats['max_price'] or 0
            },
            'tags': list(tags),
            'product_count': products.count()
        }
    
    # --- Products ---
    
    @staticmethod
    def get_product_by_slug(slug: str, increment_view: bool = True) -> Product:
        """
        Get product by slug with view tracking.
        """
        try:
            product = Product.objects.select_related(
                'category', 'brand'
            ).prefetch_related(
                'images', 'tags', 'stock'
            ).get(slug=slug, is_active=True)
            
            if increment_view:
                CatalogService.increment_product_view_count(product)
            
            return product
            
        except Product.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy sản phẩm')
            
    @staticmethod
    def increment_product_view_count(product: Product):
        """
        Increment view count in ProductStat (Vertical Partitioning).
        Uses Redis for buffer if available.
        """
        from django.db.models import F
        from django.core.cache import cache
        from .models import ProductStat
        
        cache_key = f'product_views:{product.pk}'
        try:
            # Increment in Redis
            new_count = cache.incr(cache_key)
            
            # Sync to DB every 10 views (updates ProductStat, not Product)
            if new_count % 10 == 0:
                ProductStat.objects.filter(product_id=product.pk).update(
                    view_count=F('view_count') + 10
                )
                cache.set(cache_key, 0, timeout=3600)
        except (ValueError, TypeError):
            # Key doesn't exist or Redis issue, fallback to direct update
            cache.set(cache_key, 1, timeout=3600)
            # Ensure ProductStat exists, then update
            ProductStat.objects.get_or_create(product_id=product.pk)
            ProductStat.objects.filter(product_id=product.pk).update(
                view_count=F('view_count') + 1
            )

    @staticmethod
    def increment_product_sold_count(product_id: UUID, quantity: int = 1):
        """
        Increment sold count atomically in ProductStat.
        """
        from django.db.models import F
        from .models import ProductStat
        
        # Ensure ProductStat exists
        ProductStat.objects.get_or_create(product_id=product_id)
        ProductStat.objects.filter(product_id=product_id).update(
            sold_count=F('sold_count') + quantity
        )
    
    @staticmethod
    def get_product_by_id(product_id: UUID) -> Product:
        """Get product by ID."""
        try:
            return Product.objects.select_related(
                'category', 'brand'
            ).prefetch_related(
                'images', 'tags', 'stock'
            ).get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy sản phẩm')
    
    @staticmethod
    def get_featured_products(limit: int = 12) -> list:
        """Get featured products."""
        return list(
            Product.objects.featured().select_related(
                'category', 'brand'
            ).prefetch_related('images')[:limit]
        )
    
    @staticmethod
    def get_new_arrivals(limit: int = 12, days: int = 30) -> list:
        """Get new arrival products."""
        return list(
            Product.objects.new_arrivals(days).select_related(
                'category', 'brand'
            ).prefetch_related('images').order_by('-created_at')[:limit]
        )
    
    @staticmethod
    def get_bestsellers(limit: int = 12) -> list:
        """Get bestselling products."""
        return list(
            Product.objects.active().filter(
                is_bestseller=True
            ).select_related(
                'category', 'brand'
            ).prefetch_related('images').order_by('-sold_count')[:limit]
        )
    
    @staticmethod
    def get_on_sale_products(limit: int = 12) -> list:
        """Get products on sale."""
        return list(
            Product.objects.on_sale().select_related(
                'category', 'brand'
            ).prefetch_related('images').order_by('-discount_percentage')[:limit]
        )
    
    @staticmethod
    def get_related_products(product: Product, limit: int = 8) -> list:
        """Get related products."""
        return list(
            Product.objects.active().filter(
                category=product.category
            ).exclude(id=product.id).select_related(
                'category', 'brand'
            ).prefetch_related('images')[:limit]
        )
    
    @staticmethod
    def search_products(
        query: str,
        category_id: int = None,
        brand_id: int = None,
        min_price: int = None,
        max_price: int = None,
        in_stock: bool = None,
        on_sale: bool = None,
        ordering: str = '-created_at',
        limit: int = 50
    ) -> dict:
        """
        Search products using Meilisearch.
        
        Falls back to Django ORM if Meilisearch is unavailable.
        """
        from django.db import models
        from django.conf import settings
        
        # Try Meilisearch first
        use_meilisearch = getattr(settings, 'USE_MEILISEARCH', True)
        
        if use_meilisearch and query:
            try:
                from .search import MeilisearchGateway
                
                result = MeilisearchGateway.search(
                    query=query,
                    category_id=category_id,
                    brand_id=brand_id,
                    min_price=min_price,
                    max_price=max_price,
                    in_stock=in_stock,
                    on_sale=on_sale,
                    sort=ordering,
                    limit=limit
                )
                
                # Convert hits to product IDs for ORM fetch (to get full objects)
                if result['hits']:
                    product_ids = [UUID(hit['id']) for hit in result['hits']]
                    
                    # Fetch full products in order
                    products_dict = {
                        str(p.id): p 
                        for p in Product.objects.filter(id__in=product_ids).select_related(
                            'category', 'brand'
                        ).prefetch_related('images')
                    }
                    
                    # Preserve Meilisearch ranking order
                    products = [products_dict[hit['id']] for hit in result['hits'] if hit['id'] in products_dict]
                    
                    return {
                        'products': products,
                        'total': result['total'],
                        'search_time_ms': result['processing_time_ms']
                    }
                
                return {'products': [], 'total': 0}
                
            except Exception as e:
                logger.warning(f"Meilisearch search failed, falling back to ORM: {e}")
        
        # Fallback to Django ORM
        queryset = Product.objects.active().select_related('category', 'brand')
        
        # Text search via icontains
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(sku__icontains=query) |
                Q(brand__name__icontains=query) |
                Q(tags__name__icontains=query)
            ).distinct()
        
        # Category filter
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                queryset = queryset.filter(category_id__in=category.get_all_children_ids())
            except Category.DoesNotExist:
                pass
        
        # Brand filter
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        
        # Price range
        if min_price is not None:
            queryset = queryset.filter(effective_price__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(effective_price__lte=max_price)
        
        # Stock filter
        if in_stock is True:
            queryset = queryset.filter(stock__quantity__gt=0)
        
        # Sale filter
        if on_sale is True:
            queryset = queryset.filter(
                sale_price__isnull=False,
                sale_price__gt=0
            ).exclude(sale_price__gte=models.F('price'))
        
        # Ordering
        valid_orderings = {
            'price': 'effective_price',
            '-price': '-effective_price',
            'name': 'name',
            '-name': '-name',
            'created': 'created_at',
            '-created': '-created_at',
            'popular': '-sold_count',
            'rating': '-average_rating'
        }
        order_field = valid_orderings.get(ordering, '-created_at')
        queryset = queryset.order_by(order_field)
        
        total = queryset.count()
        products = list(queryset.prefetch_related('images')[:limit])
        
        return {
            'products': products,
            'total': total
        }
    
    @staticmethod
    def get_search_suggestions(query: str, limit: int = 10) -> dict:
        """
        Get search suggestions for autocomplete.
        """
        products = Product.objects.active().filter(
            Q(name__icontains=query) | Q(sku__icontains=query)
        ).select_related('brand')[:limit]
        
        categories = Category.objects.filter(
            is_active=True,
            name__icontains=query
        )[:5]
        
        brands = Brand.objects.filter(
            is_active=True,
            name__icontains=query
        )[:5]
        
        return {
            'products': list(products),
            'categories': list(categories),
            'brands': list(brands)
        }
    
    # --- Admin Operations ---
    
    @staticmethod
    @transaction.atomic
    def create_product(data: dict, images: list = None) -> Product:
        """
        Create a new product.
        """
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
        """
        Update a product.
        """
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
        """
        Bulk update products.
        
        Returns number of updated products.
        """
        count = Product.objects.filter(id__in=product_ids).update(**updates)
        
        logger.info(f"Bulk updated {count} products")
        
        return count
    
    @staticmethod
    def get_catalog_statistics() -> dict:
        """
        Get catalog statistics for admin dashboard.
        """
        now = timezone.now()
        last_30_days = now - timezone.timedelta(days=30)
        
        products = Product.objects.all()
        
        return {
            'total_products': products.count(),
            'active_products': products.filter(is_active=True).count(),
            'out_of_stock': products.filter(stock__quantity__lte=0).count(),
            'low_stock': products.filter(stock__quantity__lte=10, stock__quantity__gt=0).count(),
            'on_sale': products.filter(sale_price__isnull=False, sale_price__gt=0).count(),
            'featured': products.filter(is_featured=True).count(),
            'new_this_month': products.filter(created_at__gte=last_30_days).count(),
            'total_categories': Category.objects.filter(is_active=True).count(),
            'total_brands': Brand.objects.filter(is_active=True).count(),
        }
