"""
Users Social - Admin Configuration.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import ProviderConfig, SocialConnection, OAuthState, SocialLoginLog


@admin.register(ProviderConfig)
class ProviderConfigAdmin(admin.ModelAdmin):
    """Admin for OAuth provider config."""
    
    list_display = ['provider', 'is_active', 'display_name', 'created_at']
    list_filter = ['provider', 'is_active']
    search_fields = ['provider', 'display_name']
    
    fieldsets = (
        ('Provider', {'fields': ('provider', 'is_active')}),
        ('Credentials', {'fields': ('client_id', 'client_secret')}),
        ('URLs', {'fields': ('authorize_url', 'token_url', 'userinfo_url')}),
        ('Settings', {'fields': ('scopes',)}),
        ('Display', {'fields': ('display_name', 'icon_url', 'button_color')}),
    )


@admin.register(SocialConnection)
class SocialConnectionAdmin(admin.ModelAdmin):
    """Admin for social connections."""
    
    list_display = ['user_email', 'provider_badge', 'provider_name', 'is_primary', 'last_login']
    list_filter = ['provider', 'is_primary', 'created_at']
    search_fields = ['user__email', 'provider_username', 'provider_email']
    raw_id_fields = ['user']
    readonly_fields = ['access_token', 'refresh_token', 'token_expires_at', 'extra_data']
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.display(description='Provider')
    def provider_badge(self, obj):
        colors = {
            'google': '#4285F4',
            'github': '#24292E',
            'facebook': '#1877F2',
            'apple': '#000000',
            'discord': '#5865F2',
        }
        color = colors.get(obj.provider, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_provider_display()
        )


@admin.register(OAuthState)
class OAuthStateAdmin(admin.ModelAdmin):
    """Admin for OAuth states."""
    
    list_display = ['state_short', 'provider', 'action', 'expires_at', 'created_at']
    list_filter = ['provider', 'action']
    search_fields = ['state']
    readonly_fields = ['state', 'created_at']
    
    actions = ['cleanup_expired']
    
    @admin.display(description='State')
    def state_short(self, obj):
        return f"{obj.state[:8]}..."
    
    @admin.action(description='Xóa state hết hạn')
    def cleanup_expired(self, request, queryset):
        from django.utils import timezone
        count = OAuthState.objects.filter(expires_at__lt=timezone.now()).delete()[0]
        self.message_user(request, f'Đã xóa {count} state hết hạn.')


@admin.register(SocialLoginLog)
class SocialLoginLogAdmin(admin.ModelAdmin):
    """Admin for social login logs."""
    
    list_display = ['provider', 'status_badge', 'provider_email', 'action', 'ip_address', 'created_at']
    list_filter = ['provider', 'status', 'action', 'created_at']
    search_fields = ['provider_email', 'ip_address']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False
    
    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'success': '#28a745',
            'failed': '#dc3545',
            'error': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.get_status_display()
        )
