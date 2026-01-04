"""
Store Catalog - Selectors (Read-Only Queries).

This module contains all READ operations for the catalog.
Following the Selector Pattern to separate read from write logic.

Services handle WRITE operations (create, update, delete).
Selectors handle READ operations (get, list, search, filter).
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from django.db.models import Q, Min, Max

from apps.common.core.exceptions import NotFoundError
from .models import Category, Brand, Product, ProductTag

logger = logging.getLogger('apps.catalog')


class CatalogSelector:
    """
    Read-only queries for catalog data.
    
    All methods are stateless and have no side effects.
    """
    
    # ==================== Categories ====================
    
    @staticmethod
    def get_category_tree() -> List[Category]:
        """Get all active categories with hierarchy."""
        return list(
            Category.objects.filter(is_active=True)
            .select_related('parent')
            .order_by('parent_id', 'sort_order', 'name')
        )
    
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
        
        Returns brands, price range, and tags in this category.
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
    
    # ==================== Products ====================
    
    @staticmethod
    def get_product_by_slug(slug: str) -> Product:
        """
        Get product by slug.
        
        Note: Use CatalogService.get_product_by_slug() if you need 
        to track views (increment_view_count).
        """
        try:
            return Product.objects.select_related(
                'category', 'brand'
            ).prefetch_related(
                'images', 'tags', 'stock'
            ).get(slug=slug, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy sản phẩm')
    
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
    def get_featured_products(limit: int = 12) -> List[Product]:
        """Get featured products."""
        return list(
            Product.objects.featured().select_related(
                'category', 'brand'
            ).prefetch_related('images')[:limit]
        )
    
    @staticmethod
    def get_new_arrivals(limit: int = 12, days: int = 30) -> List[Product]:
        """Get new arrival products."""
        return list(
            Product.objects.new_arrivals(days).select_related(
                'category', 'brand'
            ).prefetch_related('images').order_by('-created_at')[:limit]
        )
    
    @staticmethod
    def get_bestsellers(limit: int = 12) -> List[Product]:
        """Get bestselling products."""
        return list(
            Product.objects.active().filter(
                is_bestseller=True
            ).select_related(
                'category', 'brand'
            ).prefetch_related('images').order_by('-sold_count')[:limit]
        )
    
    @staticmethod
    def get_on_sale_products(limit: int = 12) -> List[Product]:
        """Get products on sale."""
        return list(
            Product.objects.on_sale().select_related(
                'category', 'brand'
            ).prefetch_related('images').order_by('-discount_percentage')[:limit]
        )
    
    @staticmethod
    def get_related_products(product: Product, limit: int = 8) -> List[Product]:
        """Get related products in same category."""
        return list(
            Product.objects.active().filter(
                category=product.category
            ).exclude(id=product.id).select_related(
                'category', 'brand'
            ).prefetch_related('images')[:limit]
        )
    
    @staticmethod
    def search_suggestions(query: str, limit: int = 10) -> Dict[str, Any]:
        """Get search suggestions for autocomplete."""
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
        """Get all active brands."""
        return list(Brand.objects.filter(is_active=True).order_by('name'))
    
    @staticmethod
    def get_brand_by_slug(slug: str) -> Brand:
        """Get brand by slug."""
        try:
            return Brand.objects.get(slug=slug, is_active=True)
        except Brand.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy thương hiệu')
