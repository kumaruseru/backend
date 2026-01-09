"""Store Catalog - Serializers."""
from decimal import Decimal
from rest_framework import serializers
from .models import Category, Brand, ProductTag, Product, ProductImage


class BrandSerializer(serializers.ModelSerializer):
    product_count = serializers.ReadOnlyField()

    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug', 'logo', 'description', 'website', 'is_featured', 'product_count']


class BrandSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug', 'logo']


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.ReadOnlyField()
    total_product_count = serializers.ReadOnlyField()
    children = serializers.SerializerMethodField()
    breadcrumb = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'icon', 'parent', 'is_active', 'is_featured', 'sort_order', 'product_count', 'total_product_count', 'level', 'children', 'breadcrumb', 'meta_title', 'meta_description']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('sort_order')
        if children.exists():
            return CategorySimpleSerializer(children, many=True).data
        return []

    def get_breadcrumb(self, obj):
        ancestors = obj.ancestors
        ancestors.append(obj)
        return [{'id': c.id, 'name': c.name, 'slug': c.slug} for c in ancestors]


class CategorySimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'level']


class CategoryTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    product_count = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'icon', 'product_count', 'children']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('sort_order')
        return CategoryTreeSerializer(children, many=True).data


class ProductTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductTag
        fields = ['id', 'name', 'slug']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'caption', 'is_primary', 'sort_order']


class ProductImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['product', 'image', 'alt_text', 'is_primary', 'sort_order']


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySimpleSerializer(read_only=True)
    brand = BrandSimpleSerializer(read_only=True)
    current_price = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    primary_image_url = serializers.ReadOnlyField()
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    stock_quantity = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'price', 'sale_price', 'current_price', 'is_on_sale', 'discount_percentage', 'category', 'brand', 'primary_image_url', 'average_rating', 'review_count', 'is_featured', 'is_new', 'is_bestseller', 'in_stock', 'stock_quantity', 'sold_count']


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    tags = ProductTagSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    current_price = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    discount_amount = serializers.ReadOnlyField()
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    stock_quantity = serializers.ReadOnlyField()
    stock_status = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'short_description', 'price', 'sale_price', 'current_price', 'is_on_sale', 'discount_percentage', 'discount_amount', 'sale_start', 'sale_end', 'category', 'brand', 'tags', 'sku', 'barcode', 'attributes', 'specifications', 'weight', 'length', 'width', 'height', 'images', 'average_rating', 'review_count', 'is_featured', 'is_new', 'is_bestseller', 'in_stock', 'stock_quantity', 'stock_status', 'view_count', 'sold_count', 'meta_title', 'meta_description', 'meta_keywords', 'related_products', 'created_at', 'updated_at']

    def get_stock_status(self, obj) -> dict:
        if hasattr(obj, 'stock'):
            return {'in_stock': obj.stock.available_quantity > 0, 'quantity': obj.stock.available_quantity, 'low_stock': getattr(obj.stock, 'is_low_stock', False), 'reserved': getattr(obj.stock, 'reserved_quantity', 0)}
        return {'in_stock': False, 'quantity': 0, 'low_stock': False, 'reserved': 0}

    def get_related_products(self, obj) -> list:
        related = Product.objects.active().filter(category=obj.category).exclude(id=obj.id).select_related('category', 'brand').prefetch_related('images')[:6]
        return ProductListSerializer(related, many=True).data


class ProductCardSerializer(serializers.ModelSerializer):
    primary_image_url = serializers.ReadOnlyField()
    current_price = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'primary_image_url', 'current_price', 'in_stock']


class ProductCreateSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(queryset=ProductTag.objects.all(), many=True, required=False)

    class Meta:
        model = Product
        fields = ['name', 'description', 'short_description', 'price', 'sale_price', 'cost_price', 'sale_start', 'sale_end', 'category', 'brand', 'tags', 'sku', 'barcode', 'attributes', 'specifications', 'weight', 'length', 'width', 'height', 'meta_title', 'meta_description', 'meta_keywords', 'is_active', 'is_featured', 'is_new', 'is_bestseller']

    def validate_sale_price(self, value):
        if value is not None and 'price' in self.initial_data:
            price = Decimal(self.initial_data['price'])
            if value >= price:
                raise serializers.ValidationError('Sale price must be less than regular price')
        return value

    def validate_sku(self, value):
        if value:
            exists = Product.objects.filter(sku=value)
            if self.instance:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise serializers.ValidationError('SKU already exists')
        return value


class ProductUpdateSerializer(ProductCreateSerializer):
    class Meta(ProductCreateSerializer.Meta):
        extra_kwargs = {field: {'required': False} for field in ProductCreateSerializer.Meta.fields}


class ProductBulkUpdateSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    is_active = serializers.BooleanField(required=False)
    is_featured = serializers.BooleanField(required=False)
    category_id = serializers.IntegerField(required=False)
    sale_price = serializers.DecimalField(max_digits=12, decimal_places=0, required=False)


class ProductSearchSerializer(serializers.Serializer):
    products = ProductListSerializer(many=True)
    categories = CategorySimpleSerializer(many=True)
    brands = BrandSimpleSerializer(many=True)
    total_results = serializers.IntegerField()


class CatalogFiltersSerializer(serializers.Serializer):
    categories = CategorySimpleSerializer(many=True)
    brands = BrandSimpleSerializer(many=True)
    price_range = serializers.DictField()
    tags = ProductTagSerializer(many=True)
