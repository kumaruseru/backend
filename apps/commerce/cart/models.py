"""
Commerce Cart - Production-Ready Models.

Shopping cart models with:
- Cart: Aggregate root with user/guest support
- CartItem: Line items with price tracking
- SavedForLater: Wishlist-like functionality
- CartAbandonmentLog: Analytics for abandoned carts
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import TimeStampedModel


class Cart(TimeStampedModel):
    """
    Shopping cart aggregate root.
    
    Supports:
    - User carts (authenticated)
    - Guest carts (session-based)
    - Cart merging on login
    - Saved for later items
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
        verbose_name='Người dùng'
    )
    session_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Session Key'
    )
    
    # Expiration for guest carts
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Hết hạn',
        help_text='For guest carts only'
    )
    
    # Applied coupon (preview before checkout)
    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Mã giảm giá'
    )
    coupon_discount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Giảm giá từ coupon'
    )
    
    # Analytics
    last_activity_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Hoạt động cuối'
    )
    abandonment_email_sent = models.BooleanField(
        default=False,
        verbose_name='Đã gửi email nhắc nhở'
    )
    
    # Source tracking
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = 'Giỏ hàng'
        verbose_name_plural = 'Giỏ hàng'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['session_key']),
            models.Index(fields=['last_activity_at']),
        ]
    
    def __str__(self) -> str:
        if self.user:
            return f"Cart: {self.user.email}"
        return f"Cart: {self.session_key[:20]}..."
    
    # --- Computed Properties ---
    
    @property
    def is_empty(self) -> bool:
        """Check if cart has no items."""
        return not self.items.exists()
    
    @property
    def total_items(self) -> int:
        """Total number of items in cart."""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def unique_items(self) -> int:
        """Number of unique products."""
        return self.items.count()
    
    @property
    def subtotal(self) -> Decimal:
        """Sum of all item subtotals."""
        return sum(item.subtotal for item in self.items.all())
    
    @property
    def total_savings(self) -> Decimal:
        """Total discount from sale prices."""
        return sum(item.savings for item in self.items.all())
    
    @property
    def total(self) -> Decimal:
        """Grand total after coupon."""
        return max(self.subtotal - self.coupon_discount, Decimal('0'))
    
    @property
    def is_expired(self) -> bool:
        """Check if guest cart is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def has_out_of_stock(self) -> bool:
        """Check if any item is out of stock."""
        return any(item.is_out_of_stock for item in self.items.all())
    
    @property
    def has_price_changes(self) -> bool:
        """Check if any item has price change since added."""
        return any(item.has_price_changed for item in self.items.all())
    
    @property
    def saved_items_count(self) -> int:
        """Number of saved for later items."""
        return self.saved_items.count()
    
    # --- Cart Operations ---
    
    def add_item(
        self,
        product,
        quantity: int = 1,
        update_price: bool = True
    ) -> 'CartItem':
        """
        Add product to cart or update quantity if exists.
        
        Args:
            product: Product to add
            quantity: Quantity to add
            update_price: Whether to update price to current
        
        Returns:
            CartItem instance
        """
        current_price = product.sale_price or product.price
        
        item, created = CartItem.objects.get_or_create(
            cart=self,
            product=product,
            defaults={
                'quantity': quantity,
                'unit_price': current_price,
                'original_price': product.price
            }
        )
        
        if not created:
            item.quantity += quantity
            
            # Optionally update price to current
            if update_price:
                item.unit_price = current_price
                item.original_price = product.price
            
            item.save(update_fields=[
                'quantity', 'unit_price', 'original_price', 'updated_at'
            ])
        
        # Update activity
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])
        
        return item
    
    def update_item(self, item_id: int, quantity: int) -> 'CartItem':
        """
        Update item quantity.
        
        Returns:
            Updated CartItem or None if deleted
        """
        try:
            item = self.items.get(id=item_id)
        except CartItem.DoesNotExist:
            return None
        
        if quantity <= 0:
            item.delete()
            return None
        
        # Check stock limit
        if hasattr(item.product, 'stock'):
            max_qty = item.product.stock.available_quantity
            quantity = min(quantity, max_qty)
        
        item.quantity = quantity
        item.save(update_fields=['quantity', 'updated_at'])
        
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])
        
        return item
    
    def remove_item(self, item_id: int) -> bool:
        """Remove item from cart."""
        deleted, _ = self.items.filter(id=item_id).delete()
        
        if deleted:
            self.last_activity_at = timezone.now()
            self.save(update_fields=['last_activity_at'])
        
        return deleted > 0
    
    def clear(self) -> int:
        """Remove all items from cart."""
        count = self.items.count()
        self.items.all().delete()
        
        # Reset coupon
        self.coupon_code = ''
        self.coupon_discount = 0
        self.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])
        
        return count
    
    def merge_with(self, other_cart: 'Cart') -> int:
        """
        Merge items from another cart (e.g., guest to user cart).
        
        Returns:
            Number of items merged
        """
        merged_count = 0
        
        for item in other_cart.items.select_related('product').all():
            existing = self.items.filter(product=item.product).first()
            
            if existing:
                existing.quantity += item.quantity
                existing.save(update_fields=['quantity', 'updated_at'])
            else:
                item.cart = self
                item.save(update_fields=['cart', 'updated_at'])
            
            merged_count += 1
        
        # Merge saved items
        for saved in other_cart.saved_items.all():
            if not self.saved_items.filter(product=saved.product).exists():
                saved.cart = self
                saved.save(update_fields=['cart', 'updated_at'])
        
        other_cart.delete()
        
        return merged_count
    
    def save_for_later(self, item_id: int) -> 'SavedForLater':
        """Move item to saved for later."""
        try:
            item = self.items.get(id=item_id)
        except CartItem.DoesNotExist:
            return None
        
        saved, created = SavedForLater.objects.get_or_create(
            cart=self,
            product=item.product,
            defaults={'price_when_saved': item.unit_price}
        )
        
        item.delete()
        
        return saved
    
    def move_to_cart(self, saved_id: int) -> 'CartItem':
        """Move saved item back to cart."""
        try:
            saved = self.saved_items.get(id=saved_id)
        except SavedForLater.DoesNotExist:
            return None
        
        item = self.add_item(saved.product, quantity=1)
        saved.delete()
        
        return item
    
    def apply_coupon(self, coupon_code: str) -> dict:
        """
        Apply coupon to cart preview.
        
        Returns:
            Dict with success status and discount
        """
        try:
            from apps.store.marketing.models import Coupon
            
            coupon = Coupon.objects.get(code__iexact=coupon_code.strip())
            
            if not coupon.is_valid:
                return {'success': False, 'error': 'Mã giảm giá không hợp lệ'}
            
            if self.subtotal < coupon.minimum_amount:
                return {
                    'success': False,
                    'error': f'Đơn hàng tối thiểu {coupon.minimum_amount:,.0f}₫'
                }
            
            discount = coupon.calculate_discount(self.subtotal)
            
            self.coupon_code = coupon_code
            self.coupon_discount = discount
            self.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])
            
            return {
                'success': True,
                'discount': discount,
                'coupon': coupon_code
            }
            
        except Exception:
            return {'success': False, 'error': 'Mã giảm giá không tồn tại'}
    
    def remove_coupon(self) -> None:
        """Remove applied coupon."""
        self.coupon_code = ''
        self.coupon_discount = 0
        self.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])
    
    def refresh_prices(self) -> dict:
        """
        Update all item prices to current product prices.
        
        Returns:
            Dict with updated items and changes
        """
        changes = []
        
        for item in self.items.select_related('product').all():
            old_price = item.unit_price
            new_price = item.product.sale_price or item.product.price
            
            if old_price != new_price:
                changes.append({
                    'product_id': str(item.product.id),
                    'product_name': item.product.name,
                    'old_price': old_price,
                    'new_price': new_price
                })
                
                item.unit_price = new_price
                item.original_price = item.product.price
                item.save(update_fields=['unit_price', 'original_price', 'updated_at'])
        
        return {
            'updated_count': len(changes),
            'changes': changes
        }
    
    def validate_stock(self) -> list:
        """
        Validate all items against current stock.
        
        Returns:
            List of items with stock issues
        """
        issues = []
        
        for item in self.items.select_related('product').all():
            if not item.product.is_active:
                issues.append({
                    'item_id': item.id,
                    'product_name': item.product.name,
                    'issue': 'unavailable',
                    'message': 'Sản phẩm không còn bán'
                })
            elif hasattr(item.product, 'stock'):
                available = item.product.stock.available_quantity
                if item.quantity > available:
                    issues.append({
                        'item_id': item.id,
                        'product_name': item.product.name,
                        'issue': 'insufficient_stock',
                        'requested': item.quantity,
                        'available': available,
                        'message': f'Chỉ còn {available} sản phẩm'
                    })
        
        return issues


class CartItem(TimeStampedModel):
    """
    Cart line item.
    
    Stores product with quantity, price tracking,
    and stock validation.
    """
    
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Giỏ hàng'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='cart_items',
        verbose_name='Sản phẩm'
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name='Số lượng'
    )
    
    # Price when added (for comparison)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name='Đơn giá'
    )
    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name='Giá gốc'
    )
    
    # Attributes (for variants)
    selected_attributes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Thuộc tính đã chọn'
    )
    
    class Meta:
        verbose_name = 'Sản phẩm trong giỏ'
        verbose_name_plural = 'Sản phẩm trong giỏ'
        unique_together = ['cart', 'product']
        indexes = [
            models.Index(fields=['cart', 'product']),
        ]
    
    def __str__(self) -> str:
        return f"{self.quantity}x {self.product.name}"
    
    # --- Computed Properties ---
    
    @property
    def subtotal(self) -> Decimal:
        """Line item total."""
        return self.unit_price * self.quantity
    
    @property
    def savings(self) -> Decimal:
        """Discount from original price."""
        if self.original_price and self.original_price > self.unit_price:
            return (self.original_price - self.unit_price) * self.quantity
        return Decimal('0')
    
    @property
    def is_on_sale(self) -> bool:
        """Check if item is on sale."""
        return self.original_price and self.original_price > self.unit_price
    
    @property
    def current_product_price(self) -> Decimal:
        """Get current price from product."""
        return self.product.sale_price or self.product.price
    
    @property
    def has_price_changed(self) -> bool:
        """Check if product price changed since added."""
        return self.unit_price != self.current_product_price
    
    @property
    def price_difference(self) -> Decimal:
        """Difference from current price (positive = increase)."""
        return self.current_product_price - self.unit_price
    
    @property
    def is_out_of_stock(self) -> bool:
        """Check if product is out of stock."""
        if hasattr(self.product, 'stock'):
            return self.product.stock.available_quantity == 0
        return False
    
    @property
    def available_quantity(self) -> int:
        """Get available stock quantity."""
        if hasattr(self.product, 'stock'):
            return self.product.stock.available_quantity
        return 999
    
    @property
    def exceeds_stock(self) -> bool:
        """Check if quantity exceeds available stock."""
        return self.quantity > self.available_quantity
    
    def save(self, *args, **kwargs):
        # Set unit price if not provided
        if not self.unit_price:
            self.unit_price = self.product.sale_price or self.product.price
        
        if not self.original_price:
            self.original_price = self.product.price
        
        # Clamp quantity to stock (optional - can be disabled)
        # if hasattr(self.product, 'stock'):
        #     max_qty = self.product.stock.available_quantity
        #     if self.quantity > max_qty:
        #         self.quantity = max(max_qty, 1)
        
        super().save(*args, **kwargs)


class SavedForLater(TimeStampedModel):
    """
    Saved for later items (wishlist within cart).
    """
    
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='saved_items',
        verbose_name='Giỏ hàng'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='saved_in_carts',
        verbose_name='Sản phẩm'
    )
    price_when_saved = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name='Giá khi lưu'
    )
    
    class Meta:
        verbose_name = 'Lưu để mua sau'
        verbose_name_plural = 'Lưu để mua sau'
        unique_together = ['cart', 'product']
    
    def __str__(self) -> str:
        return f"Saved: {self.product.name}"
    
    @property
    def current_price(self) -> Decimal:
        """Current product price."""
        return self.product.sale_price or self.product.price
    
    @property
    def price_dropped(self) -> bool:
        """Check if price is lower than when saved."""
        return self.current_price < self.price_when_saved
    
    @property
    def price_change(self) -> Decimal:
        """Price difference (negative = dropped)."""
        return self.current_price - self.price_when_saved


class CartEvent(TimeStampedModel):
    """
    Cart analytics event log.
    
    Tracks cart actions for analytics and abandonment.
    """
    
    class EventType(models.TextChoices):
        ADD_ITEM = 'add_item', 'Thêm sản phẩm'
        UPDATE_QUANTITY = 'update_qty', 'Cập nhật số lượng'
        REMOVE_ITEM = 'remove_item', 'Xóa sản phẩm'
        APPLY_COUPON = 'apply_coupon', 'Áp dụng mã giảm giá'
        SAVE_FOR_LATER = 'save_later', 'Lưu để mua sau'
        CHECKOUT_START = 'checkout_start', 'Bắt đầu thanh toán'
        CHECKOUT_COMPLETE = 'checkout_done', 'Hoàn thành thanh toán'
        ABANDONED = 'abandoned', 'Bỏ giỏ hàng'
    
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name='Giỏ hàng'
    )
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        verbose_name='Loại sự kiện'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Sản phẩm'
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Dữ liệu'
    )
    
    class Meta:
        verbose_name = 'Sự kiện giỏ hàng'
        verbose_name_plural = 'Sự kiện giỏ hàng'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cart', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.cart}: {self.event_type}"
