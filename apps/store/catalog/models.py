"""Store Catalog - Product Catalog Models."""
import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.common.core.models import TimeStampedModel, UUIDModel
from apps.common.core.storage import category_image_path, brand_logo_path, product_image_path
from apps.common.utils.string import generate_unique_slug


class Category(TimeStampedModel):
    name = models.CharField(max_length=100, verbose_name='Name')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Description')
    image = models.ImageField(upload_to=category_image_path, blank=True, null=True, verbose_name='Image')
    icon = models.CharField(max_length=50, blank=True, verbose_name='Icon Class')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='Parent Category')
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='Meta Title')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='Meta Description')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Active')
    is_featured = models.BooleanField(default=False, verbose_name='Featured')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')
    _cached_product_count = models.PositiveIntegerField(default=0, verbose_name='Cached Product Count')

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
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
            self.slug = generate_unique_slug(Category, self, 'name')
        super().save(*args, **kwargs)

    @property
    def product_count(self) -> int:
        return self.products.filter(is_active=True).count()

    @property
    def total_product_count(self) -> int:
        count = self.product_count
        for child in self.children.filter(is_active=True):
            count += child.total_product_count
        return count

    @property
    def full_path(self) -> str:
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

    @property
    def level(self) -> int:
        if self.parent:
            return self.parent.level + 1
        return 0

    @property
    def ancestors(self) -> list:
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def get_all_children_ids(self) -> list:
        ids = [self.id]
        for child in self.children.all():
            ids.extend(child.get_all_children_ids())
        return ids


class Brand(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='Name')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Slug')
    logo = models.ImageField(upload_to=brand_logo_path, blank=True, null=True, verbose_name='Logo')
    description = models.TextField(blank=True, verbose_name='Description')
    website = models.URLField(blank=True, verbose_name='Website')
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Active')
    is_featured = models.BooleanField(default=False, verbose_name='Featured')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')

    class Meta:
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        ordering = ['sort_order', 'name']

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(Brand, self, 'name')
        super().save(*args, **kwargs)

    @property
    def product_count(self) -> int:
        return self.products.filter(is_active=True).count()


class ProductTag(TimeStampedModel):
    name = models.CharField(max_length=50, unique=True, verbose_name='Name')
    slug = models.SlugField(max_length=50, unique=True, verbose_name='Slug')

    class Meta:
        verbose_name = 'Product Tag'
        verbose_name_plural = 'Product Tags'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(ProductTag, self, 'name')
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def featured(self):
        return self.filter(is_featured=True, is_active=True)

    def new_arrivals(self, days=30):
        since = timezone.now() - timezone.timedelta(days=days)
        return self.filter(is_active=True, created_at__gte=since)

    def on_sale(self):
        return self.filter(is_active=True, sale_price__isnull=False, sale_price__gt=0).exclude(sale_price__gte=models.F('price'))

    def in_stock(self):
        return self.filter(stock__quantity__gt=0)

    def in_category(self, category):
        if hasattr(category, 'get_all_children_ids'):
            return self.filter(category_id__in=category.get_all_children_ids())
        return self.filter(category=category)

    def in_price_range(self, min_price=None, max_price=None):
        qs = self
        if min_price is not None:
            qs = qs.filter(models.Q(sale_price__gte=min_price) | models.Q(sale_price__isnull=True, price__gte=min_price))
        if max_price is not None:
            qs = qs.filter(models.Q(sale_price__lte=max_price, sale_price__gt=0) | models.Q(sale_price__isnull=True, price__lte=max_price))
        return qs

    def search(self, query):
        return self.filter(models.Q(name__icontains=query) | models.Q(description__icontains=query) | models.Q(sku__icontains=query) | models.Q(brand__name__icontains=query))

    def with_effective_price(self):
        return self.annotate(effective_price=models.Case(
            models.When(sale_price__isnull=False, sale_price__gt=0, then=models.F('sale_price')),
            default=models.F('price'),
            output_field=models.DecimalField()
        ))


