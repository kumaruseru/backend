"""Users Security - URL Configuration."""
from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # 2FA
    path('2fa/status/', views.TwoFactorStatusView.as_view(), name='2fa_status'),
    path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('2fa/enable/', views.TwoFactorEnableView.as_view(), name='2fa_enable'),
    path('2fa/disable/', views.TwoFactorDisableView.as_view(), name='2fa_disable'),
    path('2fa/verify/', views.TwoFactorVerifyView.as_view(), name='2fa_verify'),
    path('2fa/backup-codes/', views.BackupCodesView.as_view(), name='2fa_backup_codes'),

    # API Keys
    path('api-keys/', views.APIKeyListView.as_view(), name='api_key_list'),
    path('api-keys/<uuid:key_id>/', views.APIKeyDetailView.as_view(), name='api_key_detail'),

    # Trusted Devices
    path('trusted-devices/', views.TrustedDeviceListView.as_view(), name='trusted_device_list'),
    path('trusted-devices/<int:device_id>/revoke/', views.TrustedDeviceRevokeView.as_view(), name='trusted_device_revoke'),
    path('trusted-devices/revoke-all/', views.TrustedDeviceRevokeAllView.as_view(), name='trusted_device_revoke_all'),

    # History & Audit
    path('login-history/', views.LoginHistoryView.as_view(), name='login_history'),
    path('audit-log/', views.SecurityAuditView.as_view(), name='audit_log'),

    # Overview
    path('overview/', views.SecurityOverviewView.as_view(), name='overview'),

    # IP Check
    path('check-ip/', views.CheckIPBlockedView.as_view(), name='check_ip'),

    # CSP Reports
    path('csp-report/', views.CSPReportView.as_view(), name='csp_report'),

    # Honeypot
    path('', views.honeypot_login_view, name='honeypot'),
    path('login/', views.honeypot_login_view, name='honeypot_login'),
]
