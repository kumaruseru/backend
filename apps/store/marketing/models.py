"""Store Marketing - Marketing Models."""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.common.core.models import TimeStampedModel, UUIDModel


class Coupon(TimeStampedModel):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED = 'fixed', 'Fixed Amount'
        FREE_SHIPPING = 'free_shipping', 'Free Shipping'

    class ApplyTo(models.TextChoices):
        ALL = 'all', 'All Products'
        CATEGORY = 'category', 'By Category'
        PRODUCT = 'product', 'Specific Products'
        BRAND = 'brand', 'By Brand'

    code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Code')
    name = models.CharField(max_length=100, blank=True, verbose_name='Name')
    description = models.TextField(blank=True, verbose_name='Description')
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE, verbose_name='Discount Type')
    discount_value = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Discount Value')
    min_order_value = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Min Order Value')
    max_discount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Max Discount')
    usage_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name='Total Usage Limit')
    usage_limit_per_user = models.PositiveIntegerField(default=1, verbose_name='Limit per User')
    used_count = models.PositiveIntegerField(default=0, verbose_name='Used Count')
    valid_from = models.DateTimeField(verbose_name='Valid From')
    valid_until = models.DateTimeField(verbose_name='Valid Until')
    apply_to = models.CharField(max_length=20, choices=ApplyTo.choices, default=ApplyTo.ALL, verbose_name='Apply To')
    applicable_categories = models.ManyToManyField('catalog.Category', blank=True, related_name='coupons', verbose_name='Categories')
    applicable_products = models.ManyToManyField('catalog.Product', blank=True, related_name='coupons', verbose_name='Products')
    applicable_brands = models.ManyToManyField('catalog.Brand', blank=True, related_name='coupons', verbose_name='Brands')
    first_order_only = models.BooleanField(default=False, verbose_name='First Order Only')
    specific_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='exclusive_coupons', verbose_name='Specific Users')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Active')
    is_public = models.BooleanField(default=True, verbose_name='Public')

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['code']), models.Index(fields=['is_active', 'valid_from', 'valid_until'])]

    def __str__(self) -> str:
        return f"{self.code} - {self.name or self.get_discount_display()}"

    def get_discount_display(self) -> str:
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return f"{self.discount_value}%"
        elif self.discount_type == self.DiscountType.FREE_SHIPPING:
            return "Free Shipping"
        return f"{self.discount_value:,.0f}₫"

    @property
    def is_valid(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.valid_until

    @property
    def remaining_uses(self) -> int:
        if self.usage_limit is None:
            return 999999
        return max(0, self.usage_limit - self.used_count)

    @property
    def days_until_expiry(self) -> int:
        delta = self.valid_until - timezone.now()
        return max(0, delta.days)

    def can_use(self, user, order_total: Decimal) -> tuple:
        if not self.is_active:
            return False, 'Coupon is not active'
        now = timezone.now()
        if now < self.valid_from:
            return False, 'Coupon is not yet valid'
        if now > self.valid_until:
            return False, 'Coupon has expired'
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, 'Coupon usage limit reached'
        if order_total < self.min_order_value:
            return False, f'Minimum order value: {self.min_order_value:,.0f}₫'
        if user and user.is_authenticated:
            user_usage = self.usages.filter(user=user).count()
            if user_usage >= self.usage_limit_per_user:
                return False, 'You have reached usage limit for this coupon'
            if self.first_order_only:
                from apps.commerce.orders.models import Order
                has_orders = Order.objects.filter(user=user).exists()
                if has_orders:
                    return False, 'This coupon is for first order only'
            if self.specific_users.exists() and not self.specific_users.filter(id=user.id).exists():
                return False, 'Invalid coupon code'
        return True, ''

    def calculate_discount(self, order_total: Decimal, shipping_fee: Decimal = 0) -> Decimal:
        if order_total < self.min_order_value:
            return Decimal('0')
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = order_total * (self.discount_value / 100)
        elif self.discount_type == self.DiscountType.FREE_SHIPPING:
            discount = shipping_fee
        else:
            discount = self.discount_value
        if self.max_discount:
            discount = min(discount, self.max_discount)
        return discount

    def use(self, user=None, order_id=None) -> 'CouponUsage':
        self.used_count += 1
        self.save(update_fields=['used_count', 'updated_at'])
        usage = CouponUsage.objects.create(coupon=self, user=user, order_id=order_id)
        return usage


class CouponUsage(TimeStampedModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages', verbose_name='Coupon')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='coupon_usages', verbose_name='User')
    order_id = models.UUIDField(null=True, blank=True, verbose_name='Order')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Discount Amount')

    class Meta:
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.coupon.code} - {self.user}"


class Banner(TimeStampedModel):
    class Position(models.TextChoices):
        HERO = 'hero', 'Hero'
        SIDEBAR = 'sidebar', 'Sidebar'
        CATEGORY = 'category', 'Category'
        POPUP = 'popup', 'Popup'
        FOOTER = 'footer', 'Footer'

    title = models.CharField(max_length=200, verbose_name='Title')
    subtitle = models.CharField(max_length=300, blank=True, verbose_name='Subtitle')
    image = models.ImageField(upload_to='banners/', verbose_name='Image')
    image_mobile = models.ImageField(upload_to='banners/', blank=True, null=True, verbose_name='Mobile Image')
    link_url = models.URLField(blank=True, verbose_name='Link URL')
    link_text = models.CharField(max_length=50, blank=True, verbose_name='Button Text')
    position = models.CharField(max_length=20, choices=Position.choices, default=Position.HERO, verbose_name='Position')
    category = models.ForeignKey('catalog.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='banners', verbose_name='Category')
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='Start Date')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='End Date')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Active')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')
    view_count = models.PositiveIntegerField(default=0, verbose_name='Views')
    click_count = models.PositiveIntegerField(default=0, verbose_name='Clicks')

    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'
        ordering = ['sort_order', '-created_at']

    def __str__(self) -> str:
        return self.title

    @property
    def is_scheduled_active(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    @property
    def click_rate(self) -> float:
        if self.view_count == 0:
            return 0.0
        return round((self.click_count / self.view_count) * 100, 2)

    def increment_view(self):
        Banner.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)

    def increment_click(self):
        Banner.objects.filter(pk=self.pk).update(click_count=models.F('click_count') + 1)


