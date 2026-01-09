"""Users Security - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import (
    TwoFactorConfig, LoginAttempt, AccountLockout, APIKey,
    TrustedDevice, IPBlacklist, SecurityAuditLog, CSPReport
)


@admin.register(TwoFactorConfig)
class TwoFactorConfigAdmin(ModelAdmin):
    list_display = ['user', 'is_enabled', 'method', 'last_used_at', 'created_at']
    list_filter = ['is_enabled', 'method']
    search_fields = ['user__email']
    raw_id_fields = ['user']


@admin.register(LoginAttempt)
class LoginAttemptAdmin(ModelAdmin):
    list_display = ['email', 'success_badge', 'ip_address', 'device_type', 'city', 'created_at']
    list_filter = ['success', 'device_type', 'created_at']
    search_fields = ['email', 'ip_address']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Status')
    def success_badge(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')


@admin.register(AccountLockout)
class AccountLockoutAdmin(ModelAdmin):
    list_display = ['user', 'reason', 'locked_until', 'is_active', 'created_at']
    list_filter = ['reason', 'is_active']
    search_fields = ['user__email', 'ip_address']
    raw_id_fields = ['user', 'unlocked_by']
    actions = ['unlock_accounts']

    @admin.action(description='Mở khóa tài khoản đã chọn')
    def unlock_accounts(self, request, queryset):
        for lockout in queryset.filter(is_active=True):
            lockout.unlock(unlocked_by=request.user)
        self.message_user(request, f'Đã mở khóa {queryset.count()} tài khoản.')


@admin.register(APIKey)
class APIKeyAdmin(ModelAdmin):
    list_display = ['name', 'user', 'key_prefix', 'permission', 'is_active', 'last_used_at', 'usage_count']
    list_filter = ['permission', 'is_active']
    search_fields = ['name', 'user__email', 'key_prefix']
    raw_id_fields = ['user']
    actions = ['revoke_keys']

    @admin.action(description='Thu hồi API keys đã chọn')
    def revoke_keys(self, request, queryset):
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'Đã thu hồi {count} API keys.')


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(ModelAdmin):
    list_display = ['user', 'device_name', 'device_type', 'browser', 'is_active', 'last_used']
    list_filter = ['is_active', 'device_type', 'browser']
    search_fields = ['user__email', 'device_name']
    raw_id_fields = ['user']


@admin.register(IPBlacklist)
class IPBlacklistAdmin(ModelAdmin):
    list_display = ['ip_address', 'reason', 'is_permanent', 'block_count', 'blocked_until', 'created_at']
    list_filter = ['reason', 'is_permanent']
    search_fields = ['ip_address', 'description']
    raw_id_fields = ['added_by']
    actions = ['unblock_ips']

    @admin.action(description='Gỡ chặn IP đã chọn')
    def unblock_ips(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Đã gỡ chặn {count} IP.')


@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(ModelAdmin):
    list_display = ['event_type', 'user', 'severity_badge', 'ip_address', 'created_at']
    list_filter = ['event_type', 'severity', 'created_at']
    search_fields = ['user__email', 'ip_address', 'description']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Severity')
    def severity_badge(self, obj):
        colors = {'info': '#17a2b8', 'warning': '#ffc107', 'critical': '#dc3545'}
        return format_html('<span style="color: {};">{}</span>', colors.get(obj.severity, '#6c757d'), obj.severity.upper())


@admin.register(CSPReport)
class CSPReportAdmin(ModelAdmin):
    list_display = ['violated_directive', 'blocked_uri_short', 'document_uri', 'created_at']
    list_filter = ['violated_directive', 'created_at']
    search_fields = ['blocked_uri', 'document_uri']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Blocked URI')
    def blocked_uri_short(self, obj):
        return obj.blocked_uri[:50] + '...' if len(obj.blocked_uri) > 50 else obj.blocked_uri
