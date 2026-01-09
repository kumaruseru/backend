"""Store Catalog - Product Filters."""
from django.db import models
from django_filters import rest_framework as filters
from .models import Product, Category, Brand


class ProductFilter(filters.FilterSet):
    category = filters.CharFilter(method='filter_category')
    category_id = filters.NumberFilter(method='filter_category_id')
    brand = filters.CharFilter(method='filter_brand')
    brand_id = filters.NumberFilter(field_name='brand_id')
    tags = filters.CharFilter(method='filter_tags')
    min_price = filters.NumberFilter(method='filter_min_price')
    max_price = filters.NumberFilter(method='filter_max_price')
    on_sale = filters.BooleanFilter(method='filter_on_sale')
    featured = filters.BooleanFilter(field_name='is_featured')
    is_new = filters.BooleanFilter(field_name='is_new')
    bestseller = filters.BooleanFilter(field_name='is_bestseller')
    in_stock = filters.BooleanFilter(method='filter_in_stock')
    search = filters.CharFilter(method='filter_search')
    q = filters.CharFilter(method='filter_search')

    ordering = filters.OrderingFilter(
        fields=(
            ('price', 'price'),
            ('sale_price', 'sale_price'),
            ('created_at', 'created'),
            ('name', 'name'),
            ('sold_count', 'popular'),
            ('view_count', 'views'),
        ),
        field_labels={
            'price': 'Price Low to High',
            '-price': 'Price High to Low',
            'created': 'Newest',
            '-created': 'Oldest',
            'name': 'Name A-Z',
            '-name': 'Name Z-A',
            '-popular': 'Bestselling',
        }
    )

    class Meta:
        model = Product
        fields = ['category', 'brand', 'is_featured', 'is_new']

    def filter_category(self, queryset, name, value):
        try:
            category = Category.objects.get(slug=value, is_active=True)
            category_ids = category.get_all_children_ids()
            return queryset.filter(category_id__in=category_ids)
        except Category.DoesNotExist:
            return queryset.none()

    def filter_category_id(self, queryset, name, value):
        try:
            category = Category.objects.get(id=value, is_active=True)
            category_ids = category.get_all_children_ids()
            return queryset.filter(category_id__in=category_ids)
        except Category.DoesNotExist:
            return queryset.none()

    def filter_brand(self, queryset, name, value):
        try:
            brand = Brand.objects.get(slug=value, is_active=True)
            return queryset.filter(brand=brand)
        except Brand.DoesNotExist:
            return queryset.none()

    def filter_tags(self, queryset, name, value):
        tag_slugs = [t.strip() for t in value.split(',')]
        return queryset.filter(tags__slug__in=tag_slugs).distinct()

    def filter_min_price(self, queryset, name, value):
        return queryset.filter(
            models.Q(sale_price__gte=value, sale_price__gt=0) |
            models.Q(sale_price__isnull=True, price__gte=value) |
            models.Q(sale_price=0, price__gte=value)
        )

    def filter_max_price(self, queryset, name, value):
        return queryset.filter(
            models.Q(sale_price__lte=value, sale_price__gt=0) |
            models.Q(sale_price__isnull=True, price__lte=value) |
            models.Q(sale_price=0, price__lte=value)
        )

    def filter_on_sale(self, queryset, name, value):
        if value:
            return queryset.filter(sale_price__isnull=False, sale_price__gt=0).exclude(sale_price__gte=models.F('price'))
        return queryset

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        elif value is False:
            return queryset.filter(models.Q(stock__isnull=True) | models.Q(stock__quantity__lte=0))
        return queryset

    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(description__icontains=value) |
                models.Q(short_description__icontains=value) |
                models.Q(brand__name__icontains=value) |
                models.Q(sku__icontains=value) |
                models.Q(tags__name__icontains=value)
            ).distinct()
        return queryset


class CategoryFilter(filters.FilterSet):
    parent = filters.NumberFilter(field_name='parent_id')
    root = filters.BooleanFilter(method='filter_root')
    featured = filters.BooleanFilter(field_name='is_featured')

    class Meta:
        model = Category
        fields = ['parent', 'is_active', 'is_featured']

    def filter_root(self, queryset, name, value):
        if value:
            return queryset.filter(parent__isnull=True)
        return queryset


class BrandFilter(filters.FilterSet):
    featured = filters.BooleanFilter(field_name='is_featured')
    has_products = filters.BooleanFilter(method='filter_has_products')

    class Meta:
        model = Brand
        fields = ['is_active', 'is_featured']

    def filter_has_products(self, queryset, name, value):
        if value:
            return queryset.filter(products__is_active=True).distinct()
        return queryset
