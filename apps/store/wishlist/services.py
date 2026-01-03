"""
Store Wishlist - Application Services.
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from django.db import transaction
from django.db.models import Count

from apps.common.core.exceptions import NotFoundError, BusinessRuleViolation
from .models import Wishlist, WishlistItem

logger = logging.getLogger('apps.wishlist')


class WishlistService:
    """Wishlist management service."""
    
    @staticmethod
    def get_or_create_default_wishlist(user) -> Wishlist:
        """Get or create user's default wishlist."""
        wishlist, created = Wishlist.objects.get_or_create(
            user=user,
            is_default=True,
            defaults={'name': 'Yêu thích'}
        )
        return wishlist
    
    @staticmethod
    def get_user_wishlists(user) -> List[Wishlist]:
        """Get all wishlists for a user."""
        wishlists = list(
            Wishlist.objects.filter(user=user)
            .annotate(items_count_annotated=Count('items'))
            .order_by('-is_default', '-created_at')
        )
        
        # Ensure default exists
        if not any(w.is_default for w in wishlists):
            default = WishlistService.get_or_create_default_wishlist(user)
            wishlists.insert(0, default)
        
        return wishlists
    
    @staticmethod
    def get_wishlist(wishlist_id: UUID, user) -> Wishlist:
        """Get a specific wishlist."""
        try:
            return Wishlist.objects.prefetch_related('items__product').get(
                id=wishlist_id,
                user=user
            )
        except Wishlist.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy danh sách')
    
    @staticmethod
    def get_shared_wishlist(share_token: str) -> Wishlist:
        """Get wishlist by share token."""
        try:
            return Wishlist.objects.prefetch_related('items__product').get(
                share_token=share_token,
                is_public=True
            )
        except Wishlist.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy danh sách')
    
    @staticmethod
    @transaction.atomic
    def create_wishlist(user, name: str, description: str = '', is_public: bool = False) -> Wishlist:
        """Create a new wishlist."""
        wishlist = Wishlist.objects.create(
            user=user,
            name=name,
            description=description,
            is_public=is_public
        )
        
        logger.info(f"Wishlist created: {wishlist.id}")
        
        return wishlist
    
    @staticmethod
    def update_wishlist(wishlist: Wishlist, **kwargs) -> Wishlist:
        """Update wishlist."""
        for key, value in kwargs.items():
            if hasattr(wishlist, key) and value is not None:
                setattr(wishlist, key, value)
        
        wishlist.save()
        return wishlist
    
    @staticmethod
    def delete_wishlist(wishlist: Wishlist) -> None:
        """Delete a wishlist."""
        if wishlist.is_default:
            raise BusinessRuleViolation(message='Không thể xóa danh sách mặc định')
        
        wishlist.delete()
    
    # --- Items ---
    
    @staticmethod
    def get_wishlist_items(wishlist: Wishlist) -> List[WishlistItem]:
        """Get items in a wishlist."""
        return list(
            wishlist.items.select_related('product__category', 'product__brand')
            .prefetch_related('product__images')
            .order_by('-created_at')
        )
    
    @staticmethod
    @transaction.atomic
    def add_item(
        user,
        product_id: UUID,
        wishlist_id: UUID = None,
        note: str = '',
        priority: str = 'medium',
        notify_on_sale: bool = True,
        target_price=None
    ) -> WishlistItem:
        """Add item to wishlist."""
        # Get wishlist
        if wishlist_id:
            wishlist = WishlistService.get_wishlist(wishlist_id, user)
        else:
            wishlist = WishlistService.get_or_create_default_wishlist(user)
        
        # Check if already in wishlist
        existing = WishlistItem.objects.filter(
            wishlist=wishlist,
            product_id=product_id
        ).first()
        
        if existing:
            # Update existing
            if note:
                existing.note = note
            existing.priority = priority
            existing.notify_on_sale = notify_on_sale
            if target_price:
                existing.target_price = target_price
            existing.save()
            return existing
        
        # Create new item
        item = WishlistItem.objects.create(
            wishlist=wishlist,
            product_id=product_id,
            note=note,
            priority=priority,
            notify_on_sale=notify_on_sale,
            target_price=target_price
        )
        
        logger.info(f"Added product {product_id} to wishlist {wishlist.id}")
        
        return item
    
    @staticmethod
    def update_item(item: WishlistItem, **kwargs) -> WishlistItem:
        """Update wishlist item."""
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        
        item.save()
        return item
    
    @staticmethod
    def remove_item(item_id: int, user) -> bool:
        """Remove item from wishlist."""
        deleted, _ = WishlistItem.objects.filter(
            id=item_id,
            wishlist__user=user
        ).delete()
        
        return deleted > 0
    
    @staticmethod
    def move_item(item: WishlistItem, target_wishlist: Wishlist) -> WishlistItem:
        """Move item to another wishlist."""
        # Check if already exists in target
        existing = WishlistItem.objects.filter(
            wishlist=target_wishlist,
            product=item.product
        ).first()
        
        if existing:
            # Merge - delete original
            item.delete()
            return existing
        
        # Move
        item.wishlist = target_wishlist
        item.save(update_fields=['wishlist', 'updated_at'])
        return item
    
    # --- Bulk Operations ---
    
    @staticmethod
    @transaction.atomic
    def bulk_add(user, product_ids: list, wishlist_id: UUID = None) -> int:
        """Bulk add products to wishlist."""
        if wishlist_id:
            wishlist = WishlistService.get_wishlist(wishlist_id, user)
        else:
            wishlist = WishlistService.get_or_create_default_wishlist(user)
        
        # Get existing products in wishlist
        existing = set(
            wishlist.items.values_list('product_id', flat=True)
        )
        
        # Add new items
        new_items = [
            WishlistItem(
                wishlist=wishlist,
                product_id=pid
            )
            for pid in product_ids
            if pid not in existing
        ]
        
        WishlistItem.objects.bulk_create(new_items)
        
        return len(new_items)
    
    @staticmethod
    @transaction.atomic
    def bulk_remove(user, item_ids: list) -> int:
        """Bulk remove items."""
        deleted, _ = WishlistItem.objects.filter(
            id__in=item_ids,
            wishlist__user=user
        ).delete()
        
        return deleted
    
    @staticmethod
    @transaction.atomic
    def move_to_cart(user, item_ids: list = None, all_items: bool = False) -> int:
        """Move wishlist items to cart."""
        from apps.commerce.cart.services import CartService
        
        if all_items:
            items = WishlistItem.objects.filter(
                wishlist__user=user
            ).select_related('product')
        else:
            items = WishlistItem.objects.filter(
                id__in=item_ids,
                wishlist__user=user
            ).select_related('product')
        
        count = 0
        for item in items:
            if item.is_in_stock:
                CartService.add_item(user, item.product.id, 1)
                count += 1
        
        return count
    
    # --- Checks ---
    
    @staticmethod
    def is_in_wishlist(user, product_id: UUID) -> bool:
        """Check if product is in any wishlist."""
        return WishlistItem.objects.filter(
            wishlist__user=user,
            product_id=product_id
        ).exists()
    
    @staticmethod
    def get_wishlists_containing(user, product_id: UUID) -> List[Wishlist]:
        """Get wishlists containing a product."""
        return list(
            Wishlist.objects.filter(
                user=user,
                items__product_id=product_id
            )
        )
    
    # --- Price Alerts ---
    
    @staticmethod
    def get_items_for_alert() -> List[WishlistItem]:
        """Get items that should receive price alerts."""
        return list(
            WishlistItem.objects.filter(
                notify_on_sale=True
            ).select_related('product', 'wishlist__user')
            .filter(
                product__sale_price__isnull=False,
                product__sale_price__gt=0
            )
        )
    
    @staticmethod
    def process_price_alerts() -> int:
        """Process and send price alerts."""
        items = WishlistService.get_items_for_alert()
        notified = 0
        
        for item in items:
            item.update_lowest_price()
            
            if item.should_notify():
                # TODO: Send notification
                item.mark_notified()
                notified += 1
        
        return notified
