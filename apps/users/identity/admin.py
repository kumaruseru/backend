"""
Users Identity - Production-Ready Admin Configuration.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, UserAddress, SocialAccount,
    UserSession, LoginHistory, UserPreferences, AccountDeletionRequest
)


class UserAddressInline(admin.TabularInline):
    """Inline for user addresses."""
    model = UserAddress
    extra = 0
    fields = ['label', 'recipient_name', 'phone', 'city', 'district', 'is_default']
    readonly_fields = []


class UserSessionInline(admin.TabularInline):
    """Inline for active sessions."""
    model = UserSession
    extra = 0
    fields = ['device_type', 'browser', 'ip_address', 'is_active', 'last_activity']
    readonly_fields = ['device_type', 'browser', 'ip_address', 'last_activity']
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for User model."""
    
    list_display = ['email', 'full_name', 'phone', 'verified_badge', 'staff_badge', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'is_email_verified', 'is_deleted']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']
    inlines = [UserAddressInline, UserSessionInline]
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Thông tin', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('Địa chỉ', {
            'fields': ('address', 'ward', 'district', 'city', 'province_id', 'district_id', 'ward_code'),
            'classes': ('collapse',)
        }),
        ('Quyền', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Xác thực', {'fields': ('is_email_verified', 'email_verified_at')}),
        ('Thời gian', {'fields': ('last_login', 'date_joined')}),
        ('Xóa mềm', {'fields': ('is_deleted', 'deleted_at'), 'classes': ('collapse',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['date_joined', 'last_login', 'email_verified_at', 'deleted_at']
    
    actions = ['verify_emails', 'deactivate_users']
    
    @admin.display(description='Họ tên')
    def full_name(self, obj):
        return obj.full_name or '-'
    
    @admin.display(description='Xác thực')
    def verified_badge(self, obj):
        if obj.is_email_verified:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    
    @admin.display(description='Staff')
    def staff_badge(self, obj):
        if obj.is_superuser:
            return format_html('<span style="background: #6f42c1; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">Admin</span>')
        elif obj.is_staff:
            return format_html('<span style="background: #17a2b8; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">Staff</span>')
        return '-'
    
    @admin.action(description='Xác thực email đã chọn')
    def verify_emails(self, request, queryset):
        count = queryset.filter(is_email_verified=False).update(is_email_verified=True)
        self.message_user(request, f'Đã xác thực {count} email.')
    
    @admin.action(description='Vô hiệu hóa tài khoản')
    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Đã vô hiệu hóa {count} tài khoản.')


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    """Admin for UserAddress."""
    
    list_display = ['recipient_name', 'user', 'label', 'city', 'district', 'is_default']
    list_filter = ['is_default', 'city']
    search_fields = ['recipient_name', 'phone', 'street', 'user__email']
    raw_id_fields = ['user']


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """Admin for SocialAccount."""
    
    list_display = ['user', 'provider', 'uid', 'created_at']
    list_filter = ['provider']
    search_fields = ['user__email', 'uid']
    raw_id_fields = ['user']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin for user sessions."""
    
    list_display = ['user_email', 'device_display', 'ip_address', 'is_active', 'last_activity']
    list_filter = ['is_active', 'device_type', 'browser']
    search_fields = ['user__email', 'ip_address']
    raw_id_fields = ['user']
    readonly_fields = ['session_key', 'created_at']
    
    actions = ['terminate_sessions']
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.display(description='Device')
    def device_display(self, obj):
        return f"{obj.device_name or obj.device_type} - {obj.browser}"
    
    @admin.action(description='Kết thúc phiên đã chọn')
    def terminate_sessions(self, request, queryset):
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'Đã kết thúc {count} phiên.')


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """Admin for login history."""
    
    list_display = ['email', 'status_badge', 'ip_address', 'device_type', 'location', 'created_at']
    list_filter = ['status', 'fail_reason', 'device_type', 'created_at']
    search_fields = ['email', 'ip_address']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'success': '#28a745',
            'failed': '#dc3545',
            'blocked': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.get_status_display()
        )


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    """Admin for user preferences."""
    
    list_display = ['user', 'email_notifications', 'push_notifications', 'two_factor_enabled', 'language']
    list_filter = ['email_notifications', 'push_notifications', 'two_factor_enabled', 'language']
    search_fields = ['user__email']


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    """Admin for deletion requests."""
    
    list_display = ['user_email', 'status_badge', 'scheduled_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__email']
    raw_id_fields = ['user', 'processed_by']
    readonly_fields = ['created_at', 'processed_at']
    
    actions = ['approve_requests', 'cancel_requests']
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#17a2b8',
            'completed': '#28a745',
            'cancelled': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.action(description='Duyệt yêu cầu')
    def approve_requests(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status='pending').update(
            status='approved',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'Đã duyệt {count} yêu cầu.')
    
    @admin.action(description='Hủy yêu cầu')
    def cancel_requests(self, request, queryset):
        count = queryset.filter(status='pending').update(status='cancelled')
        self.message_user(request, f'Đã hủy {count} yêu cầu.')
