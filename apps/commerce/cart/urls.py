"""Commerce Cart - URL Configuration (Production-Ready)."""
from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    # ===== Cart Operations =====
    path('', views.CartView.as_view(), name='cart'),
    path('summary/', views.CartSummaryView.as_view(), name='summary'),
    
    # Add items
    path('add/', views.CartAddView.as_view(), name='add'),
    path('bulk-add/', views.CartBulkAddView.as_view(), name='bulk_add'),
    
    # Item operations
    path('items/<int:item_id>/', views.CartItemView.as_view(), name='item'),
    
    # ===== Saved for Later =====
    path('items/<int:item_id>/save/', views.SaveForLaterView.as_view(), name='save_for_later'),
    path('saved/<int:saved_id>/move/', views.MoveToCartView.as_view(), name='move_to_cart'),
    path('saved/<int:saved_id>/', views.RemoveSavedView.as_view(), name='remove_saved'),
    
    # ===== Coupon =====
    path('coupon/', views.CartCouponView.as_view(), name='coupon'),
    
    # ===== Validation & Refresh =====
    path('validate/', views.CartValidateView.as_view(), name='validate'),
    path('refresh-prices/', views.CartRefreshPricesView.as_view(), name='refresh_prices'),
    
    # ===== Merge =====
    path('merge/', views.CartMergeView.as_view(), name='merge'),
]
