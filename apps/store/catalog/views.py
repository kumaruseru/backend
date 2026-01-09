"""Store Catalog - API Views."""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.common.core.exceptions import DomainException
from .models import Category, Brand, Product, ProductTag
from .serializers import (
    CategorySerializer, CategorySimpleSerializer, CategoryTreeSerializer,
    BrandSerializer, BrandSimpleSerializer,
    ProductTagSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCardSerializer,
    ProductCreateSerializer, ProductUpdateSerializer, ProductBulkUpdateSerializer,
    CatalogFiltersSerializer, ProductSearchSerializer
)
from .services import CatalogService
from .selectors import CatalogSelector
from .filters import ProductFilter


class CategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related('children').order_by('sort_order', 'name')

    @extend_schema(responses={200: CategorySerializer(many=True)}, tags=['Catalog - Categories'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CategoryTreeView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: CategoryTreeSerializer(many=True)}, tags=['Catalog - Categories'])
    def get(self, request):
        categories = CatalogSelector.get_category_tree()
        return Response(CategoryTreeSerializer(categories, many=True).data)


class CategoryDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Category.objects.filter(is_active=True).prefetch_related('children')

    @extend_schema(responses={200: CategorySerializer}, tags=['Catalog - Categories'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CategoryFiltersView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: CatalogFiltersSerializer}, tags=['Catalog - Categories'])
    def get(self, request, slug):
        try:
            category = CatalogSelector.get_category_by_slug(slug)
            filters = CatalogSelector.get_category_filters(category)
            return Response({
                'category': CategorySimpleSerializer(category).data,
                'brands': BrandSimpleSerializer(filters['brands'], many=True).data,
                'price_range': filters['price_range'],
                'tags': ProductTagSerializer(filters['tags'], many=True).data,
                'product_count': filters['product_count']
            })
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class BrandListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BrandSerializer

    def get_queryset(self):
        queryset = Brand.objects.filter(is_active=True).order_by('sort_order', 'name')
        if self.request.query_params.get('featured') == 'true':
            queryset = queryset.filter(is_featured=True)
        return queryset

    @extend_schema(parameters=[OpenApiParameter('featured', bool, description='Featured brands only')], responses={200: BrandSerializer(many=True)}, tags=['Catalog - Brands'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BrandDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BrandSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Brand.objects.filter(is_active=True)

    @extend_schema(responses={200: BrandSerializer}, tags=['Catalog - Brands'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter

    def get_queryset(self):
        return Product.objects.active().select_related('category', 'brand').prefetch_related('images')

    @extend_schema(
        parameters=[
            OpenApiParameter('category', str, description='Category slug'),
            OpenApiParameter('category_id', int, description='Category ID'),
            OpenApiParameter('brand', str, description='Brand slug'),
            OpenApiParameter('brand_id', int, description='Brand ID'),
            OpenApiParameter('min_price', int, description='Minimum price'),
            OpenApiParameter('max_price', int, description='Maximum price'),
            OpenApiParameter('on_sale', bool, description='On sale only'),
            OpenApiParameter('featured', bool, description='Featured only'),
            OpenApiParameter('in_stock', bool, description='In stock only'),
            OpenApiParameter('is_new', bool, description='New arrivals only'),
            OpenApiParameter('q', str, description='Search query'),
            OpenApiParameter('ordering', str, description='Ordering: price, -price, name, -created, popular'),
        ],
        responses={200: ProductListSerializer(many=True)},
        tags=['Catalog - Products']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: ProductDetailSerializer}, tags=['Catalog - Products'])
    def get(self, request, slug):
        try:
            product = CatalogService.get_product_by_slug(slug, increment_view=True)
            return Response(ProductDetailSerializer(product).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class ProductByIdView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: ProductDetailSerializer}, tags=['Catalog - Products'])
    def get(self, request, product_id):
        try:
            product = CatalogSelector.get_product_by_id(product_id)
            return Response(ProductDetailSerializer(product).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class FeaturedProductsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = None

    def get_queryset(self):
        limit = int(self.request.query_params.get('limit', 12))
        return CatalogSelector.get_featured_products(limit)

    @extend_schema(parameters=[OpenApiParameter('limit', int)], responses={200: ProductListSerializer(many=True)}, tags=['Catalog - Products'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class NewArrivalsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = None

    def get_queryset(self):
        limit = int(self.request.query_params.get('limit', 12))
        days = int(self.request.query_params.get('days', 30))
        return CatalogSelector.get_new_arrivals(limit, days)

    @extend_schema(parameters=[OpenApiParameter('limit', int), OpenApiParameter('days', int)], responses={200: ProductListSerializer(many=True)}, tags=['Catalog - Products'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BestsellersView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = None

    def get_queryset(self):
        limit = int(self.request.query_params.get('limit', 12))
        return CatalogSelector.get_bestsellers(limit)

    @extend_schema(parameters=[OpenApiParameter('limit', int)], responses={200: ProductListSerializer(many=True)}, tags=['Catalog - Products'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OnSaleProductsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = None

    def get_queryset(self):
        limit = int(self.request.query_params.get('limit', 12))
        return CatalogSelector.get_on_sale_products(limit)

    @extend_schema(parameters=[OpenApiParameter('limit', int)], responses={200: ProductListSerializer(many=True)}, tags=['Catalog - Products'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RelatedProductsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = None

    def get_queryset(self):
        slug = self.kwargs.get('slug')
        limit = int(self.request.query_params.get('limit', 8))
        try:
            product = Product.objects.get(slug=slug)
            return CatalogSelector.get_related_products(product, limit)
        except Product.DoesNotExist:
            return Product.objects.none()

    @extend_schema(parameters=[OpenApiParameter('limit', int)], responses={200: ProductListSerializer(many=True)}, tags=['Catalog - Products'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SearchView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter('q', str, required=True),
            OpenApiParameter('category_id', int),
            OpenApiParameter('brand_id', int),
            OpenApiParameter('min_price', int),
            OpenApiParameter('max_price', int),
            OpenApiParameter('in_stock', bool),
            OpenApiParameter('on_sale', bool),
            OpenApiParameter('ordering', str),
            OpenApiParameter('limit', int),
        ],
        responses={200: ProductListSerializer(many=True)},
        tags=['Catalog - Search']
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        limit = int(request.query_params.get('limit', 50))
        products = Product.objects.active().search(query).select_related('category', 'brand').prefetch_related('images')[:limit]
        return Response({
            'products': ProductListSerializer(products, many=True).data,
            'total': products.count()
        })


class SearchSuggestionsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(parameters=[OpenApiParameter('q', str, required=True)], responses={200: ProductSearchSerializer}, tags=['Catalog - Search'])
    def get(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response({'products': [], 'categories': [], 'brands': []})
        result = CatalogSelector.search_suggestions(query)
        return Response(result)


class AdminProductListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter

    def get_queryset(self):
        return Product.objects.all().select_related('category', 'brand')

    @extend_schema(tags=['Catalog - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminProductDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: ProductDetailSerializer}, tags=['Catalog - Admin'])
    def get(self, request, product_id):
        try:
            product = Product.objects.select_related('category', 'brand').get(id=product_id)
            return Response(ProductDetailSerializer(product).data)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(request=ProductUpdateSerializer, responses={200: ProductDetailSerializer}, tags=['Catalog - Admin'])
    def patch(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
            serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            updated = CatalogService.update_product(product, serializer.validated_data)
            return Response(ProductDetailSerializer(updated).data)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(responses={204: None}, tags=['Catalog - Admin'])
    def delete(self, request, product_id):
        Product.objects.filter(id=product_id).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminProductCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ProductCreateSerializer, responses={201: ProductDetailSerializer}, tags=['Catalog - Admin'])
    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = CatalogService.create_product(serializer.validated_data)
        return Response(ProductDetailSerializer(product).data, status=status.HTTP_201_CREATED)


class AdminBulkUpdateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ProductBulkUpdateSerializer, responses={200: OpenApiResponse(description='Number of updated products')}, tags=['Catalog - Admin'])
    def post(self, request):
        serializer = ProductBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        product_ids = data.pop('product_ids')
        updates = {k: v for k, v in data.items() if v is not None}
        count = CatalogService.bulk_update_products(product_ids, updates)
        return Response({'updated': count})


class AdminStatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(tags=['Catalog - Admin'])
    def get(self, request):
        stats = CatalogService.get_catalog_statistics()
        return Response(stats)
