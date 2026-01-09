"""
OWLS E-Commerce - URL Configuration.

Main URL router for the backend API.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from two_factor.urls import urlpatterns as two_factor_patterns
from apps.users.security.views import csp_report_view, honeypot_login_view

urlpatterns = [
    # Admin (2FA protected)
    path('admin-login/', admin.site.urls),
    
    # Two-Factor Authentication
    path('', include((two_factor_patterns[0], 'two_factor'))),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Health Check
    path('health/', include('health_check.urls')),
    
    # Language Switch
    path('i18n/', include('django.conf.urls.i18n')),
    
    # API Endpoints - Users
    path('api/auth/', include('apps.users.identity.urls')),
    path('api/notifications/', include('apps.users.notifications.urls')),
    path('api/social/', include('apps.users.social.urls')),
    
    # API Endpoints - Store
    path('api/catalog/', include('apps.store.catalog.urls')),
    path('api/reviews/', include('apps.store.reviews.urls')),
    path('api/wishlist/', include('apps.store.wishlist.urls')),
    path('api/marketing/', include('apps.store.marketing.urls')),
    path('api/inventory/', include('apps.store.inventory.urls')),
    
    # API Endpoints - Commerce
    path('api/cart/', include('apps.commerce.cart.urls')),
    path('api/orders/', include('apps.commerce.orders.urls')),
    path('api/payments/', include('apps.commerce.billing.urls')),
    path('api/shipping/', include('apps.commerce.shipping.urls')),
    path('api/returns/', include('apps.commerce.returns.urls')),
    
    # CSP Report endpoint (to avoid 404 spam)
    path('api/csp-report/', csp_report_view, name='csp_report'),
    
    # Security API
    path('api/security/', include('apps.users.security.urls', namespace='security')),
    
    # Honeypot - Fake admin pages to trap bots/attackers
    path('admin/', honeypot_login_view),
    path('wp-admin/', honeypot_login_view),
    path('wp-login/', honeypot_login_view),
    path('wp-login.php/', honeypot_login_view),
    path('administrator/', honeypot_login_view),
    path('phpmyadmin/', honeypot_login_view),
    path('pma/', honeypot_login_view),
    path('mysql/', honeypot_login_view),
    path('myadmin/', honeypot_login_view),
    path('cpanel/', honeypot_login_view),
    path('webadmin/', honeypot_login_view),
    path('siteadmin/', honeypot_login_view),
    path('panel/', honeypot_login_view),
    path('controlpanel/', honeypot_login_view),
    path('manager/', honeypot_login_view),
    path('manage/', honeypot_login_view),
    path('cms/', honeypot_login_view),
    path('backend/', honeypot_login_view),
    path('login/', honeypot_login_view),
    path('signin/', honeypot_login_view),
    path('.env/', honeypot_login_view),
    path('config/', honeypot_login_view),
]

