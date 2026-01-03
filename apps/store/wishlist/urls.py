"""Store Wishlist - URL Configuration (Production-Ready)."""
from django.urls import path
from . import views

app_name = 'wishlist'

urlpatterns = [
    # ===== Wishlists =====
    path('', views.WishlistListView.as_view(), name='list'),
    path('create/', views.WishlistCreateView.as_view(), name='create'),
    path('<uuid:wishlist_id>/', views.WishlistDetailView.as_view(), name='detail'),
    path('<uuid:wishlist_id>/items/', views.WishlistItemsView.as_view(), name='items'),
    path('<uuid:wishlist_id>/share/', views.WishlistShareView.as_view(), name='share'),
    
    # ===== Shared =====
    path('shared/<str:share_token>/', views.SharedWishlistView.as_view(), name='shared'),
    
    # ===== Items =====
    path('items/add/', views.AddItemView.as_view(), name='add_item'),
    path('items/<int:item_id>/', views.ItemDetailView.as_view(), name='item_detail'),
    path('items/<int:item_id>/move/', views.MoveItemView.as_view(), name='move_item'),
    
    # ===== Quick Actions =====
    path('toggle/<uuid:product_id>/', views.ToggleWishlistView.as_view(), name='toggle'),
    path('check/<uuid:product_id>/', views.CheckWishlistView.as_view(), name='check'),
    
    # ===== Bulk =====
    path('bulk/add/', views.BulkAddView.as_view(), name='bulk_add'),
    path('bulk/remove/', views.BulkRemoveView.as_view(), name='bulk_remove'),
    path('bulk/to-cart/', views.MoveToCartView.as_view(), name='to_cart'),
]
