"""
URL configuration for OWLS Backend (DDD Architecture).

Complete API Routes for all domains:
- Users: identity, security, social, notifications
- Store: catalog, marketing, reviews, wishlist, inventory
- Commerce: cart, orders, billing, shipping, returns
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # ==================== Admin ====================
    path('admin/', admin.site.urls),
    
    # ==================== Users Domain ====================
    # Authentication & Identity
    path('api/auth/', include('apps.users.identity.urls', namespace='identity')),
    
    # Security (2FA, API Keys, etc.)
    path('api/security/', include('apps.users.security.urls', namespace='security')),
    
    # Social OAuth
    path('api/social/', include('apps.users.social.urls', namespace='social')),
    
    # Notifications
    path('api/notifications/', include('apps.users.notifications.urls', namespace='notifications')),
    
    # ==================== Store Domain ====================
    # Catalog (Products, Categories)
    path('api/catalog/', include('apps.store.catalog.urls', namespace='catalog')),
    
    # Marketing (Promotions, Coupons, Banners)
    path('api/marketing/', include('apps.store.marketing.urls', namespace='marketing')),
    
    # Reviews & Ratings
    path('api/reviews/', include('apps.store.reviews.urls', namespace='reviews')),
    
    # Wishlist
    path('api/wishlist/', include('apps.store.wishlist.urls', namespace='wishlist')),
    
    # Inventory
    path('api/inventory/', include('apps.store.inventory.urls', namespace='inventory')),
    
    # ==================== Commerce Domain ====================
    # Shopping Cart
    path('api/cart/', include('apps.commerce.cart.urls', namespace='cart')),
    
    # Orders
    path('api/orders/', include('apps.commerce.orders.urls', namespace='orders')),
    
    # Billing (Payments)
    path('api/billing/', include('apps.commerce.billing.urls', namespace='billing')),
    
    # Shipping
    path('api/shipping/', include('apps.commerce.shipping.urls', namespace='shipping')),
    
    # Returns & Refunds
    path('api/returns/', include('apps.commerce.returns.urls', namespace='returns')),
    
    # ==================== API Documentation ====================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
