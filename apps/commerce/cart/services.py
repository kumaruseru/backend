"""
Commerce Cart - Production-Ready Application Services.

Comprehensive business logic with:
- Cart management for users and guests
- Session-based guest carts
- Cart merging on login
- Coupon preview
- Stock validation
- Analytics
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.common.core.exceptions import (
    NotFoundError, BusinessRuleViolation, ValidationError
)
from apps.store.catalog.models import Product
from .models import Cart, CartItem, SavedForLater, CartEvent

logger = logging.getLogger('apps.cart')


class CartService:
    """
    Shopping cart use cases.
    
    Handles:
    - Getting/creating carts for users and guests
    - Cart operations (add, update, remove)
    - Saved for later
    - Coupon preview
    - Cart merging
    - Validation
    """
    
    GUEST_CART_EXPIRY_DAYS = 30
    MAX_CART_ITEMS = 50
    MAX_QUANTITY_PER_ITEM = 99
    
    # --- Cart Retrieval ---
    
    @staticmethod
    def get_or_create_cart(user=None, session_key: str = None) -> Cart:
        """
        Get or create cart for user or session.
        
        Args:
            user: Authenticated user (optional)
            session_key: Session key for guest carts
            
        Returns:
            Cart instance
        """
        if user and user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=user)
            
            if created:
                logger.info(f"Created cart for user {user.email}")
            
            return cart
        
        if session_key:
            cart, created = Cart.objects.get_or_create(
                session_key=session_key,
                user__isnull=True,
                defaults={
                    'expires_at': timezone.now() + timedelta(days=CartService.GUEST_CART_EXPIRY_DAYS)
                }
            )
            
            if created:
                logger.info(f"Created guest cart: {session_key[:20]}...")
            
            return cart
        
        raise ValidationError(message='User hoặc session_key là bắt buộc')
    
    @staticmethod
    def get_cart(user=None, session_key: str = None) -> Cart:
        """
        Get existing cart.
        
        Raises NotFoundError if cart doesn't exist.
        """
        if user and user.is_authenticated:
            try:
                return Cart.objects.prefetch_related(
                    'items', 'items__product', 'items__product__images',
                    'saved_items', 'saved_items__product'
                ).get(user=user)
            except Cart.DoesNotExist:
                raise NotFoundError(message='Giỏ hàng không tồn tại')
        
        if session_key:
            try:
                return Cart.objects.prefetch_related(
                    'items', 'items__product', 'items__product__images',
                    'saved_items', 'saved_items__product'
                ).get(session_key=session_key, user__isnull=True)
            except Cart.DoesNotExist:
                raise NotFoundError(message='Giỏ hàng không tồn tại')
        
        raise ValidationError(message='User hoặc session_key là bắt buộc')
    
    # --- Cart Operations ---
    
    @staticmethod
    @transaction.atomic
    def add_item(
        cart: Cart,
        product_id: UUID,
        quantity: int = 1,
        attributes: Dict = None
    ) -> CartItem:
        """
        Add product to cart.
        
        Args:
            cart: Cart instance
            product_id: Product UUID
            quantity: Quantity to add
            attributes: Selected attributes (for variants)
            
        Returns:
            CartItem instance
        """
        # Check max items
        if cart.items.count() >= CartService.MAX_CART_ITEMS:
            raise BusinessRuleViolation(
                message=f'Giỏ hàng tối đa {CartService.MAX_CART_ITEMS} sản phẩm'
            )
        
        # Get product
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(message='Sản phẩm không tồn tại')
        
        # Check stock
        if hasattr(product, 'stock'):
            available = product.stock.available_quantity
            
            # Check existing quantity in cart
            existing = cart.items.filter(product=product).first()
            current_qty = existing.quantity if existing else 0
            
            if current_qty + quantity > available:
                if available == 0:
                    raise BusinessRuleViolation(message='Sản phẩm đã hết hàng')
                
                raise BusinessRuleViolation(
                    message=f'Chỉ còn {available} sản phẩm. Bạn đã có {current_qty} trong giỏ.'
                )
        
        # Check max quantity
        if quantity > CartService.MAX_QUANTITY_PER_ITEM:
            quantity = CartService.MAX_QUANTITY_PER_ITEM
        
        item = cart.add_item(product, quantity)
        
        if attributes:
            item.selected_attributes = attributes
            item.save(update_fields=['selected_attributes', 'updated_at'])
        
        # Log event
        CartEvent.objects.create(
            cart=cart,
            event_type=CartEvent.EventType.ADD_ITEM,
            product=product,
            data={'quantity': quantity}
        )
        
        logger.info(f"Added {quantity}x {product.name} to cart")
        
        return item
    
    @staticmethod
    @transaction.atomic
    def update_item(
        cart: Cart,
        item_id: int,
        quantity: int
    ) -> Optional[CartItem]:
        """
        Update item quantity.
        
        Args:
            cart: Cart instance
            item_id: CartItem ID
            quantity: New quantity (0 to remove)
            
        Returns:
            Updated CartItem or None if removed
        """
        try:
            item = cart.items.select_related('product').get(id=item_id)
        except CartItem.DoesNotExist:
            raise NotFoundError(message='Sản phẩm không có trong giỏ hàng')
        
        # Clamp quantity
        quantity = min(quantity, CartService.MAX_QUANTITY_PER_ITEM)
        
        if quantity <= 0:
            return CartService.remove_item(cart, item_id)
        
        # Check stock
        if hasattr(item.product, 'stock'):
            available = item.product.stock.available_quantity
            if quantity > available:
                raise BusinessRuleViolation(
                    message=f'Chỉ còn {available} sản phẩm trong kho'
                )
        
        old_qty = item.quantity
        result = cart.update_item(item_id, quantity)
        
        # Log event
        CartEvent.objects.create(
            cart=cart,
            event_type=CartEvent.EventType.UPDATE_QUANTITY,
            product=item.product,
            data={'old_quantity': old_qty, 'new_quantity': quantity}
        )
        
        return result
    
    @staticmethod
    @transaction.atomic
    def remove_item(cart: Cart, item_id: int) -> bool:
        """Remove item from cart."""
        try:
            item = cart.items.select_related('product').get(id=item_id)
            product = item.product
        except CartItem.DoesNotExist:
            return False
        
        removed = cart.remove_item(item_id)
        
        if removed:
            # Log event
            CartEvent.objects.create(
                cart=cart,
                event_type=CartEvent.EventType.REMOVE_ITEM,
                product=product,
                data={'quantity': item.quantity}
            )
        
        return removed
    
    @staticmethod
    def clear_cart(cart: Cart) -> int:
        """Clear all items from cart."""
        count = cart.clear()
        logger.info(f"Cleared {count} items from cart")
        return count
    
    # --- Saved For Later ---
    
    @staticmethod
    def save_for_later(cart: Cart, item_id: int) -> SavedForLater:
        """Move cart item to saved for later."""
        try:
            item = cart.items.get(id=item_id)
        except CartItem.DoesNotExist:
            raise NotFoundError(message='Sản phẩm không có trong giỏ hàng')
        
        saved = cart.save_for_later(item_id)
        
        if saved:
            CartEvent.objects.create(
                cart=cart,
                event_type=CartEvent.EventType.SAVE_FOR_LATER,
                product=saved.product
            )
        
        return saved
    
    @staticmethod
    def move_to_cart(cart: Cart, saved_id: int) -> CartItem:
        """Move saved item back to cart."""
        try:
            saved = cart.saved_items.get(id=saved_id)
        except SavedForLater.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy sản phẩm đã lưu')
        
        item = cart.move_to_cart(saved_id)
        
        if item:
            CartEvent.objects.create(
                cart=cart,
                event_type=CartEvent.EventType.ADD_ITEM,
                product=item.product,
                data={'from_saved': True}
            )
        
        return item
    
    @staticmethod
    def remove_saved(cart: Cart, saved_id: int) -> bool:
        """Remove saved for later item."""
        return cart.saved_items.filter(id=saved_id).delete()[0] > 0
    
    # --- Coupon ---
    
    @staticmethod
    def apply_coupon(cart: Cart, coupon_code: str) -> Dict[str, Any]:
        """Apply coupon to cart preview."""
        result = cart.apply_coupon(coupon_code)
        
        if result['success']:
            CartEvent.objects.create(
                cart=cart,
                event_type=CartEvent.EventType.APPLY_COUPON,
                data={'coupon': coupon_code, 'discount': float(result['discount'])}
            )
        
        return result
    
    @staticmethod
    def remove_coupon(cart: Cart) -> None:
        """Remove applied coupon."""
        cart.remove_coupon()
    
    # --- Validation ---
    
    @staticmethod
    def validate_cart(cart: Cart) -> Dict[str, Any]:
        """
        Validate cart for checkout readiness.
        
        Returns:
            Dict with valid status and any issues
        """
        issues = cart.validate_stock()
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'total_items': cart.total_items,
            'subtotal': cart.subtotal,
            'total': cart.total
        }
    
    @staticmethod
    def refresh_prices(cart: Cart) -> Dict[str, Any]:
        """
        Update all prices to current.
        
        Returns:
            Dict with changes made
        """
        return cart.refresh_prices()
    
    # --- Cart Merge ---
    
    @staticmethod
    @transaction.atomic
    def merge_guest_cart(user, session_key: str) -> Optional[Cart]:
        """
        Merge guest cart into user cart on login.
        
        Args:
            user: Authenticated user
            session_key: Guest session key
            
        Returns:
            User's cart with merged items
        """
        try:
            guest_cart = Cart.objects.prefetch_related('items', 'saved_items').get(
                session_key=session_key,
                user__isnull=True
            )
        except Cart.DoesNotExist:
            return None
        
        user_cart, _ = Cart.objects.get_or_create(user=user)
        
        merged_count = user_cart.merge_with(guest_cart)
        
        logger.info(f"Merged {merged_count} items from guest cart to user {user.email}")
        
        return user_cart
    
    # --- Cleanup ---
    
    @staticmethod
    def cleanup_expired_carts() -> int:
        """Delete expired guest carts."""
        expired = Cart.objects.filter(
            user__isnull=True,
            expires_at__lt=timezone.now()
        )
        count = expired.count()
        expired.delete()
        
        logger.info(f"Cleaned up {count} expired guest carts")
        
        return count
    
    @staticmethod
    def cleanup_inactive_carts(days: int = 90) -> int:
        """Delete inactive guest carts."""
        cutoff = timezone.now() - timedelta(days=days)
        
        inactive = Cart.objects.filter(
            user__isnull=True,
            last_activity_at__lt=cutoff
        )
        count = inactive.count()
        inactive.delete()
        
        logger.info(f"Cleaned up {count} inactive guest carts")
        
        return count
    
    # --- Analytics ---
    
    @staticmethod
    def get_abandoned_carts(hours: int = 24, min_value: Decimal = Decimal('100000')) -> list:
        """
        Get carts abandoned in the last N hours.
        
        For sending reminder emails.
        """
        cutoff = timezone.now() - timedelta(hours=hours)
        recent = timezone.now() - timedelta(hours=1)
        
        carts = Cart.objects.filter(
            user__isnull=False,
            last_activity_at__lt=cutoff,
            last_activity_at__gt=recent - timedelta(hours=hours),
            abandonment_email_sent=False
        ).select_related('user').prefetch_related('items')
        
        abandoned = []
        for cart in carts:
            if cart.subtotal >= min_value and not cart.is_empty:
                abandoned.append(cart)
        
        return abandoned
    
    @staticmethod
    def mark_abandonment_email_sent(cart: Cart) -> None:
        """Mark that abandonment email was sent."""
        cart.abandonment_email_sent = True
        cart.save(update_fields=['abandonment_email_sent', 'updated_at'])
    
    @staticmethod
    def get_cart_statistics() -> Dict[str, Any]:
        """Get cart statistics for dashboard."""
        from django.db.models import Count, Sum, Avg
        
        stats = Cart.objects.filter(
            items__isnull=False
        ).aggregate(
            total_carts=Count('id', distinct=True),
            user_carts=Count('id', filter=models.Q(user__isnull=False), distinct=True),
            guest_carts=Count('id', filter=models.Q(user__isnull=True), distinct=True)
        )
        
        return {
            'total_active_carts': stats['total_carts'] or 0,
            'user_carts': stats['user_carts'] or 0,
            'guest_carts': stats['guest_carts'] or 0
        }


# Import for statistics
from django.db import models
