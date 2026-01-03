"""
Store Wishlist - Production-Ready Models.

Comprehensive wishlist system with:
- Wishlist: Named collections (default + custom)
- WishlistItem: Products with price tracking
- WishlistShare: Sharing wishlists publicly
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.common.core.models import TimeStampedModel, UUIDModel


class Wishlist(UUIDModel):
    """
    Wishlist collection.
    
    Users can have multiple wishlists (default + custom named lists).
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlists',
        verbose_name='Người dùng'
    )
    
    name = models.CharField(max_length=100, default='Yêu thích', verbose_name='Tên danh sách')
    description = models.TextField(blank=True, verbose_name='Mô tả')
    
    is_default = models.BooleanField(default=False, verbose_name='Mặc định')
    is_public = models.BooleanField(default=False, verbose_name='Công khai')
    
    # Sharing
    share_token = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        null=True,
        verbose_name='Token chia sẻ'
    )
    
    class Meta:
        verbose_name = 'Danh sách yêu thích'
        verbose_name_plural = 'Danh sách yêu thích'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default per user
        if self.is_default:
            Wishlist.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        # Generate share token if public
        if self.is_public and not self.share_token:
            self.share_token = get_random_string(32)
        
        super().save(*args, **kwargs)
    
    @property
    def items_count(self) -> int:
        """Number of items in wishlist."""
        return self.items.count()
    
    @property
    def total_value(self) -> Decimal:
        """Total value of items at current prices."""
        return sum(
            item.product.current_price
            for item in self.items.select_related('product')
        )
    
    @property
    def share_url(self) -> str:
        """Get shareable URL."""
        if self.share_token:
            return f"/wishlist/shared/{self.share_token}/"
        return ''
    
    def generate_share_token(self) -> str:
        """Generate or regenerate share token."""
        self.share_token = get_random_string(32)
        self.is_public = True
        self.save(update_fields=['share_token', 'is_public', 'updated_at'])
        return self.share_token
    
    def revoke_share(self) -> None:
        """Revoke sharing."""
        self.share_token = None
        self.is_public = False
        self.save(update_fields=['share_token', 'is_public', 'updated_at'])


class WishlistItem(TimeStampedModel):
    """
    Item in a wishlist with price tracking.
    """
    
    class Priority(models.TextChoices):
        HIGH = 'high', 'Cao'
        MEDIUM = 'medium', 'Trung bình'
        LOW = 'low', 'Thấp'
    
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Danh sách'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='wishlist_entries',
        verbose_name='Sản phẩm'
    )
    
    # User notes
    note = models.TextField(blank=True, verbose_name='Ghi chú')
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name='Ưu tiên'
    )
    
    # Price tracking
    price_when_added = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name='Giá khi thêm'
    )
    lowest_price_seen = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name='Giá thấp nhất'
    )
    notify_on_sale = models.BooleanField(
        default=True,
        verbose_name='Thông báo khi giảm giá'
    )
    target_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name='Giá mong muốn'
    )
    
    # Notification sent
    last_price_alert_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Thông báo giá cuối'
    )
    
    class Meta:
        verbose_name = 'Sản phẩm yêu thích'
        verbose_name_plural = 'Sản phẩm yêu thích'
        unique_together = ['wishlist', 'product']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wishlist', '-created_at']),
            models.Index(fields=['product']),
        ]
    
    def __str__(self) -> str:
        return f"{self.wishlist.user.email} - {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Track price when added
        if not self.price_when_added:
            self.price_when_added = self.product.current_price
            self.lowest_price_seen = self.product.current_price
        
        super().save(*args, **kwargs)
    
    @property
    def user(self):
        """Get user from wishlist."""
        return self.wishlist.user
    
    @property
    def current_price(self) -> Decimal:
        """Get current product price."""
        return self.product.current_price
    
    @property
    def price_change(self) -> Decimal:
        """Price change since added."""
        if self.price_when_added:
            return self.current_price - self.price_when_added
        return Decimal('0')
    
    @property
    def price_change_percentage(self) -> int:
        """Price change percentage."""
        if self.price_when_added and self.price_when_added > 0:
            change = ((self.current_price - self.price_when_added) / self.price_when_added) * 100
            return int(change)
        return 0
    
    @property
    def is_price_dropped(self) -> bool:
        """Check if price has dropped."""
        return self.price_change < 0
    
    @property
    def is_on_sale(self) -> bool:
        """Check if product is on sale."""
        return self.product.is_on_sale
    
    @property
    def is_in_stock(self) -> bool:
        """Check if product is in stock."""
        return self.product.in_stock
    
    @property
    def reached_target_price(self) -> bool:
        """Check if target price is reached."""
        if self.target_price:
            return self.current_price <= self.target_price
        return False
    
    def update_lowest_price(self) -> bool:
        """Update lowest price if current is lower."""
        if self.lowest_price_seen is None or self.current_price < self.lowest_price_seen:
            self.lowest_price_seen = self.current_price
            self.save(update_fields=['lowest_price_seen', 'updated_at'])
            return True
        return False
    
    def should_notify(self) -> bool:
        """Check if should send price alert."""
        if not self.notify_on_sale:
            return False
        
        # Don't notify more than once per day
        if self.last_price_alert_at:
            hours_since = (timezone.now() - self.last_price_alert_at).total_seconds() / 3600
            if hours_since < 24:
                return False
        
        # Notify if on sale or target price reached
        return self.is_on_sale or self.reached_target_price
    
    def mark_notified(self):
        """Mark as notified."""
        self.last_price_alert_at = timezone.now()
        self.save(update_fields=['last_price_alert_at', 'updated_at'])


# Keep backward compatibility
class WishlistItemLegacy(TimeStampedModel):
    """
    Legacy simple wishlist item for backward compatibility.
    Maps to default wishlist.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist_items_legacy',
        verbose_name='Người dùng'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='wishlist_entries_legacy',
        verbose_name='Sản phẩm'
    )
    
    class Meta:
        verbose_name = 'Wishlist Item (Legacy)'
        verbose_name_plural = 'Wishlist Items (Legacy)'
        unique_together = ['user', 'product']
        ordering = ['-created_at']
        managed = False  # Don't create table
        db_table = 'wishlist_wishlistitem'  # Map to existing table
