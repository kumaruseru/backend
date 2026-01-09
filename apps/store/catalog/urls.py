"""Store Catalog - URL Configuration."""
from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/tree/', views.CategoryTreeView.as_view(), name='category_tree'),
    path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('categories/<slug:slug>/filters/', views.CategoryFiltersView.as_view(), name='category_filters'),

    # Brands
    path('brands/', views.BrandListView.as_view(), name='brand_list'),
    path('brands/<slug:slug>/', views.BrandDetailView.as_view(), name='brand_detail'),

    # Products
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/featured/', views.FeaturedProductsView.as_view(), name='featured'),
    path('products/new/', views.NewArrivalsView.as_view(), name='new_arrivals'),
    path('products/bestsellers/', views.BestsellersView.as_view(), name='bestsellers'),
    path('products/on-sale/', views.OnSaleProductsView.as_view(), name='on_sale'),
    path('products/id/<uuid:product_id>/', views.ProductByIdView.as_view(), name='product_by_id'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<slug:slug>/related/', views.RelatedProductsView.as_view(), name='related'),

    # Search
    path('search/', views.SearchView.as_view(), name='search'),
    path('search/suggestions/', views.SearchSuggestionsView.as_view(), name='suggestions'),

    # Admin
    path('admin/products/', views.AdminProductListView.as_view(), name='admin_list'),
    path('admin/products/create/', views.AdminProductCreateView.as_view(), name='admin_create'),
    path('admin/products/bulk-update/', views.AdminBulkUpdateView.as_view(), name='admin_bulk'),
    path('admin/products/<uuid:product_id>/', views.AdminProductDetailView.as_view(), name='admin_detail'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
]
