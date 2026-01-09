"""Store Marketing - URL Configuration."""
from django.urls import path
from . import views

app_name = 'marketing'

urlpatterns = [
    # Coupons
    path('coupons/', views.PublicCouponsView.as_view(), name='public_coupons'),
    path('coupons/my/', views.UserCouponsView.as_view(), name='user_coupons'),
    path('coupons/validate/', views.ValidateCouponView.as_view(), name='validate_coupon'),

    # Banners
    path('banners/', views.BannersView.as_view(), name='banners'),
    path('banners/<int:banner_id>/click/', views.BannerClickView.as_view(), name='banner_click'),

    # Flash Sales
    path('flash-sales/', views.FlashSalesView.as_view(), name='flash_sales'),
    path('flash-sales/upcoming/', views.UpcomingFlashSalesView.as_view(), name='upcoming_flash_sales'),
    path('flash-sales/<uuid:flash_sale_id>/', views.FlashSaleDetailView.as_view(), name='flash_sale_detail'),
    path('flash-price/', views.CheckFlashPriceView.as_view(), name='check_flash_price'),

    # Admin
    path('admin/campaigns/', views.AdminCampaignsView.as_view(), name='admin_campaigns'),
    path('admin/campaigns/<uuid:campaign_id>/', views.AdminCampaignDetailView.as_view(), name='admin_campaign_detail'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
]
