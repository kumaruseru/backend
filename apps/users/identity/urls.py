"""Users Identity - URL Configuration."""
from django.urls import path
from . import views

app_name = 'identity'

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', views.RefreshTokenView.as_view(), name='token_refresh'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend_verification'),

    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('password/change/', views.PasswordChangeView.as_view(), name='password_change'),

    # Addresses
    path('addresses/', views.AddressListView.as_view(), name='address_list'),
    path('addresses/<int:address_id>/', views.AddressDetailView.as_view(), name='address_detail'),
    path('addresses/<int:address_id>/set-default/', views.AddressSetDefaultView.as_view(), name='address_set_default'),

    # Sessions & Security
    path('sessions/', views.SessionListView.as_view(), name='session_list'),
    path('sessions/<int:session_id>/terminate/', views.SessionTerminateView.as_view(), name='session_terminate'),
    path('sessions/terminate-all/', views.SessionTerminateAllView.as_view(), name='session_terminate_all'),
    path('login-history/', views.LoginHistoryView.as_view(), name='login_history'),

    # Preferences
    path('preferences/', views.PreferencesView.as_view(), name='preferences'),
]
