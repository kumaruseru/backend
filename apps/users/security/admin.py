"""
Users Security - Admin Configuration.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    TwoFactorConfig, LoginAttempt, AccountLockout,
    APIKey, TrustedDevice, IPBlacklist, SecurityAuditLog
)


@admin.register(TwoFactorConfig)
class TwoFactorConfigAdmin(admin.ModelAdmin):
    """Admin for 2FA config."""
    
    list_display = ['user_email', 'method', 'is_enabled', 'backup_codes_count', 'last_used_at']
    list_filter = ['is_enabled', 'method']
    search_fields = ['user__email']
    raw_id_fields = ['user']
    readonly_fields = ['secret', 'backup_codes', 'last_used_at', 'setup_completed_at']
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin for login attempts."""
    
    list_display = ['status_badge', 'email', 'ip_address', 'device_type', 'country', 'created_at']
    list_filter = ['success', 'device_type', 'country', 'created_at']
    search_fields = ['email', 'ip_address']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False
    
    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')


@admin.register(AccountLockout)
class AccountLockoutAdmin(admin.ModelAdmin):
    """Admin for account lockouts."""
    
    list_display = ['user_email', 'reason_badge', 'locked_until', 'is_active', 'created_at']
    list_filter = ['reason', 'is_active', 'created_at']
    search_fields = ['user__email']
    raw_id_fields = ['user', 'unlocked_by']
    
    actions = ['unlock_accounts']
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.display(description='Reason')
    def reason_badge(self, obj):
        colors = {
            'failed_logins': '#ffc107',
            'suspicious': '#dc3545',
            'admin': '#6c757d',
            'brute_force': '#dc3545',
            'compromised': '#dc3545',
        }
        color = colors.get(obj.reason, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.get_reason_display()
        )
    
    @admin.action(description='Mở khóa tài khoản')
    def unlock_accounts(self, request, queryset):
        for lockout in queryset.filter(is_active=True):
            lockout.unlock(request.user)
        self.message_user(request, f'Đã mở khóa {queryset.count()} tài khoản.')


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin for API keys."""
    
    list_display = ['name', 'user_email', 'key_prefix', 'permission', 'is_active', 'last_used_at']
    list_filter = ['permission', 'is_active', 'created_at']
    search_fields = ['name', 'user__email', 'key_prefix']
    raw_id_fields = ['user']
    readonly_fields = ['key_prefix', 'key_hash', 'usage_count', 'last_used_at']
    
    actions = ['revoke_keys']
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.action(description='Thu hồi API key')
    def revoke_keys(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Đã thu hồi {count} API key.')


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    """Admin for trusted devices."""
    
    list_display = ['user_email', 'device_name', 'device_type', 'browser', 'is_active', 'last_used']
    list_filter = ['device_type', 'is_active', 'created_at']
    search_fields = ['user__email', 'device_name']
    raw_id_fields = ['user']
    
    actions = ['revoke_trust']
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.action(description='Thu hồi trust')
    def revoke_trust(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Đã thu hồi {count} trust.')


@admin.register(IPBlacklist)
class IPBlacklistAdmin(admin.ModelAdmin):
    """Admin for IP blacklist."""
    
    list_display = ['ip_address', 'reason', 'is_permanent', 'blocked_until', 'block_count', 'created_at']
    list_filter = ['reason', 'is_permanent', 'created_at']
    search_fields = ['ip_address', 'description']
    raw_id_fields = ['added_by']
    
    actions = ['unblock_ips']
    
    @admin.action(description='Gỡ block IP')
    def unblock_ips(self, request, queryset):
        count = queryset.delete()[0]
        self.message_user(request, f'Đã gỡ {count} IP.')


@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    """Admin for security audit logs."""
    
    list_display = ['event_type_display', 'user_email', 'severity_badge', 'ip_address', 'created_at']
    list_filter = ['event_type', 'severity', 'created_at']
    search_fields = ['user__email', 'ip_address', 'description']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email if obj.user else '-'
    
    @admin.display(description='Event')
    def event_type_display(self, obj):
        return obj.get_event_type_display()
    
    @admin.display(description='Severity')
    def severity_badge(self, obj):
        colors = {
            'info': '#17a2b8',
            'warning': '#ffc107',
            'critical': '#dc3545',
        }
        color = colors.get(obj.severity, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.severity.upper()
        )
