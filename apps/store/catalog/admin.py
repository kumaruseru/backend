"""
Store Catalog - Production-Ready Admin Configuration.

Comprehensive admin interface with:
- Inline images
- Bulk actions
- Status badges
- Export
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Category, Brand, ProductTag, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    """Inline for product images."""
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'sort_order']
    readonly_fields = []


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for categories."""
    
    list_display = [
        'name', 'parent', 'slug', 'product_count_display',
        'is_active_badge', 'is_featured', 'sort_order'
    ]
    list_filter = ['is_active', 'is_featured', 'parent']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['sort_order', 'is_featured']
    ordering = ['sort_order', 'name']
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('name', 'slug', 'description', 'image', 'icon', 'parent')
        }),
        ('Trạng thái', {
            'fields': ('is_active', 'is_featured', 'sort_order')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Số SP')
    def product_count_display(self, obj):
        return obj.product_count
    
    @admin.display(description='Hoạt động')
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin for brands."""
    
    list_display = ['name', 'slug', 'logo_preview', 'product_count', 'is_active', 'is_featured']
    list_filter = ['is_active', 'is_featured']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_featured']
    
    @admin.display(description='Logo')
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="height: 30px; width: auto;"/>',
                obj.logo.url
            )
        return '-'


@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    """Admin for product tags."""
    
    list_display = ['name', 'slug', 'product_count']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            prod_count=Count('products')
        )
    
    @admin.display(description='Số SP')
    def product_count(self, obj):
        return obj.prod_count


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for products."""
    
    list_display = [
        'name', 'sku', 'category', 'brand_name',
        'price_display', 'sale_badge', 'stock_badge',
        'is_active_badge', 'is_featured', 'sold_count'
    ]
    list_filter = [
        'is_active', 'is_featured', 'is_new', 'is_bestseller',
        'category', 'brand', 'created_at'
    ]
    search_fields = ['name', 'slug', 'sku', 'description']
    raw_id_fields = ['category', 'brand']
    filter_horizontal = ['tags']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['view_count', 'sold_count', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    inlines = [ProductImageInline]
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': (
                'name', 'slug', 'short_description', 'description',
                'category', 'brand', 'tags'
            )
        }),
        ('Giá', {
            'fields': (
                'price', 'sale_price', 'cost_price',
                'sale_start', 'sale_end'
            )
        }),
        ('Mã sản phẩm', {
            'fields': ('sku', 'barcode')
        }),
        ('Thuộc tính', {
            'fields': ('attributes', 'specifications'),
            'classes': ('collapse',)
        }),
        ('Kích thước & Cân nặng', {
            'fields': ('weight', 'length', 'width', 'height'),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Trạng thái', {
            'fields': ('is_active', 'is_featured', 'is_new', 'is_bestseller')
        }),
        ('Thống kê', {
            'fields': ('view_count', 'sold_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate', 'deactivate', 'mark_featured', 'export_csv']
    
    # Custom displays
    
    @admin.display(description='Thương hiệu')
    def brand_name(self, obj):
        return obj.brand.name if obj.brand else '-'
    
    @admin.display(description='Giá')
    def price_display(self, obj):
        if obj.is_on_sale:
            return format_html(
                '<del style="color: #999;">{:,.0f}</del> '
                '<span style="color: red;">{:,.0f}₫</span>',
                obj.price, obj.sale_price
            )
        return f"{obj.price:,.0f}₫"
    
    @admin.display(description='Sale')
    def sale_badge(self, obj):
        if obj.is_on_sale:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px;">-{}%</span>',
                obj.discount_percentage
            )
        return '-'
    
    @admin.display(description='Kho')
    def stock_badge(self, obj):
        if hasattr(obj, 'stock'):
            qty = obj.stock.available_quantity
            if qty <= 0:
                return format_html(
                    '<span style="background: #dc3545; color: white; padding: 2px 6px; '
                    'border-radius: 3px; font-size: 11px;">Hết hàng</span>'
                )
            elif qty <= 10:
                return format_html(
                    '<span style="background: #ffc107; color: black; padding: 2px 6px; '
                    'border-radius: 3px; font-size: 11px;">{}</span>',
                    qty
                )
            return format_html(
                '<span style="color: green;">{}</span>',
                qty
            )
        return '-'
    
    @admin.display(description='Trạng thái')
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px;">Đang bán</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">Ẩn</span>'
        )
    
    # Actions
    
    @admin.action(description='Kích hoạt sản phẩm đã chọn')
    def activate(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'Đã kích hoạt {count} sản phẩm.')
    
    @admin.action(description='Ẩn sản phẩm đã chọn')
    def deactivate(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Đã ẩn {count} sản phẩm.')
    
    @admin.action(description='Đánh dấu nổi bật')
    def mark_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'Đã đánh dấu {count} sản phẩm nổi bật.')
    
    @admin.action(description='Export CSV')
    def export_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products.csv"'
        response.write('\ufeff')  # BOM for Excel
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'SKU', 'Tên', 'Danh mục', 'Thương hiệu',
            'Giá', 'Giá KM', 'Trạng thái', 'Đã bán'
        ])
        
        for obj in queryset:
            writer.writerow([
                str(obj.id)[:8],
                obj.sku or '',
                obj.name,
                obj.category.name,
                obj.brand.name if obj.brand else '',
                obj.price,
                obj.sale_price or '',
                'Đang bán' if obj.is_active else 'Ẩn',
                obj.sold_count
            ])
        
        return response


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Admin for product images."""
    
    list_display = ['product', 'image_preview', 'is_primary', 'sort_order']
    list_filter = ['is_primary']
    search_fields = ['product__name', 'alt_text']
    raw_id_fields = ['product']
    
    @admin.display(description='Preview')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height: 50px; width: auto;"/>',
                obj.image.url
            )
        return '-'
