"""Commerce Cart - Cart Models."""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import TimeStampedModel


class Cart(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='cart', verbose_name='User')
    session_key = models.CharField(max_length=255, null=True, blank=True, db_index=True, verbose_name='Session Key')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Expires At')
    coupon_code = models.CharField(max_length=50, blank=True, verbose_name='Coupon Code')
    coupon_discount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Coupon Discount')
    last_activity_at = models.DateTimeField(auto_now=True, verbose_name='Last Activity')
    abandonment_email_sent = models.BooleanField(default=False, verbose_name='Abandonment Email Sent')
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
        indexes = [models.Index(fields=['user']), models.Index(fields=['session_key']), models.Index(fields=['last_activity_at'])]

    def __str__(self) -> str:
        if self.user:
            return f"Cart: {self.user.email}"
        return f"Cart: {self.session_key[:20] if self.session_key else 'guest'}..."

    @property
    def is_empty(self) -> bool:
        return not self.items.exists()

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def unique_items(self) -> int:
        return self.items.count()

    @property
    def subtotal(self) -> Decimal:
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_savings(self) -> Decimal:
        return sum(item.savings for item in self.items.all())

    @property
    def total(self) -> Decimal:
        return max(self.subtotal - self.coupon_discount, Decimal('0'))

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def has_out_of_stock(self) -> bool:
        return any(item.is_out_of_stock for item in self.items.all())

    @property
    def saved_items_count(self) -> int:
        return self.saved_items.count()

    def add_item(self, product, quantity: int = 1, update_price: bool = True) -> 'CartItem':
        current_price = product.sale_price if hasattr(product, 'sale_price') and product.sale_price else product.price
        item, created = CartItem.objects.get_or_create(cart=self, product=product, defaults={'quantity': quantity, 'unit_price': current_price, 'original_price': product.price})
        if not created:
            item.quantity += quantity
            if update_price:
                item.unit_price = current_price
                item.original_price = product.price
            item.save(update_fields=['quantity', 'unit_price', 'original_price', 'updated_at'])
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])
        return item

    def update_item(self, item_id: int, quantity: int) -> 'CartItem':
        try:
            item = self.items.get(id=item_id)
        except CartItem.DoesNotExist:
            return None
        if quantity <= 0:
            item.delete()
            return None
        item.quantity = quantity
        item.save(update_fields=['quantity', 'updated_at'])
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])
        return item

    def remove_item(self, item_id: int) -> bool:
        deleted, _ = self.items.filter(id=item_id).delete()
        if deleted:
            self.last_activity_at = timezone.now()
            self.save(update_fields=['last_activity_at'])
        return deleted > 0

    def clear(self) -> int:
        count = self.items.count()
        self.items.all().delete()
        self.coupon_code = ''
        self.coupon_discount = 0
        self.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])
        return count

    def merge_with(self, other_cart: 'Cart') -> int:
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
        for saved in other_cart.saved_items.all():
            if not self.saved_items.filter(product=saved.product).exists():
                saved.cart = self
                saved.save(update_fields=['cart', 'updated_at'])
        other_cart.delete()
        return merged_count

    def save_for_later(self, item_id: int) -> 'SavedForLater':
        try:
            item = self.items.get(id=item_id)
        except CartItem.DoesNotExist:
            return None
        saved, created = SavedForLater.objects.get_or_create(cart=self, product=item.product, defaults={'price_when_saved': item.unit_price})
        item.delete()
        return saved

    def move_to_cart(self, saved_id: int) -> 'CartItem':
        try:
            saved = self.saved_items.get(id=saved_id)
        except SavedForLater.DoesNotExist:
            return None
        item = self.add_item(saved.product, quantity=1)
        saved.delete()
        return item

    def remove_coupon(self) -> None:
        self.coupon_code = ''
        self.coupon_discount = 0
        self.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])

    def validate_stock(self) -> list:
        issues = []
        for item in self.items.select_related('product').all():
            if not item.product.is_active:
                issues.append({'item_id': item.id, 'product_name': item.product.name, 'issue': 'unavailable', 'message': 'Product no longer available'})
            elif hasattr(item.product, 'stock'):
                available = item.product.stock.available_quantity
                if item.quantity > available:
                    issues.append({'item_id': item.id, 'product_name': item.product.name, 'issue': 'insufficient_stock', 'requested': item.quantity, 'available': available})
        return issues


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name='Cart')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='cart_items', verbose_name='Product')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Quantity')
    unit_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Unit Price')
    original_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Original Price')
    selected_attributes = models.JSONField(default=dict, blank=True, verbose_name='Attributes')

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = ['cart', 'product']
        indexes = [models.Index(fields=['cart', 'product'])]

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product.name}"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def savings(self) -> Decimal:
        if self.original_price and self.original_price > self.unit_price:
            return (self.original_price - self.unit_price) * self.quantity
        return Decimal('0')

    @property
    def is_on_sale(self) -> bool:
        return self.original_price and self.original_price > self.unit_price

    @property
    def current_product_price(self) -> Decimal:
        return self.product.sale_price if hasattr(self.product, 'sale_price') and self.product.sale_price else self.product.price

    @property
    def has_price_changed(self) -> bool:
        return self.unit_price != self.current_product_price

    @property
    def is_out_of_stock(self) -> bool:
        if hasattr(self.product, 'stock'):
            return self.product.stock.available_quantity == 0
        return False

    @property
    def available_quantity(self) -> int:
        if hasattr(self.product, 'stock'):
            return self.product.stock.available_quantity
        return 999

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.sale_price if hasattr(self.product, 'sale_price') and self.product.sale_price else self.product.price
        if not self.original_price:
            self.original_price = self.product.price
        super().save(*args, **kwargs)


class SavedForLater(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='saved_items', verbose_name='Cart')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='saved_in_carts', verbose_name='Product')
    price_when_saved = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Price When Saved')

    class Meta:
        verbose_name = 'Saved for Later'
        verbose_name_plural = 'Saved for Later'
        unique_together = ['cart', 'product']

    def __str__(self) -> str:
        return f"Saved: {self.product.name}"

    @property
    def current_price(self) -> Decimal:
        return self.product.sale_price if hasattr(self.product, 'sale_price') and self.product.sale_price else self.product.price

    @property
    def price_dropped(self) -> bool:
        return self.current_price < self.price_when_saved


class CartEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        ADD_ITEM = 'add_item', 'Add Item'
        UPDATE_QUANTITY = 'update_qty', 'Update Quantity'
        REMOVE_ITEM = 'remove_item', 'Remove Item'
        APPLY_COUPON = 'apply_coupon', 'Apply Coupon'
        SAVE_FOR_LATER = 'save_later', 'Save for Later'
        CHECKOUT_START = 'checkout_start', 'Checkout Start'
        CHECKOUT_COMPLETE = 'checkout_done', 'Checkout Complete'
        ABANDONED = 'abandoned', 'Abandoned'

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='events', verbose_name='Cart')
    event_type = models.CharField(max_length=20, choices=EventType.choices, verbose_name='Event Type')
    product = models.ForeignKey('catalog.Product', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Product')
    data = models.JSONField(default=dict, blank=True, verbose_name='Data')

    class Meta:
        verbose_name = 'Cart Event'
        verbose_name_plural = 'Cart Events'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['cart', '-created_at']), models.Index(fields=['event_type', '-created_at'])]

    def __str__(self) -> str:
        return f"{self.cart}: {self.event_type}"
