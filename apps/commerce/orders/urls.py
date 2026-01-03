"""Commerce Orders - URL Configuration (Production-Ready)."""
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # ===== User Endpoints =====
    
    # List orders
    path('', views.OrderListView.as_view(), name='list'),
    
    # Create orders
    path('from-cart/', views.OrderFromCartView.as_view(), name='from_cart'),
    path('from-items/', views.OrderFromItemsView.as_view(), name='from_items'),
    
    # Order detail
    path('<uuid:order_id>/', views.OrderDetailView.as_view(), name='detail'),
    path('<uuid:order_id>/cancel/', views.OrderCancelView.as_view(), name='cancel'),
    path('<uuid:order_id>/reorder/', views.OrderReorderView.as_view(), name='reorder'),
    
    # By order number
    path('number/<str:order_number>/', views.OrderByNumberView.as_view(), name='by_number'),
    
    # Public tracking
    path('track/<str:order_number>/', views.OrderTrackView.as_view(), name='track'),
    
    # User statistics
    path('my/statistics/', views.UserOrderStatisticsView.as_view(), name='user_stats'),
    
    # ===== Admin Endpoints =====
    
    path('admin/', views.AdminOrderListView.as_view(), name='admin_list'),
    path('admin/statistics/', views.AdminOrderStatisticsView.as_view(), name='admin_stats'),
    
    path('admin/<uuid:order_id>/', views.AdminOrderDetailView.as_view(), name='admin_detail'),
    path('admin/<uuid:order_id>/confirm/', views.AdminOrderConfirmView.as_view(), name='admin_confirm'),
    path('admin/<uuid:order_id>/process/', views.AdminOrderProcessView.as_view(), name='admin_process'),
    path('admin/<uuid:order_id>/ship/', views.AdminOrderShipView.as_view(), name='admin_ship'),
    path('admin/<uuid:order_id>/deliver/', views.AdminOrderDeliverView.as_view(), name='admin_deliver'),
    path('admin/<uuid:order_id>/cancel/', views.AdminOrderCancelView.as_view(), name='admin_cancel'),
    path('admin/<uuid:order_id>/notes/', views.AdminOrderNoteView.as_view(), name='admin_notes'),
]
