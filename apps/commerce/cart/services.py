"""Commerce Cart - Application Services."""
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Sum

from apps.common.core.exceptions import NotFoundError, BusinessRuleViolation
from apps.store.catalog.models import Product
from .models import Cart, CartItem, SavedForLater, CartEvent

logger = logging.getLogger('apps.cart')


class CartService:
    @staticmethod
    def get_or_create_cart(user=None, session_key: str = None) -> Cart:
        if user and user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=user)
            if session_key and created:
                guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
                if guest_cart:
                    cart.merge_with(guest_cart)
            return cart
        elif session_key:
            cart, created = Cart.objects.get_or_create(session_key=session_key, user__isnull=True, defaults={'expires_at': timezone.now() + timezone.timedelta(days=7)})
            return cart
        raise BusinessRuleViolation(message='Cannot create cart without user or session')

    @staticmethod
    def get_cart(cart_id: int, user=None) -> Cart:
        queryset = Cart.objects.prefetch_related('items__product', 'saved_items__product')
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        try:
            return queryset.get(id=cart_id)
        except Cart.DoesNotExist:
            raise NotFoundError(message='Cart not found')

    @staticmethod
    @transaction.atomic
    def add_item(user, product_id: UUID, quantity: int = 1, session_key: str = None) -> CartItem:
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(message='Product not found')
        cart = CartService.get_or_create_cart(user, session_key)
        item = cart.add_item(product, quantity)
        CartEvent.objects.create(cart=cart, event_type=CartEvent.EventType.ADD_ITEM, product=product, data={'quantity': quantity})
        logger.info(f"Added {quantity}x product {product_id} to cart {cart.id}")
        return item

    @staticmethod
    @transaction.atomic
    def update_item(user, item_id: int, quantity: int, session_key: str = None) -> Optional[CartItem]:
        cart = CartService.get_or_create_cart(user, session_key)
        item = cart.update_item(item_id, quantity)
        if quantity > 0:
            CartEvent.objects.create(cart=cart, event_type=CartEvent.EventType.UPDATE_QUANTITY, data={'item_id': item_id, 'quantity': quantity})
        else:
            CartEvent.objects.create(cart=cart, event_type=CartEvent.EventType.REMOVE_ITEM, data={'item_id': item_id})
        return item

    @staticmethod
    @transaction.atomic
    def remove_item(user, item_id: int, session_key: str = None) -> bool:
        cart = CartService.get_or_create_cart(user, session_key)
        result = cart.remove_item(item_id)
        if result:
            CartEvent.objects.create(cart=cart, event_type=CartEvent.EventType.REMOVE_ITEM, data={'item_id': item_id})
        return result

    @staticmethod
    @transaction.atomic
    def clear_cart(user, session_key: str = None) -> int:
        cart = CartService.get_or_create_cart(user, session_key)
        count = cart.clear()
        logger.info(f"Cleared cart {cart.id}, removed {count} items")
        return count

    @staticmethod
    def save_for_later(user, item_id: int, session_key: str = None) -> SavedForLater:
        cart = CartService.get_or_create_cart(user, session_key)
        saved = cart.save_for_later(item_id)
        if saved:
            CartEvent.objects.create(cart=cart, event_type=CartEvent.EventType.SAVE_FOR_LATER, data={'item_id': item_id})
        return saved

    @staticmethod
    def move_to_cart(user, saved_id: int, session_key: str = None) -> CartItem:
        cart = CartService.get_or_create_cart(user, session_key)
        return cart.move_to_cart(saved_id)

    @staticmethod
    def remove_saved(user, saved_id: int, session_key: str = None) -> bool:
        cart = CartService.get_or_create_cart(user, session_key)
        deleted, _ = cart.saved_items.filter(id=saved_id).delete()
        return deleted > 0

    @staticmethod
    def apply_coupon(user, coupon_code: str, session_key: str = None) -> Dict[str, Any]:
        cart = CartService.get_or_create_cart(user, session_key)
        try:
            from apps.store.marketing.models import Coupon
            coupon = Coupon.objects.get(code__iexact=coupon_code.strip())
            if not coupon.is_valid:
                return {'success': False, 'error': 'Invalid coupon code'}
            if cart.subtotal < coupon.min_order_value:
                return {'success': False, 'error': f'Minimum order: {coupon.min_order_value:,.0f}₫'}
            discount = coupon.calculate_discount(cart.subtotal)
            cart.coupon_code = coupon_code
            cart.coupon_discount = discount
            cart.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])
            CartEvent.objects.create(cart=cart, event_type=CartEvent.EventType.APPLY_COUPON, data={'coupon': coupon_code, 'discount': str(discount)})
            return {'success': True, 'discount': discount, 'coupon': coupon_code}
        except Exception:
            return {'success': False, 'error': 'Coupon not found'}

    @staticmethod
    def remove_coupon(user, session_key: str = None) -> None:
        cart = CartService.get_or_create_cart(user, session_key)
        cart.remove_coupon()

    @staticmethod
    def validate_cart(user, session_key: str = None) -> Dict[str, Any]:
        cart = CartService.get_or_create_cart(user, session_key)
        issues = cart.validate_stock()
        return {'valid': len(issues) == 0, 'issues': issues, 'subtotal': cart.subtotal, 'total': cart.total}


class CartStatisticsService:
    @staticmethod
    def get_statistics(days: int = 30) -> Dict[str, Any]:
        since = timezone.now() - timezone.timedelta(days=days)
        total_carts = Cart.objects.filter(created_at__gte=since).count()
        with_items = Cart.objects.filter(created_at__gte=since, items__isnull=False).distinct().count()
        completed = CartEvent.objects.filter(created_at__gte=since, event_type=CartEvent.EventType.CHECKOUT_COMPLETE).values('cart').distinct().count()
        abandoned = with_items - completed
        return {'period_days': days, 'total_carts': total_carts, 'carts_with_items': with_items, 'completed_checkout': completed, 'abandoned_carts': abandoned, 'abandonment_rate': round(abandoned / max(with_items, 1) * 100, 2)}
