"""Store Marketing - URL Configuration (Production-Ready)."""
from django.urls import path
from . import views

app_name = 'marketing'

urlpatterns = [
    # ===== Coupons =====
    path('coupons/', views.CouponListView.as_view(), name='coupon_list'),
    path('coupons/validate/', views.CouponValidateView.as_view(), name='coupon_validate'),
    path('coupons/<str:code>/', views.CouponDetailView.as_view(), name='coupon_detail'),
    path('coupons/my/history/', views.MyCouponHistoryView.as_view(), name='coupon_history'),
    
    # ===== Banners =====
    path('banners/', views.BannerListView.as_view(), name='banner_list'),
    path('banners/<int:banner_id>/click/', views.BannerClickView.as_view(), name='banner_click'),
    
    # ===== Flash Sales =====
    path('flash-sales/current/', views.FlashSaleCurrentView.as_view(), name='flash_current'),
    path('flash-sales/upcoming/', views.FlashSaleUpcomingView.as_view(), name='flash_upcoming'),
    path('flash-sales/<uuid:sale_id>/', views.FlashSaleDetailView.as_view(), name='flash_detail'),
    path('flash-sales/product/<uuid:product_id>/', views.ProductFlashPriceView.as_view(), name='flash_product'),
    
    # ===== Admin =====
    path('admin/coupons/', views.AdminCouponListView.as_view(), name='admin_coupons'),
    path('admin/coupons/<int:pk>/', views.AdminCouponDetailView.as_view(), name='admin_coupon_detail'),
    path('admin/banners/', views.AdminBannerListView.as_view(), name='admin_banners'),
    path('admin/flash-sales/', views.AdminFlashSaleListView.as_view(), name='admin_flash_sales'),
    path('admin/campaigns/', views.AdminCampaignListView.as_view(), name='admin_campaigns'),
    path('admin/campaigns/<uuid:pk>/', views.AdminCampaignDetailView.as_view(), name='admin_campaign_detail'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_statistics'),
]
