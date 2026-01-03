"""Commerce Shipping - URL Configuration (Production-Ready)."""
from django.urls import path
from . import views

app_name = 'shipping'

urlpatterns = [
    # ===== Public - Location APIs =====
    path('provinces/', views.ProvincesView.as_view(), name='provinces'),
    path('districts/<int:province_id>/', views.DistrictsView.as_view(), name='districts'),
    path('wards/<int:district_id>/', views.WardsView.as_view(), name='wards'),
    
    # ===== Public - Fee Calculation =====
    path('calculate/', views.CalculateFeeView.as_view(), name='calculate_fee'),
    
    # ===== Public - Tracking =====
    path('track/<str:tracking_code>/', views.TrackingView.as_view(), name='track'),
    
    # ===== User Endpoints =====
    path('my/', views.UserShipmentListView.as_view(), name='user_list'),
    path('my/<uuid:shipment_id>/', views.UserShipmentDetailView.as_view(), name='user_detail'),
    
    # ===== Admin Endpoints =====
    path('admin/', views.AdminShipmentListView.as_view(), name='admin_list'),
    path('admin/statistics/', views.AdminShippingStatisticsView.as_view(), name='admin_stats'),
    path('admin/create/', views.AdminCreateShipmentView.as_view(), name='admin_create'),
    path('admin/<uuid:shipment_id>/', views.AdminShipmentDetailView.as_view(), name='admin_detail'),
    path('admin/<uuid:shipment_id>/cancel/', views.AdminCancelShipmentView.as_view(), name='admin_cancel'),
    path('admin/<uuid:shipment_id>/sync/', views.AdminSyncTrackingView.as_view(), name='admin_sync'),
    
    # ===== Webhooks =====
    path('webhook/ghn/', views.GHNWebhookView.as_view(), name='webhook_ghn'),
    path('webhook/ghtk/', views.GHTKWebhookView.as_view(), name='webhook_ghtk'),
    path('webhook/vtp/', views.VTPWebhookView.as_view(), name='webhook_vtp'),
]
