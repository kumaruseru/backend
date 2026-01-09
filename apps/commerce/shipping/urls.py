"""Commerce Shipping - URL Configuration."""
from django.urls import path
from . import views

app_name = 'shipping'

urlpatterns = [
    # Public
    path('tracking/<str:tracking_code>/', views.ShipmentTrackingView.as_view(), name='tracking'),
    path('calculate-fee/', views.CalculateFeeView.as_view(), name='calculate_fee'),

    # Admin
    path('admin/shipments/', views.AdminShipmentListView.as_view(), name='admin_list'),
    path('admin/shipments/active/', views.AdminActiveShipmentsView.as_view(), name='admin_active'),
    path('admin/shipments/failed/', views.AdminFailedShipmentsView.as_view(), name='admin_failed'),
    path('admin/shipments/pending-cod/', views.AdminPendingCODView.as_view(), name='admin_pending_cod'),
    path('admin/shipments/create/', views.AdminShipmentCreateView.as_view(), name='admin_create'),
    path('admin/shipments/<uuid:shipment_id>/', views.AdminShipmentDetailView.as_view(), name='admin_detail'),
    path('admin/shipments/<uuid:shipment_id>/status/', views.AdminShipmentUpdateStatusView.as_view(), name='admin_update_status'),
    path('admin/shipments/<uuid:shipment_id>/cancel/', views.AdminShipmentCancelView.as_view(), name='admin_cancel'),
    path('admin/shipments/<uuid:shipment_id>/attempt/', views.AdminDeliveryAttemptView.as_view(), name='admin_delivery_attempt'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
]
