"""Commerce Orders - URL Configuration."""
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # User
    path('orders/', views.OrderListView.as_view(), name='list'),
    path('orders/create/', views.OrderCreateView.as_view(), name='create'),
    path('orders/<uuid:order_id>/', views.OrderDetailView.as_view(), name='detail'),
    path('orders/<uuid:order_id>/cancel/', views.OrderCancelView.as_view(), name='cancel'),
    path('orders/<uuid:order_id>/notes/', views.OrderNoteCreateView.as_view(), name='add_note'),
    path('orders/number/<str:order_number>/', views.OrderByNumberView.as_view(), name='by_number'),
    path('tracking/<str:order_number>/', views.OrderTrackingView.as_view(), name='tracking'),

    # Admin
    path('admin/orders/', views.AdminOrderListView.as_view(), name='admin_list'),
    path('admin/orders/<uuid:order_id>/', views.AdminOrderDetailView.as_view(), name='admin_detail'),
    path('admin/orders/<uuid:order_id>/confirm/', views.AdminOrderConfirmView.as_view(), name='admin_confirm'),
    path('admin/orders/<uuid:order_id>/cancel/', views.AdminOrderCancelView.as_view(), name='admin_cancel'),
    path('admin/orders/<uuid:order_id>/ship/', views.AdminOrderShipView.as_view(), name='admin_ship'),
    path('admin/orders/<uuid:order_id>/deliver/', views.AdminOrderDeliverView.as_view(), name='admin_deliver'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
]
