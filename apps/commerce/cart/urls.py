"""Commerce Cart - URL Configuration."""
from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.CartView.as_view(), name='cart'),
    path('summary/', views.CartSummaryView.as_view(), name='summary'),
    path('items/', views.AddItemView.as_view(), name='add_item'),
    path('items/<int:item_id>/', views.UpdateItemView.as_view(), name='update_item'),
    path('items/<int:item_id>/save/', views.SaveForLaterView.as_view(), name='save_for_later'),
    path('saved/<int:saved_id>/move/', views.MoveToCartView.as_view(), name='move_to_cart'),
    path('saved/<int:saved_id>/', views.RemoveSavedView.as_view(), name='remove_saved'),
    path('coupon/', views.ApplyCouponView.as_view(), name='coupon'),
    path('validate/', views.ValidateCartView.as_view(), name='validate'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
]
