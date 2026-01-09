"""Store Wishlist - Wishlist Models."""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from apps.common.core.models import TimeStampedModel, UUIDModel


class Wishlist(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlists', verbose_name='User')
    name = models.CharField(max_length=100, default='Favorites', verbose_name='Name')
    description = models.TextField(blank=True, verbose_name='Description')
    is_default = models.BooleanField(default=False, verbose_name='Default')
    is_public = models.BooleanField(default=False, verbose_name='Public')
    share_token = models.CharField(max_length=32, unique=True, blank=True, null=True, verbose_name='Share Token')

    class Meta:
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'
        ordering = ['-is_default', '-created_at']

    def __str__(self) -> str:
        return f"{self.user.email} - {self.name}"

    def save(self, *args, **kwargs):
        if self.is_default:
            Wishlist.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        if self.is_public and not self.share_token:
            self.share_token = get_random_string(32)
        super().save(*args, **kwargs)

    @property
    def items_count(self) -> int:
        return self.items.count()

    @property
    def total_value(self) -> Decimal:
        return sum(item.product.current_price for item in self.items.select_related('product'))

    @property
    def share_url(self) -> str:
        if self.share_token:
            return f"/wishlist/shared/{self.share_token}/"
        return ''

    def generate_share_token(self) -> str:
        self.share_token = get_random_string(32)
        self.is_public = True
        self.save(update_fields=['share_token', 'is_public', 'updated_at'])
        return self.share_token

    def revoke_share(self) -> None:
        self.share_token = None
        self.is_public = False
        self.save(update_fields=['share_token', 'is_public', 'updated_at'])


class WishlistItem(TimeStampedModel):
    class Priority(models.TextChoices):
        HIGH = 'high', 'High'
        MEDIUM = 'medium', 'Medium'
        LOW = 'low', 'Low'

    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items', verbose_name='Wishlist')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='wishlist_entries', verbose_name='Product')
    note = models.TextField(blank=True, verbose_name='Note')
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM, verbose_name='Priority')
    price_when_added = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Price When Added')
    lowest_price_seen = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Lowest Price')
    notify_on_sale = models.BooleanField(default=True, verbose_name='Notify on Sale')
    target_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Target Price')
    last_price_alert_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Alert')

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        unique_together = ['wishlist', 'product']
        ordering = ['-created_at']
        indexes = [models.Index(fields=['wishlist', '-created_at']), models.Index(fields=['product'])]

    def __str__(self) -> str:
        return f"{self.wishlist.user.email} - {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.price_when_added:
            self.price_when_added = self.product.current_price
            self.lowest_price_seen = self.product.current_price
        super().save(*args, **kwargs)

    @property
    def user(self):
        return self.wishlist.user

    @property
    def current_price(self) -> Decimal:
        return self.product.current_price

    @property
    def price_change(self) -> Decimal:
        if self.price_when_added:
            return self.current_price - self.price_when_added
        return Decimal('0')

    @property
    def price_change_percentage(self) -> int:
        if self.price_when_added and self.price_when_added > 0:
            change = ((self.current_price - self.price_when_added) / self.price_when_added) * 100
            return int(change)
        return 0

    @property
    def is_price_dropped(self) -> bool:
        return self.price_change < 0

    @property
    def is_on_sale(self) -> bool:
        return self.product.is_sale_active if hasattr(self.product, 'is_sale_active') else False

    @property
    def is_in_stock(self) -> bool:
        return self.product.in_stock if hasattr(self.product, 'in_stock') else True

    @property
    def reached_target_price(self) -> bool:
        if self.target_price:
            return self.current_price <= self.target_price
        return False

    def update_lowest_price(self) -> bool:
        if self.lowest_price_seen is None or self.current_price < self.lowest_price_seen:
            self.lowest_price_seen = self.current_price
            self.save(update_fields=['lowest_price_seen', 'updated_at'])
            return True
        return False

    def should_notify(self) -> bool:
        if not self.notify_on_sale:
            return False
        if self.last_price_alert_at:
            hours_since = (timezone.now() - self.last_price_alert_at).total_seconds() / 3600
            if hours_since < 24:
                return False
        return self.is_on_sale or self.reached_target_price

    def mark_notified(self):
        self.last_price_alert_at = timezone.now()
        self.save(update_fields=['last_price_alert_at', 'updated_at'])
