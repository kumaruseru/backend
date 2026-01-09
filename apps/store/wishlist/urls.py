"""Store Wishlist - URL Configuration."""
from django.urls import path
from . import views

app_name = 'wishlist'

urlpatterns = [
    # Wishlists
    path('wishlists/', views.WishlistListView.as_view(), name='list'),
    path('wishlists/create/', views.WishlistCreateView.as_view(), name='create'),
    path('wishlists/<uuid:wishlist_id>/', views.WishlistDetailView.as_view(), name='detail'),
    path('wishlists/<uuid:wishlist_id>/update/', views.WishlistUpdateView.as_view(), name='update'),
    path('wishlists/<uuid:wishlist_id>/share/', views.WishlistShareView.as_view(), name='share'),
    path('shared/<str:share_token>/', views.SharedWishlistView.as_view(), name='shared'),

    # Items
    path('items/add/', views.WishlistItemAddView.as_view(), name='add_item'),
    path('items/<int:item_id>/', views.WishlistItemUpdateView.as_view(), name='update_item'),
    path('toggle/', views.ToggleWishlistView.as_view(), name='toggle'),
    path('check/', views.CheckWishlistView.as_view(), name='check'),

    # Bulk
    path('bulk/add/', views.BulkAddView.as_view(), name='bulk_add'),
    path('bulk/remove/', views.BulkRemoveView.as_view(), name='bulk_remove'),
]
