"""
Store Marketing - Production-Ready Models.

Comprehensive marketing models:
- Coupon: Discount codes with usage tracking
- CouponUsage: Per-user coupon usage history
- Banner: Homepage/category banners
- FlashSale: Time-limited sales events
- Campaign: Marketing campaigns
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.common.core.models import TimeStampedModel, UUIDModel
from apps.common.core.storage import banner_image_path


class Coupon(TimeStampedModel):
    """
    Discount coupon with comprehensive validation.
    """
    
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Phần trăm'
        FIXED = 'fixed', 'Số tiền cố định'
        FREE_SHIPPING = 'free_shipping', 'Miễn phí vận chuyển'
    
    class ApplyTo(models.TextChoices):
        ALL = 'all', 'Tất cả sản phẩm'
        CATEGORY = 'category', 'Theo danh mục'
        PRODUCT = 'product', 'Sản phẩm cụ thể'
        BRAND = 'brand', 'Theo thương hiệu'
    
    # Basic info
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='Mã giảm giá'
    )
    name = models.CharField(max_length=100, blank=True, verbose_name='Tên coupon')
    description = models.TextField(blank=True, verbose_name='Mô tả')
    
    # Discount configuration
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
        verbose_name='Loại giảm giá'
    )
    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name='Giá trị giảm'
    )
    
    # Limits
    min_order_value = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Giá trị đơn tối thiểu'
    )
    max_discount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name='Giảm tối đa'
    )
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Giới hạn tổng'
    )
    usage_limit_per_user = models.PositiveIntegerField(
        default=1,
        verbose_name='Giới hạn/người'
    )
    used_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Đã sử dụng'
    )
    
    # Validity
    valid_from = models.DateTimeField(verbose_name='Hiệu lực từ')
    valid_until = models.DateTimeField(verbose_name='Hiệu lực đến')
    
    # Targeting
    apply_to = models.CharField(
        max_length=20,
        choices=ApplyTo.choices,
        default=ApplyTo.ALL,
        verbose_name='Áp dụng cho'
    )
    applicable_categories = models.ManyToManyField(
        'catalog.Category',
        blank=True,
        related_name='coupons',
        verbose_name='Danh mục áp dụng'
    )
    applicable_products = models.ManyToManyField(
        'catalog.Product',
        blank=True,
        related_name='coupons',
        verbose_name='Sản phẩm áp dụng'
    )
    applicable_brands = models.ManyToManyField(
        'catalog.Brand',
        blank=True,
        related_name='coupons',
        verbose_name='Thương hiệu áp dụng'
    )
    
    # User targeting
    first_order_only = models.BooleanField(
        default=False,
        verbose_name='Chỉ đơn đầu tiên'
    )
    specific_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='exclusive_coupons',
        verbose_name='Người dùng cụ thể'
    )
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Hoạt động')
    is_public = models.BooleanField(default=True, verbose_name='Hiển thị công khai')
    
    class Meta:
        verbose_name = 'Mã giảm giá'
        verbose_name_plural = 'Mã giảm giá'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'valid_from', 'valid_until']),
        ]
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name or self.get_discount_display()}"
    
    def get_discount_display(self) -> str:
        """Get human-readable discount."""
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return f"{self.discount_value}%"
        elif self.discount_type == self.DiscountType.FREE_SHIPPING:
            return "Miễn phí ship"
        return f"{self.discount_value:,.0f}₫"
    
    @property
    def is_valid(self) -> bool:
        """Check if coupon is currently valid."""
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
        """Check if coupon is expired."""
        return timezone.now() > self.valid_until
    
    @property
    def remaining_uses(self) -> int:
        """Get remaining usage count."""
        if self.usage_limit is None:
            return float('inf')
        return max(0, self.usage_limit - self.used_count)
    
    @property
    def days_until_expiry(self) -> int:
        """Days until expiry."""
        delta = self.valid_until - timezone.now()
        return max(0, delta.days)
    
    def can_use(self, user, order_total: Decimal) -> tuple:
        """
        Check if coupon can be used.
        
        Returns (can_use: bool, reason: str)
        """
        if not self.is_active:
            return False, 'Mã giảm giá không còn hoạt động'
        
        now = timezone.now()
        if now < self.valid_from:
            return False, 'Mã giảm giá chưa có hiệu lực'
        if now > self.valid_until:
            return False, 'Mã giảm giá đã hết hạn'
        
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, 'Mã giảm giá đã hết lượt sử dụng'
        
        if order_total < self.min_order_value:
            return False, f'Đơn hàng tối thiểu {self.min_order_value:,.0f}₫'
        
        if user and user.is_authenticated:
            # Check per-user limit
            user_usage = self.usages.filter(user=user).count()
            if user_usage >= self.usage_limit_per_user:
                return False, 'Bạn đã sử dụng hết lượt của mã này'
            
            # Check first order only
            if self.first_order_only:
                from apps.commerce.orders.models import Order
                has_orders = Order.objects.filter(user=user).exists()
                if has_orders:
                    return False, 'Mã này chỉ dành cho đơn hàng đầu tiên'
            
            # Check specific users
            if self.specific_users.exists() and not self.specific_users.filter(id=user.id).exists():
                return False, 'Mã giảm giá không hợp lệ'
        
        return True, ''
    
    def calculate_discount(self, order_total: Decimal, shipping_fee: Decimal = 0) -> Decimal:
        """Calculate discount amount for an order."""
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
        """Mark coupon as used."""
        self.used_count += 1
        self.save(update_fields=['used_count', 'updated_at'])
        
        usage = CouponUsage.objects.create(
            coupon=self,
            user=user,
            order_id=order_id
        )
        
        return usage


class CouponUsage(TimeStampedModel):
    """
    Track coupon usage per user.
    """
    
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='usages',
        verbose_name='Coupon'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupon_usages',
        verbose_name='Người dùng'
    )
    order_id = models.UUIDField(null=True, blank=True, verbose_name='Đơn hàng')
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Số tiền giảm'
    )
    
    class Meta:
        verbose_name = 'Lịch sử sử dụng coupon'
        verbose_name_plural = 'Lịch sử sử dụng coupon'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.coupon.code} - {self.user}"


class Banner(TimeStampedModel):
    """
    Promotional banner for homepage/category pages.
    """
    
    class Position(models.TextChoices):
        HERO = 'hero', 'Hero (chính)'
        SIDEBAR = 'sidebar', 'Sidebar'
        CATEGORY = 'category', 'Danh mục'
        POPUP = 'popup', 'Popup'
        FOOTER = 'footer', 'Footer'
    
    title = models.CharField(max_length=200, verbose_name='Tiêu đề')
    subtitle = models.CharField(max_length=300, blank=True, verbose_name='Phụ đề')
    image = models.ImageField(
        upload_to=banner_image_path,
        verbose_name='Hình ảnh'
    )
    image_mobile = models.ImageField(
        upload_to=banner_image_path,
        blank=True,
        null=True,
        verbose_name='Hình mobile'
    )
    
    # Link
    link_url = models.URLField(blank=True, verbose_name='Link URL')
    link_text = models.CharField(max_length=50, blank=True, verbose_name='Text nút')
    
    # Targeting
    position = models.CharField(
        max_length=20,
        choices=Position.choices,
        default=Position.HERO,
        verbose_name='Vị trí'
    )
    category = models.ForeignKey(
        'catalog.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='banners',
        verbose_name='Danh mục'
    )
    
    # Scheduling
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='Bắt đầu')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Kết thúc')
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Hoạt động')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Thứ tự')
    
    # Stats
    view_count = models.PositiveIntegerField(default=0, verbose_name='Lượt xem')
    click_count = models.PositiveIntegerField(default=0, verbose_name='Lượt click')
    
    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banner'
        ordering = ['sort_order', '-created_at']
    
    def __str__(self) -> str:
        return self.title
    
    @property
    def is_scheduled_active(self) -> bool:
        """Check if banner is active based on schedule."""
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
        """Calculate click-through rate."""
        if self.view_count == 0:
            return 0.0
        return round((self.click_count / self.view_count) * 100, 2)
    
    def increment_view(self):
        """Increment view count."""
        Banner.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)
    
    def increment_click(self):
        """Increment click count."""
        Banner.objects.filter(pk=self.pk).update(click_count=models.F('click_count') + 1)


class FlashSale(UUIDModel):
    """
    Time-limited flash sale event.
    """
    
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Đã lên lịch'
        ACTIVE = 'active', 'Đang diễn ra'
        ENDED = 'ended', 'Đã kết thúc'
        CANCELLED = 'cancelled', 'Đã hủy'
    
    name = models.CharField(max_length=200, verbose_name='Tên Flash Sale')
    description = models.TextField(blank=True, verbose_name='Mô tả')
    banner_image = models.ImageField(
        upload_to='flash_sales/',
        blank=True,
        null=True,
        verbose_name='Banner'
    )
    
    # Schedule
    start_time = models.DateTimeField(verbose_name='Bắt đầu')
    end_time = models.DateTimeField(verbose_name='Kết thúc')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        verbose_name='Trạng thái'
    )
    is_active = models.BooleanField(default=True, verbose_name='Hoạt động')
    
    class Meta:
        verbose_name = 'Flash Sale'
        verbose_name_plural = 'Flash Sale'
        ordering = ['-start_time']
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def is_ongoing(self) -> bool:
        """Check if flash sale is ongoing."""
        now = timezone.now()
        return self.is_active and self.start_time <= now <= self.end_time
    
    @property
    def is_upcoming(self) -> bool:
        """Check if flash sale is upcoming."""
        return self.is_active and timezone.now() < self.start_time
    
    @property
    def time_remaining(self) -> int:
        """Seconds remaining."""
        if not self.is_ongoing:
            return 0
        delta = self.end_time - timezone.now()
        return max(0, int(delta.total_seconds()))
    
    def update_status(self):
        """Update status based on time."""
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
    """
    Product in a flash sale with special pricing.
    """
    
    flash_sale = models.ForeignKey(
        FlashSale,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Flash Sale'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='flash_sale_items',
        verbose_name='Sản phẩm'
    )
    
    # Pricing
    flash_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name='Giá Flash Sale'
    )
    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name='Giá gốc'
    )
    
    # Limits
    quantity_limit = models.PositiveIntegerField(
        default=0,
        verbose_name='Số lượng giới hạn',
        help_text='0 = không giới hạn'
    )
    quantity_sold = models.PositiveIntegerField(
        default=0,
        verbose_name='Đã bán'
    )
    per_user_limit = models.PositiveIntegerField(
        default=1,
        verbose_name='Giới hạn/người'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Sản phẩm Flash Sale'
        verbose_name_plural = 'Sản phẩm Flash Sale'
        unique_together = [['flash_sale', 'product']]
        ordering = ['sort_order']
    
    def __str__(self) -> str:
        return f"{self.product.name} - {self.flash_sale.name}"
    
    @property
    def discount_percentage(self) -> int:
        """Calculate discount percentage."""
        if self.original_price <= 0:
            return 0
        return int(((self.original_price - self.flash_price) / self.original_price) * 100)
    
    @property
    def remaining_quantity(self) -> int:
        """Get remaining quantity."""
        if self.quantity_limit == 0:
            return float('inf')
        return max(0, self.quantity_limit - self.quantity_sold)
    
    @property
    def is_sold_out(self) -> bool:
        """Check if sold out."""
        return self.quantity_limit > 0 and self.quantity_sold >= self.quantity_limit
    
    @property
    def sold_percentage(self) -> int:
        """Percentage sold."""
        if self.quantity_limit == 0:
            return 0
        return min(100, int((self.quantity_sold / self.quantity_limit) * 100))
    
    def purchase(self, quantity: int = 1):
        """Record a purchase."""
        FlashSaleItem.objects.filter(pk=self.pk).update(
            quantity_sold=models.F('quantity_sold') + quantity
        )


class Campaign(UUIDModel):
    """
    Marketing campaign for tracking and analytics.
    """
    
    class Type(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        PUSH = 'push', 'Push Notification'
        SOCIAL = 'social', 'Social Media'
        ADS = 'ads', 'Quảng cáo'
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Nháp'
        SCHEDULED = 'scheduled', 'Đã lên lịch'
        ACTIVE = 'active', 'Đang chạy'
        PAUSED = 'paused', 'Tạm dừng'
        COMPLETED = 'completed', 'Hoàn thành'
    
    name = models.CharField(max_length=200, verbose_name='Tên campaign')
    description = models.TextField(blank=True)
    campaign_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.EMAIL,
        verbose_name='Loại'
    )
    
    # Schedule
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    
    # Targeting
    target_audience = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Đối tượng'
    )
    
    # Associated coupon
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns'
    )
    
    # Stats
    sent_count = models.PositiveIntegerField(default=0, verbose_name='Đã gửi')
    open_count = models.PositiveIntegerField(default=0, verbose_name='Đã mở')
    click_count = models.PositiveIntegerField(default=0, verbose_name='Đã click')
    conversion_count = models.PositiveIntegerField(default=0, verbose_name='Chuyển đổi')
    revenue = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name='Doanh thu'
    )
    
    class Meta:
        verbose_name = 'Campaign'
        verbose_name_plural = 'Campaign'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def open_rate(self) -> float:
        """Calculate open rate."""
        if self.sent_count == 0:
            return 0.0
        return round((self.open_count / self.sent_count) * 100, 2)
    
    @property
    def click_rate(self) -> float:
        """Calculate click rate."""
        if self.sent_count == 0:
            return 0.0
        return round((self.click_count / self.sent_count) * 100, 2)
    
    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate."""
        if self.click_count == 0:
            return 0.0
        return round((self.conversion_count / self.click_count) * 100, 2)
