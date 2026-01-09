"""Users Identity - Admin Configuration."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from .models import User, UserAddress, SocialAccount, UserSession, LoginHistory, UserPreferences


class UserAddressInline(admin.TabularInline):
    model = UserAddress
    extra = 0
    fields = ['label', 'recipient_name', 'phone', 'city', 'district', 'is_default']


class UserSessionInline(admin.TabularInline):
    model = UserSession
    extra = 0
    fields = ['device_type', 'browser', 'ip_address', 'is_active', 'last_activity']
    readonly_fields = ['device_type', 'browser', 'ip_address', 'last_activity']
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    list_display = ['email', 'full_name', 'phone', 'verified_badge', 'staff_badge', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'is_email_verified']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']
    inlines = [UserAddressInline, UserSessionInline]
    raw_id_fields = ['province', 'district', 'ward']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('Address', {'fields': ('address', 'province', 'district', 'ward')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Verification', {'fields': ('is_email_verified', 'email_verified_at')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),)
    readonly_fields = ['date_joined', 'last_login', 'email_verified_at']
    actions = ['verify_emails', 'deactivate_users']

    @admin.display(description='Full Name')
    def full_name(self, obj):
        return obj.full_name or '-'

    @admin.display(description='Verified')
    def verified_badge(self, obj):
        if obj.is_email_verified:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')

    @admin.display(description='Staff')
    def staff_badge(self, obj):
        if obj.is_superuser:
            return format_html('<span style="background: #6f42c1; color: white; padding: 2px 6px; border-radius: 3px;">Admin</span>')
        elif obj.is_staff:
            return format_html('<span style="background: #17a2b8; color: white; padding: 2px 6px; border-radius: 3px;">Staff</span>')
        return '-'

    @admin.action(description='Verify selected emails')
    def verify_emails(self, request, queryset):
        count = queryset.filter(is_email_verified=False).update(is_email_verified=True)
        self.message_user(request, f'Verified {count} emails.')

    @admin.action(description='Deactivate accounts')
    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {count} accounts.')


@admin.register(UserAddress)
class UserAddressAdmin(ModelAdmin):
    list_display = ['recipient_name', 'user', 'label', 'city', 'district', 'is_default']
    list_filter = ['is_default', 'city']
    search_fields = ['recipient_name', 'phone', 'street', 'user__email']
    raw_id_fields = ['user']


@admin.register(SocialAccount)
class SocialAccountAdmin(ModelAdmin):
    list_display = ['user', 'provider', 'uid', 'created_at']
    list_filter = ['provider']
    search_fields = ['user__email', 'uid']
    raw_id_fields = ['user']


@admin.register(UserSession)
class UserSessionAdmin(ModelAdmin):
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

    @admin.action(description='Terminate selected sessions')
    def terminate_sessions(self, request, queryset):
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'Terminated {count} sessions.')


@admin.register(LoginHistory)
class LoginHistoryAdmin(ModelAdmin):
    list_display = ['email', 'status_badge', 'ip_address', 'device_type', 'location', 'created_at']
    list_filter = ['status', 'fail_reason', 'device_type', 'created_at']
    search_fields = ['email', 'ip_address']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'success': '#28a745', 'failed': '#dc3545', 'blocked': '#6c757d'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>', color, obj.get_status_display())


@admin.register(UserPreferences)
class UserPreferencesAdmin(ModelAdmin):
    list_display = ['user', 'email_notifications', 'push_notifications', 'two_factor_enabled', 'language']
    list_filter = ['email_notifications', 'push_notifications', 'two_factor_enabled', 'language']
    search_fields = ['user__email']
