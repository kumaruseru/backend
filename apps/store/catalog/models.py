"""
Store Catalog - Production-Ready Domain Models.

Product catalog models:
- Category: Hierarchical product categories with SEO
- Brand: Product brands with logo
- Product: Main product entity (aggregate root) with full SEO
- ProductImage: Product images with optimization
- ProductTag: Product tagging for search/filter
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from apps.common.core.models import TimeStampedModel, UUIDModel
from apps.common.core.storage import category_image_path, brand_logo_path, product_image_path


class Category(TimeStampedModel):
    """
    Product category with hierarchical structure.
    
    Supports parent-child relationships for nested categories
    with SEO metadata and caching support.
    """
    
    name = models.CharField(
        max_length=100,
        verbose_name='Tên danh mục'
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name='Slug'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Mô tả'
    )
    image = models.ImageField(
        upload_to=category_image_path,
        blank=True,
        null=True,
        verbose_name='Hình ảnh'
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Icon class'
    )
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Danh mục cha'
    )
    
    # SEO
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='Meta title')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='Meta description')
    
    # Status and ordering
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Hoạt động')
    is_featured = models.BooleanField(default=False, verbose_name='Nổi bật')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Thứ tự')
    
    # Cache fields
    _cached_product_count = models.PositiveIntegerField(default=0, verbose_name='Cache số SP')
    
    class Meta:
        verbose_name = 'Danh mục'
        verbose_name_plural = 'Danh mục'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
            original_slug = self.slug
            counter = 1
            while Category.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    @property
    def product_count(self) -> int:
        """Count of active products in this category."""
        return self.products.filter(is_active=True).count()
    
    @property
    def total_product_count(self) -> int:
        """Count including child categories."""
        count = self.product_count
        for child in self.children.filter(is_active=True):
            count += child.total_product_count
        return count
    
    @property
    def full_path(self) -> str:
        """Get full category path."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name
    
    @property
    def level(self) -> int:
        """Get depth level in hierarchy (0 = root)."""
        if self.parent:
            return self.parent.level + 1
        return 0
    
    @property
    def ancestors(self) -> list:
        """Get list of ancestor categories."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors
    
    def get_all_children_ids(self) -> list:
        """Get all descendant category IDs for filtering."""
        ids = [self.id]
        for child in self.children.all():
            ids.extend(child.get_all_children_ids())
        return ids


class Brand(TimeStampedModel):
    """
    Product brand entity.
    """
    
    name = models.CharField(max_length=100, unique=True, verbose_name='Tên thương hiệu')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Slug')
    logo = models.ImageField(
        upload_to=brand_logo_path,
        blank=True,
        null=True,
        verbose_name='Logo'
    )
    description = models.TextField(blank=True, verbose_name='Mô tả')
    website = models.URLField(blank=True, verbose_name='Website')
    
    # SEO
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Hoạt động')
    is_featured = models.BooleanField(default=False, verbose_name='Nổi bật')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Thứ tự')
    
    class Meta:
        verbose_name = 'Thương hiệu'
        verbose_name_plural = 'Thương hiệu'
        ordering = ['sort_order', 'name']
    
    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)
    
    @property
    def product_count(self) -> int:
        return self.products.filter(is_active=True).count()


class ProductTag(TimeStampedModel):
    """
    Product tagging for better search and filtering.
    """
    
    name = models.CharField(max_length=50, unique=True, verbose_name='Tên tag')
    slug = models.SlugField(max_length=50, unique=True, verbose_name='Slug')
    
    class Meta:
        verbose_name = 'Tag sản phẩm'
        verbose_name_plural = 'Tag sản phẩm'
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    """Custom queryset for Product model."""
    
    def active(self):
        """Filter only active products."""
        return self.filter(is_active=True)
    
    def featured(self):
        """Filter featured products."""
        return self.filter(is_featured=True, is_active=True)
    
    def new_arrivals(self, days=30):
        """Products created in last N days."""
        since = timezone.now() - timezone.timedelta(days=days)
        return self.filter(is_active=True, created_at__gte=since)
    
    def on_sale(self):
        """Products currently on sale."""
        return self.filter(
            is_active=True,
            sale_price__isnull=False,
            sale_price__gt=0
        ).exclude(sale_price__gte=models.F('price'))
    
    def in_stock(self):
        """Filter products that are in stock."""
        return self.filter(stock__quantity__gt=0)
    
    def in_category(self, category):
        """Filter by category including children."""
        if hasattr(category, 'get_all_children_ids'):
            return self.filter(category_id__in=category.get_all_children_ids())
        return self.filter(category=category)
    
    def in_price_range(self, min_price=None, max_price=None):
        """Filter by price range."""
        qs = self
        if min_price is not None:
            qs = qs.filter(
                models.Q(sale_price__gte=min_price) | 
                models.Q(sale_price__isnull=True, price__gte=min_price)
            )
        if max_price is not None:
            qs = qs.filter(
                models.Q(sale_price__lte=max_price, sale_price__gt=0) |
                models.Q(sale_price__isnull=True, price__lte=max_price)
            )
        return qs
    
    def search(self, query):
        """Full text search."""
        return self.filter(
            models.Q(name__icontains=query) |
            models.Q(description__icontains=query) |
            models.Q(sku__icontains=query) |
            models.Q(brand__name__icontains=query)
        )
    
    def with_effective_price(self):
        """Annotate with effective price (sale or regular)."""
        return self.annotate(
            effective_price=models.Case(
                models.When(
                    sale_price__isnull=False,
                    sale_price__gt=0,
                    then=models.F('sale_price')
                ),
                default=models.F('price'),
                output_field=models.DecimalField()
            )
        )


class ProductManager(models.Manager):
    """Custom manager for Product model."""
    
    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db)
    
    def active(self):
        return self.get_queryset().active()
    
    def featured(self):
        return self.get_queryset().featured()
    
    def on_sale(self):
        return self.get_queryset().on_sale()
    
    def new_arrivals(self, days=30):
        return self.get_queryset().new_arrivals(days)
    
    def in_stock(self):
        return self.get_queryset().in_stock()


class Product(UUIDModel):
    """
    Product aggregate root.
    
    Main entity for product catalog with support for:
    - Pricing with sale prices and scheduling
    - Flexible attributes via JSON
    - Multiple images
    - Category and brand association
    - SEO metadata
    - Tags for filtering
    """
    
    objects = ProductManager()
    
    # Basic info
    name = models.CharField(max_length=255, verbose_name='Tên sản phẩm')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Mô tả')
    short_description = models.CharField(max_length=500, blank=True, verbose_name='Mô tả ngắn')
    
    # Pricing (in VND, no decimals)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Giá gốc'
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Giá khuyến mãi'
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Giá vốn'
    )
    
    # Sale scheduling
    sale_start = models.DateTimeField(null=True, blank=True, verbose_name='Bắt đầu KM')
    sale_end = models.DateTimeField(null=True, blank=True, verbose_name='Kết thúc KM')
    
    # Classification
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Danh mục'
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name='Thương hiệu'
    )
    tags = models.ManyToManyField(
        ProductTag,
        blank=True,
        related_name='products',
        verbose_name='Tags'
    )
    
    # Identification
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name='Mã SKU')
    barcode = models.CharField(max_length=50, blank=True, verbose_name='Barcode')
    
    # Flexible attributes for variant data
    attributes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Thuộc tính',
        help_text='Lưu các thuộc tính như màu sắc, kích thước, v.v.'
    )
    specifications = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Thông số kỹ thuật'
    )
    
    # Physical attributes (for shipping)
    weight = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name='Cân nặng (kg)'
    )
    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Dài (cm)')
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Rộng (cm)')
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Cao (cm)')
    
    # SEO
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='Meta title')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='Meta description')
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name='Meta keywords')
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Đang bán')
    is_featured = models.BooleanField(default=False, db_index=True, verbose_name='Nổi bật')
    is_new = models.BooleanField(default=True, verbose_name='Mới')
    is_bestseller = models.BooleanField(default=False, verbose_name='Bán chạy')
    
    # Stats (cached)
    view_count = models.PositiveIntegerField(default=0, verbose_name='Lượt xem')
    sold_count = models.PositiveIntegerField(default=0, verbose_name='Đã bán')
    
    class Meta:
        verbose_name = 'Sản phẩm'
        verbose_name_plural = 'Sản phẩm'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['sku']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
            models.Index(fields=['is_active', '-sold_count']),
            models.Index(fields=['price']),
            models.Index(fields=['sale_price']),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True)
            self.slug = base_slug
            counter = 1
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    # --- Computed Properties ---
    
    @property
    def current_price(self) -> Decimal:
        """Get effective price (sale price if valid, else regular price)."""
        if self.is_sale_active:
            return self.sale_price
        return self.price
    
    @property
    def is_sale_active(self) -> bool:
        """Check if sale is currently active."""
        if not self.sale_price or self.sale_price <= 0 or self.sale_price >= self.price:
            return False
        
        now = timezone.now()
        if self.sale_start and now < self.sale_start:
            return False
        if self.sale_end and now > self.sale_end:
            return False
        
        return True
    
    @property
    def is_on_sale(self) -> bool:
        """Alias for is_sale_active."""
        return self.is_sale_active
    
    @property
    def discount_percentage(self) -> int:
        """Calculate discount percentage."""
        if self.is_sale_active and self.price > 0:
            discount = ((self.price - self.sale_price) / self.price) * 100
            return int(discount)
        return 0
    
    @property
    def discount_amount(self) -> Decimal:
        """Calculate discount amount."""
        if self.is_sale_active:
            return self.price - self.sale_price
        return Decimal('0')
    
    @property
    def profit_margin(self) -> Decimal:
        """Calculate profit margin percentage."""
        if self.cost_price and self.cost_price > 0:
            return ((self.current_price - self.cost_price) / self.current_price) * 100
        return Decimal('0')
    
    @property
    def primary_image(self):
        """Get primary product image."""
        primary = self.images.filter(is_primary=True).first()
        if primary:
            return primary.image
        first = self.images.first()
        return first.image if first else None
    
    @property
    def primary_image_url(self) -> str:
        """Get primary image URL."""
        img = self.primary_image
        return img.url if img else ''
    
    @property
    def average_rating(self) -> float:
        """Calculate average rating from reviews."""
        from django.db.models import Avg
        result = self.reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))
        avg = result.get('avg')
        return round(avg, 1) if avg else 0.0
    
    @property
    def review_count(self) -> int:
        """Count of approved reviews."""
        return self.reviews.filter(is_approved=True).count()
    
    @property
    def in_stock(self) -> bool:
        """Check if product is in stock."""
        if hasattr(self, 'stock'):
            return self.stock.available_quantity > 0
        return False
    
    @property
    def stock_quantity(self) -> int:
        """Get available stock quantity."""
        if hasattr(self, 'stock'):
            return self.stock.available_quantity
        return 0
    
    def increment_view_count(self):
        """Increment view count atomically."""
        Product.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)
    
    def increment_sold_count(self, quantity: int = 1):
        """Increment sold count atomically."""
        Product.objects.filter(pk=self.pk).update(sold_count=models.F('sold_count') + quantity)


class ProductImage(TimeStampedModel):
    """
    Product image entity.
    
    Supports multiple images per product with primary flag
    and optimization metadata.
    """
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Sản phẩm'
    )
    image = models.ImageField(
        upload_to=product_image_path,
        verbose_name='Hình ảnh'
    )
    alt_text = models.CharField(max_length=255, blank=True, verbose_name='Alt text')
    caption = models.CharField(max_length=255, blank=True, verbose_name='Caption')
    is_primary = models.BooleanField(default=False, verbose_name='Ảnh chính')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Thứ tự')
    
    # Image metadata
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text='Size in bytes')
    
    class Meta:
        verbose_name = 'Hình ảnh sản phẩm'
        verbose_name_plural = 'Hình ảnh sản phẩm'
        ordering = ['sort_order', '-is_primary']
    
    def __str__(self) -> str:
        return f"Image for {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
