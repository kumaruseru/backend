"""
Meilisearch Search Gateway.

Handles product indexing and search via Meilisearch.
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger('apps.catalog')


class MeilisearchGateway:
    """
    Gateway for Meilisearch product search.
    
    Handles:
    - Product indexing (single and bulk)
    - Full-text search with filters
    - Index management
    """
    
    INDEX_NAME = 'products'
    
    # Searchable attributes (weighted by order)
    SEARCHABLE_ATTRIBUTES = ['name', 'sku', 'brand_name', 'category_name', 'description', 'tags']
    
    # Filterable attributes (for faceted search)
    FILTERABLE_ATTRIBUTES = ['category_id', 'brand_id', 'is_active', 'in_stock', 'on_sale', 'price']
    
    # Sortable attributes
    SORTABLE_ATTRIBUTES = ['price', 'created_at', 'sold_count', 'name']
    
    _client = None
    
    @classmethod
    def get_client(cls):
        """Get or create Meilisearch client."""
        if cls._client is None:
            import meilisearch
            
            url = getattr(settings, 'MEILISEARCH_URL', 'http://localhost:7700')
            api_key = getattr(settings, 'MEILISEARCH_API_KEY', '')
            
            cls._client = meilisearch.Client(url, api_key)
            
        return cls._client
    
    @classmethod
    def get_index(cls):
        """Get or create products index."""
        client = cls.get_client()
        return client.index(cls.INDEX_NAME)
    
    @classmethod
    def setup_index(cls):
        """
        Configure index settings (call once on deployment).
        """
        index = cls.get_index()
        
        # Configure searchable attributes
        index.update_searchable_attributes(cls.SEARCHABLE_ATTRIBUTES)
        
        # Configure filterable attributes
        index.update_filterable_attributes(cls.FILTERABLE_ATTRIBUTES)
        
        # Configure sortable attributes
        index.update_sortable_attributes(cls.SORTABLE_ATTRIBUTES)
        
        # Configure typo tolerance
        index.update_typo_tolerance({
            'enabled': True,
            'minWordSizeForTypos': {
                'oneTypo': 4,
                'twoTypos': 8
            }
        })
        
        logger.info("Meilisearch index configured successfully")
    
    @classmethod
    def product_to_document(cls, product) -> Dict[str, Any]:
        """
        Convert Product model to Meilisearch document.
        """
        # Get price (use sale_price if available)
        price = float(product.sale_price or product.price)
        
        # Get stock info
        in_stock = False
        if hasattr(product, 'stock'):
            in_stock = product.stock.available_quantity > 0
        
        # Check if on sale
        on_sale = bool(product.sale_price and product.sale_price > 0 and product.sale_price < product.price)
        
        # Get primary image
        primary_image = ''
        if hasattr(product, 'images') and product.images.exists():
            primary = product.images.filter(is_primary=True).first()
            if primary:
                primary_image = primary.image.url
            else:
                primary_image = product.images.first().image.url
        
        # Get tags
        tags = []
        if hasattr(product, 'tags'):
            tags = list(product.tags.values_list('name', flat=True))
        
        return {
            'id': str(product.id),
            'name': product.name,
            'slug': product.slug,
            'sku': product.sku or '',
            'description': product.description or '',
            'price': price,
            'original_price': float(product.price),
            'category_id': product.category_id,
            'category_name': product.category.name if product.category else '',
            'brand_id': product.brand_id,
            'brand_name': product.brand.name if product.brand else '',
            'tags': tags,
            'is_active': product.is_active,
            'in_stock': in_stock,
            'on_sale': on_sale,
            'sold_count': getattr(product, 'sold_count', 0),
            'image': primary_image,
            'created_at': product.created_at.timestamp() if product.created_at else 0
        }
    
    @classmethod
    def index_product(cls, product) -> None:
        """Index a single product."""
        try:
            index = cls.get_index()
            document = cls.product_to_document(product)
            index.add_documents([document])
            logger.debug(f"Indexed product: {product.id}")
        except Exception as e:
            logger.error(f"Failed to index product {product.id}: {e}")
    
    @classmethod
    def bulk_index(cls, products) -> None:
        """Bulk index multiple products."""
        try:
            index = cls.get_index()
            documents = [cls.product_to_document(p) for p in products]
            index.add_documents(documents)
            logger.info(f"Bulk indexed {len(documents)} products")
        except Exception as e:
            logger.error(f"Failed to bulk index products: {e}")
    
    @classmethod
    def delete_product(cls, product_id: UUID) -> None:
        """Remove product from index."""
        try:
            index = cls.get_index()
            index.delete_document(str(product_id))
            logger.debug(f"Deleted product from index: {product_id}")
        except Exception as e:
            logger.error(f"Failed to delete product {product_id}: {e}")
    
    @classmethod
    def search(
        cls,
        query: str,
        category_id: int = None,
        brand_id: int = None,
        min_price: float = None,
        max_price: float = None,
        in_stock: bool = None,
        on_sale: bool = None,
        sort: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search products with filters.
        
        Returns:
            {
                'hits': [...],
                'total': int,
                'processing_time_ms': int
            }
        """
        try:
            index = cls.get_index()
            
            # Build filter string
            filters = ['is_active = true']
            
            if category_id:
                filters.append(f'category_id = {category_id}')
            if brand_id:
                filters.append(f'brand_id = {brand_id}')
            if in_stock is True:
                filters.append('in_stock = true')
            if on_sale is True:
                filters.append('on_sale = true')
            if min_price is not None:
                filters.append(f'price >= {min_price}')
            if max_price is not None:
                filters.append(f'price <= {max_price}')
            
            filter_string = ' AND '.join(filters)
            
            # Build sort
            sort_options = []
            if sort:
                sort_mapping = {
                    'price': ['price:asc'],
                    '-price': ['price:desc'],
                    'name': ['name:asc'],
                    '-name': ['name:desc'],
                    'popular': ['sold_count:desc'],
                    '-created': ['created_at:desc'],
                    'created': ['created_at:asc']
                }
                sort_options = sort_mapping.get(sort, [])
            
            # Execute search
            result = index.search(
                query,
                {
                    'filter': filter_string,
                    'sort': sort_options,
                    'limit': limit,
                    'offset': offset,
                    'attributesToRetrieve': ['id', 'name', 'slug', 'price', 'original_price', 
                                             'image', 'brand_name', 'category_name', 'in_stock', 'on_sale']
                }
            )
            
            return {
                'hits': result.get('hits', []),
                'total': result.get('estimatedTotalHits', 0),
                'processing_time_ms': result.get('processingTimeMs', 0)
            }
            
        except Exception as e:
            logger.error(f"Meilisearch search failed: {e}")
            # Return empty result on error
            return {'hits': [], 'total': 0, 'processing_time_ms': 0}
    
    @classmethod
    def reindex_all(cls):
        """
        Reindex all active products.
        Call via management command.
        """
        from .models import Product
        
        products = Product.objects.active().select_related(
            'category', 'brand'
        ).prefetch_related('images', 'tags', 'stock')
        
        # Process in batches
        batch_size = 100
        total = 0
        
        for i in range(0, products.count(), batch_size):
            batch = products[i:i + batch_size]
            cls.bulk_index(list(batch))
            total += len(batch)
        
        logger.info(f"Reindexed {total} products")
        return total