class ProductManager(models.Manager):
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
    objects = ProductManager()

    name = models.CharField(max_length=255, verbose_name='Name')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Description')
    short_description = models.CharField(max_length=500, blank=True, verbose_name='Short Description')

    price = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(Decimal('0'))], verbose_name='Price')
    sale_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(Decimal('0'))], verbose_name='Sale Price')
    cost_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(Decimal('0'))], verbose_name='Cost Price')

    sale_start = models.DateTimeField(null=True, blank=True, verbose_name='Sale Start')
    sale_end = models.DateTimeField(null=True, blank=True, verbose_name='Sale End')

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products', verbose_name='Category')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name='Brand')
    tags = models.ManyToManyField(ProductTag, blank=True, related_name='products', verbose_name='Tags')

    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name='SKU')
    barcode = models.CharField(max_length=50, blank=True, verbose_name='Barcode')

    attributes = models.JSONField(default=dict, blank=True, verbose_name='Attributes', help_text='Store attributes like color, size, etc.')
    specifications = models.JSONField(default=dict, blank=True, verbose_name='Specifications')

    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Weight (kg)')
    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Length (cm)')
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Width (cm)')
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Height (cm)')

    meta_title = models.CharField(max_length=70, blank=True, verbose_name='Meta Title')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='Meta Description')
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name='Meta Keywords')

    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Active')
    is_featured = models.BooleanField(default=False, db_index=True, verbose_name='Featured')
    is_new = models.BooleanField(default=True, verbose_name='New')
    is_bestseller = models.BooleanField(default=False, verbose_name='Bestseller')

    view_count = models.PositiveIntegerField(default=0, verbose_name='View Count')
    sold_count = models.PositiveIntegerField(default=0, verbose_name='Sold Count')

    effective_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, db_index=True, editable=False, verbose_name='Effective Price')

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
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
            models.Index(fields=['effective_price']),
            models.Index(fields=['is_active', 'effective_price']),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(Product, self, 'name')
        self._update_effective_price()
        super().save(*args, **kwargs)

    def _update_effective_price(self):
        if self._is_sale_currently_active():
            self.effective_price = self.sale_price
        else:
            self.effective_price = self.price

    def _is_sale_currently_active(self) -> bool:
        if not self.sale_price or self.sale_price <= 0:
            return False
        if self.price and self.sale_price >= self.price:
            return False
        now = timezone.now()
        if self.sale_start and now < self.sale_start:
            return False
        if self.sale_end and now > self.sale_end:
            return False
        return True

    @property
    def current_price(self) -> Decimal:
        if self.is_sale_active:
            return self.sale_price
        return self.price

    @property
    def is_sale_active(self) -> bool:
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
        return self.is_sale_active

    @property
    def discount_percentage(self) -> int:
        if self.is_sale_active and self.price > 0:
            discount = ((self.price - self.sale_price) / self.price) * 100
            return int(discount)
        return 0

    @property
    def discount_amount(self) -> Decimal:
        if self.is_sale_active:
            return self.price - self.sale_price
        return Decimal('0')

    @property
    def profit_margin(self) -> Decimal:
        if self.cost_price and self.cost_price > 0:
            return ((self.current_price - self.cost_price) / self.current_price) * 100
        return Decimal('0')

    @property
    def primary_image(self):
        primary = self.images.filter(is_primary=True).first()
        if primary:
            return primary.image
        first = self.images.first()
        return first.image if first else None

    @property
    def primary_image_url(self) -> str:
        img = self.primary_image
        return img.url if img else ''

    @property
    def average_rating(self) -> float:
        from django.db.models import Avg
        result = self.reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))
        avg = result.get('avg')
        return round(avg, 1) if avg else 0.0

    @property
    def review_count(self) -> int:
        return self.reviews.filter(is_approved=True).count()

    @property
    def in_stock(self) -> bool:
        if hasattr(self, 'stock'):
            return self.stock.available_quantity > 0
        return False

    @property
    def stock_quantity(self) -> int:
        if hasattr(self, 'stock'):
            return self.stock.available_quantity
        return 0


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name='Product')
    image = models.ImageField(upload_to=product_image_path, verbose_name='Image')
    alt_text = models.CharField(max_length=255, blank=True, verbose_name='Alt Text')
    caption = models.CharField(max_length=255, blank=True, verbose_name='Caption')
    is_primary = models.BooleanField(default=False, verbose_name='Primary')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text='Size in bytes')

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['sort_order', '-is_primary']

    def __str__(self) -> str:
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductStat(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stats', primary_key=True, verbose_name='Product')
    view_count = models.PositiveIntegerField(default=0, verbose_name='View Count')
    sold_count = models.PositiveIntegerField(default=0, verbose_name='Sold Count')
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'), verbose_name='Avg Rating')
    rating_count = models.PositiveIntegerField(default=0, verbose_name='Rating Count')

    class Meta:
        verbose_name = 'Product Stat'
        verbose_name_plural = 'Product Stats'

    def __str__(self) -> str:
        return f"Stats for {self.product_id}"
