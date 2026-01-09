"""Users Social - URL Configuration."""
from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    path('providers/', views.AvailableProvidersView.as_view(), name='providers'),
    path('authorize/', views.OAuthAuthorizeView.as_view(), name='authorize'),
    path('callback/<str:provider>/', views.OAuthCallbackView.as_view(), name='callback'),
    path('connections/', views.SocialConnectionsView.as_view(), name='connections'),
    path('connect/', views.ConnectView.as_view(), name='connect'),
    path('disconnect/', views.DisconnectView.as_view(), name='disconnect'),
]
