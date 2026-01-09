"""Store Wishlist - Application Services."""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from django.db import transaction
from django.db.models import Count

from apps.common.core.exceptions import NotFoundError, BusinessRuleViolation
from .models import Wishlist, WishlistItem

logger = logging.getLogger('apps.wishlist')


class WishlistService:
    @staticmethod
    def get_or_create_default_wishlist(user) -> Wishlist:
        wishlist, created = Wishlist.objects.get_or_create(user=user, is_default=True, defaults={'name': 'Favorites'})
        return wishlist

    @staticmethod
    def get_user_wishlists(user) -> List[Wishlist]:
        wishlists = list(Wishlist.objects.filter(user=user).annotate(items_count_annotated=Count('items')).order_by('-is_default', '-created_at'))
        if not any(w.is_default for w in wishlists):
            default = WishlistService.get_or_create_default_wishlist(user)
            wishlists.insert(0, default)
        return wishlists

    @staticmethod
    def get_wishlist(wishlist_id: UUID, user) -> Wishlist:
        try:
            return Wishlist.objects.prefetch_related('items__product').get(id=wishlist_id, user=user)
        except Wishlist.DoesNotExist:
            raise NotFoundError(message='Wishlist not found')

    @staticmethod
    def get_shared_wishlist(share_token: str) -> Wishlist:
        try:
            return Wishlist.objects.prefetch_related('items__product').get(share_token=share_token, is_public=True)
        except Wishlist.DoesNotExist:
            raise NotFoundError(message='Wishlist not found')

    @staticmethod
    @transaction.atomic
    def create_wishlist(user, name: str, description: str = '', is_public: bool = False) -> Wishlist:
        wishlist = Wishlist.objects.create(user=user, name=name, description=description, is_public=is_public)
        logger.info(f"Wishlist created: {wishlist.id}")
        return wishlist

    @staticmethod
    def update_wishlist(wishlist: Wishlist, **kwargs) -> Wishlist:
        for key, value in kwargs.items():
            if hasattr(wishlist, key) and value is not None:
                setattr(wishlist, key, value)
        wishlist.save()
        return wishlist

    @staticmethod
    def delete_wishlist(wishlist: Wishlist) -> None:
        if wishlist.is_default:
            raise BusinessRuleViolation(message='Cannot delete default wishlist')
        wishlist.delete()

    @staticmethod
    def get_wishlist_items(wishlist: Wishlist) -> List[WishlistItem]:
        return list(wishlist.items.select_related('product__category', 'product__brand').prefetch_related('product__images').order_by('-created_at'))

    @staticmethod
    @transaction.atomic
    def add_item(user, product_id: UUID, wishlist_id: UUID = None, note: str = '', priority: str = 'medium', notify_on_sale: bool = True, target_price=None) -> WishlistItem:
        if wishlist_id:
            wishlist = WishlistService.get_wishlist(wishlist_id, user)
        else:
            wishlist = WishlistService.get_or_create_default_wishlist(user)
        existing = WishlistItem.objects.filter(wishlist=wishlist, product_id=product_id).first()
        if existing:
            if note:
                existing.note = note
            existing.priority = priority
            existing.notify_on_sale = notify_on_sale
            if target_price:
                existing.target_price = target_price
            existing.save()
            return existing
        item = WishlistItem.objects.create(wishlist=wishlist, product_id=product_id, note=note, priority=priority, notify_on_sale=notify_on_sale, target_price=target_price)
        logger.info(f"Added product {product_id} to wishlist {wishlist.id}")
        return item

    @staticmethod
    def update_item(item: WishlistItem, **kwargs) -> WishlistItem:
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        item.save()
        return item

    @staticmethod
    def remove_item(item_id: int, user) -> bool:
        deleted, _ = WishlistItem.objects.filter(id=item_id, wishlist__user=user).delete()
        return deleted > 0

    @staticmethod
    def move_item(item: WishlistItem, target_wishlist: Wishlist) -> WishlistItem:
        existing = WishlistItem.objects.filter(wishlist=target_wishlist, product=item.product).first()
        if existing:
            item.delete()
            return existing
        item.wishlist = target_wishlist
        item.save(update_fields=['wishlist', 'updated_at'])
        return item

    @staticmethod
    @transaction.atomic
    def bulk_add(user, product_ids: list, wishlist_id: UUID = None) -> int:
        if wishlist_id:
            wishlist = WishlistService.get_wishlist(wishlist_id, user)
        else:
            wishlist = WishlistService.get_or_create_default_wishlist(user)
        existing = set(wishlist.items.values_list('product_id', flat=True))
        new_items = [WishlistItem(wishlist=wishlist, product_id=pid) for pid in product_ids if pid not in existing]
        WishlistItem.objects.bulk_create(new_items)
        return len(new_items)

    @staticmethod
    @transaction.atomic
    def bulk_remove(user, item_ids: list) -> int:
        deleted, _ = WishlistItem.objects.filter(id__in=item_ids, wishlist__user=user).delete()
        return deleted

    @staticmethod
    def is_in_wishlist(user, product_id: UUID) -> bool:
        return WishlistItem.objects.filter(wishlist__user=user, product_id=product_id).exists()

    @staticmethod
    def get_wishlists_containing(user, product_id: UUID) -> List[Wishlist]:
        return list(Wishlist.objects.filter(user=user, items__product_id=product_id))

    @staticmethod
    @transaction.atomic
    def remove_product_from_all(user, product_id: UUID) -> int:
        deleted, _ = WishlistItem.objects.filter(wishlist__user=user, product_id=product_id).delete()
        if deleted > 0:
            logger.info(f"Removed product {product_id} from {deleted} wishlist(s) for user {user.id}")
        return deleted

    @staticmethod
    def get_items_for_alert() -> List[WishlistItem]:
        return list(WishlistItem.objects.filter(notify_on_sale=True).select_related('product', 'wishlist__user').filter(product__sale_price__isnull=False, product__sale_price__gt=0))

    @staticmethod
    def process_price_alerts() -> int:
        items = WishlistService.get_items_for_alert()
        notified = 0
        for item in items:
            item.update_lowest_price()
            if item.should_notify():
                item.mark_notified()
                notified += 1
        return notified