class FlashSale(UUIDModel):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        ACTIVE = 'active', 'Active'
        ENDED = 'ended', 'Ended'
        CANCELLED = 'cancelled', 'Cancelled'

    name = models.CharField(max_length=200, verbose_name='Name')
    description = models.TextField(blank=True, verbose_name='Description')
    banner_image = models.ImageField(upload_to='flash_sales/', blank=True, null=True, verbose_name='Banner')
    start_time = models.DateTimeField(verbose_name='Start Time')
    end_time = models.DateTimeField(verbose_name='End Time')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED, verbose_name='Status')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Flash Sale'
        verbose_name_plural = 'Flash Sales'
        ordering = ['-start_time']

    def __str__(self) -> str:
        return self.name

    @property
    def is_ongoing(self) -> bool:
        now = timezone.now()
        return self.is_active and self.start_time <= now <= self.end_time

    @property
    def is_upcoming(self) -> bool:
        return self.is_active and timezone.now() < self.start_time

    @property
    def time_remaining(self) -> int:
        if not self.is_ongoing:
            return 0
        delta = self.end_time - timezone.now()
        return max(0, int(delta.total_seconds()))

    def update_status(self):
        now = timezone.now()
        if now < self.start_time:
            new_status = self.Status.SCHEDULED
        elif now <= self.end_time:
            new_status = self.Status.ACTIVE
        else:
            new_status = self.Status.ENDED
        if self.status != new_status and self.status != self.Status.CANCELLED:
            self.status = new_status
            self.save(update_fields=['status', 'updated_at'])


class FlashSaleItem(TimeStampedModel):
    flash_sale = models.ForeignKey(FlashSale, on_delete=models.CASCADE, related_name='items', verbose_name='Flash Sale')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='flash_sale_items', verbose_name='Product')
    flash_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Flash Price')
    original_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Original Price')
    quantity_limit = models.PositiveIntegerField(default=0, verbose_name='Quantity Limit', help_text='0 = unlimited')
    quantity_sold = models.PositiveIntegerField(default=0, verbose_name='Sold')
    per_user_limit = models.PositiveIntegerField(default=1, verbose_name='Limit per User')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Flash Sale Item'
        verbose_name_plural = 'Flash Sale Items'
        unique_together = [['flash_sale', 'product']]
        ordering = ['sort_order']

    def __str__(self) -> str:
        return f"{self.product.name} - {self.flash_sale.name}"

    @property
    def discount_percentage(self) -> int:
        if self.original_price <= 0:
            return 0
        return int(((self.original_price - self.flash_price) / self.original_price) * 100)

    @property
    def remaining_quantity(self) -> int:
        if self.quantity_limit == 0:
            return 999999
        return max(0, self.quantity_limit - self.quantity_sold)

    @property
    def is_sold_out(self) -> bool:
        return self.quantity_limit > 0 and self.quantity_sold >= self.quantity_limit

    @property
    def sold_percentage(self) -> int:
        if self.quantity_limit == 0:
            return 0
        return min(100, int((self.quantity_sold / self.quantity_limit) * 100))

    def purchase(self, quantity: int = 1):
        FlashSaleItem.objects.filter(pk=self.pk).update(quantity_sold=models.F('quantity_sold') + quantity)


class Campaign(UUIDModel):
    class Type(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        PUSH = 'push', 'Push Notification'
        SOCIAL = 'social', 'Social Media'
        ADS = 'ads', 'Ads'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'

    name = models.CharField(max_length=200, verbose_name='Name')
    description = models.TextField(blank=True)
    campaign_type = models.CharField(max_length=20, choices=Type.choices, default=Type.EMAIL, verbose_name='Type')
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    target_audience = models.JSONField(default=dict, blank=True, verbose_name='Target Audience')
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    sent_count = models.PositiveIntegerField(default=0, verbose_name='Sent')
    open_count = models.PositiveIntegerField(default=0, verbose_name='Opened')
    click_count = models.PositiveIntegerField(default=0, verbose_name='Clicked')
    conversion_count = models.PositiveIntegerField(default=0, verbose_name='Conversions')
    revenue = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Revenue')

    class Meta:
        verbose_name = 'Campaign'
        verbose_name_plural = 'Campaigns'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.name

    @property
    def open_rate(self) -> float:
        if self.sent_count == 0:
            return 0.0
        return round((self.open_count / self.sent_count) * 100, 2)

    @property
    def click_rate(self) -> float:
        if self.sent_count == 0:
            return 0.0
        return round((self.click_count / self.sent_count) * 100, 2)

    @property
    def conversion_rate(self) -> float:
        if self.click_count == 0:
            return 0.0
        return round((self.conversion_count / self.click_count) * 100, 2)
