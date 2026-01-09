from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import (
    Notification, NotificationTemplate, NotificationPreference,
    DeviceToken, NotificationLog
)


class NotificationLogInline(TabularInline):
    model = NotificationLog
    extra = 0
    readonly_fields = ['channel', 'status', 'sent_at', 'delivered_at', 'error_message']
    can_delete = False


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ['title_short', 'user_email', 'type_badge', 'read_badge', 'priority', 'created_at']
    list_filter = ['notification_type', 'is_read', 'priority', 'created_at']
    search_fields = ['title', 'message', 'user__email']
    raw_id_fields = ['user']
    readonly_fields = ['id', 'created_at', 'updated_at', 'read_at', 'channels_sent']
    inlines = [NotificationLogInline]
    date_hierarchy = 'created_at'

    @admin.display(description='Tiêu đề')
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Loại')
    def type_badge(self, obj):
        colors = {
            'order_placed': '#28a745',
            'order_shipped': '#17a2b8',
            'payment_success': '#28a745',
            'security_alert': '#dc3545',
            'promotion': '#ffc107',
        }
        color = colors.get(obj.notification_type, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.get_notification_type_display()
        )

    @admin.display(description='Đã đọc')
    def read_badge(self, obj):
        if obj.is_read:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: gray;">○</span>')


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(ModelAdmin):
    list_display = ['notification_type', 'title_template', 'is_active', 'default_channels']
    list_filter = ['notification_type', 'is_active']
    search_fields = ['title_template', 'message_template']

    fieldsets = (
        ('Loại', {'fields': ('notification_type', 'is_active')}),
        ('In-App Template', {
            'fields': ('title_template', 'message_template', 'action_url_template', 'action_text')
        }),
        ('Email Template', {
            'fields': ('email_subject_template', 'email_template_name'),
            'classes': ('collapse',)
        }),
        ('Push Template', {
            'fields': ('push_title_template', 'push_body_template'),
            'classes': ('collapse',)
        }),
        ('SMS Template', {
            'fields': ('sms_template',),
            'classes': ('collapse',)
        }),
        ('Defaults', {
            'fields': ('default_channels', 'default_priority')
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(ModelAdmin):
    list_display = ['user_email', 'notification_type', 'in_app_enabled', 'email_enabled', 'push_enabled']
    list_filter = ['notification_type', 'in_app_enabled', 'email_enabled', 'push_enabled']
    search_fields = ['user__email']
    raw_id_fields = ['user']

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email


@admin.register(DeviceToken)
class DeviceTokenAdmin(ModelAdmin):
    list_display = ['user_email', 'platform', 'device_name', 'is_active', 'last_used']
    list_filter = ['platform', 'is_active']
    search_fields = ['user__email', 'device_name']
    raw_id_fields = ['user']
    actions = ['deactivate_tokens']

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email

    @admin.action(description='Vô hiệu hóa token')
    def deactivate_tokens(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'Đã vô hiệu hóa {count} token.')


@admin.register(NotificationLog)
class NotificationLogAdmin(ModelAdmin):
    list_display = ['notification_title', 'channel', 'status_badge', 'sent_at', 'error_short']
    list_filter = ['channel', 'status', 'created_at']
    search_fields = ['notification__title', 'notification__user__email']
    raw_id_fields = ['notification']
    readonly_fields = ['created_at', 'sent_at', 'delivered_at', 'opened_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    @admin.display(description='Thông báo')
    def notification_title(self, obj):
        return obj.notification.title[:40]

    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'sent': '#17a2b8',
            'delivered': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.get_status_display()
        )

    @admin.display(description='Lỗi')
    def error_short(self, obj):
        if obj.error_message:
            return obj.error_message[:50]
        return '-'
