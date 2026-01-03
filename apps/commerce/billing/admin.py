"""
Commerce Billing - Production-Ready Admin Configuration.

Comprehensive admin interface with:
- Status badges
- Inline logs and refunds
- Payment analytics
- Refund actions
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Payment, Refund, PaymentLog, PaymentMethod


class PaymentLogInline(admin.TabularInline):
    """Inline for payment logs."""
    model = PaymentLog
    extra = 0
    readonly_fields = ['event', 'old_status', 'new_status', 'notes', 'created_at']
    can_delete = False
    max_num = 0
    
    def has_add_permission(self, request, obj=None):
        return False


class RefundInline(admin.TabularInline):
    """Inline for refunds."""
    model = Refund
    extra = 0
    readonly_fields = ['refund_type', 'amount', 'reason', 'status', 'created_at']
    fields = ['refund_type', 'amount', 'reason', 'status', 'refund_id', 'created_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for payments."""
    
    list_display = [
        'id_short', 'order_link', 'user_email',
        'method_badge', 'amount_display', 'status_badge',
        'retry_info', 'created_at'
    ]
    list_filter = [
        'status', 'method', 'currency',
        'created_at', 'paid_at'
    ]
    search_fields = [
        'id', 'order__order_number',
        'transaction_id', 'provider_transaction_id',
        'user__email'
    ]
    raw_id_fields = ['order', 'user']
    readonly_fields = [
        'created_at', 'updated_at', 'paid_at', 'captured_at',
        'payment_summary', 'provider_info'
    ]
    date_hierarchy = 'created_at'
    inlines = [PaymentLogInline, RefundInline]
    
    fieldsets = (
        ('Thông tin thanh toán', {
            'fields': (
                'order', 'user', 'payment_summary',
                'method', 'amount', 'currency', 'status'
            )
        }),
        ('Provider', {
            'fields': (
                'provider_info',
                'transaction_id', 'provider_transaction_id',
                'payment_url', 'qr_code_url'
            )
        }),
        ('Thất bại/Retry', {
            'fields': (
                'failure_reason', 'failure_code',
                'retry_count', 'max_retries'
            ),
            'classes': ('collapse',)
        }),
        ('Hoàn tiền', {
            'fields': ('refunded_amount',),
            'classes': ('collapse',)
        }),
        ('Thời gian', {
            'fields': ('expires_at', 'paid_at', 'captured_at', 'created_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('ip_address', 'provider_data', 'webhook_data'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_completed', 'mark_expired', 'export_csv']
    
    # Custom displays
    
    @admin.display(description='ID')
    def id_short(self, obj):
        return str(obj.id)[:8]
    
    @admin.display(description='Đơn hàng')
    def order_link(self, obj):
        return format_html(
            '<a href="/admin/orders/order/{}/change/">{}</a>',
            obj.order.id, obj.order.order_number
        )
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.display(description='Phương thức')
    def method_badge(self, obj):
        colors = {
            'cod': '#28A745',
            'vnpay': '#0066B3',
            'momo': '#A50064'
        }
        color = colors.get(obj.method, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_method_display()
        )
    
    @admin.display(description='Số tiền')
    def amount_display(self, obj):
        return f"{obj.amount:,.0f}₫"
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'processing': '#1E90FF',
            'awaiting_capture': '#9370DB',
            'completed': '#228B22',
            'failed': '#DC143C',
            'cancelled': '#808080',
            'expired': '#A0522D',
            'partial_refund': '#FF8C00',
            'refunded': '#6B7280'
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.display(description='Retry')
    def retry_info(self, obj):
        if obj.retry_count > 0:
            return f"{obj.retry_count}/{obj.max_retries}"
        return '-'
    
    @admin.display(description='Tổng quan')
    def payment_summary(self, obj):
        return format_html(
            '<strong>Đơn hàng:</strong> {}<br>'
            '<strong>Số tiền:</strong> {:,.0f}₫<br>'
            '<strong>Phương thức:</strong> {}<br>'
            '<strong>Trạng thái:</strong> {}',
            obj.order.order_number,
            obj.amount,
            obj.get_method_display(),
            obj.get_status_display()
        )
    
    @admin.display(description='Provider Info')
    def provider_info(self, obj):
        return format_html(
            '<strong>Transaction ID:</strong> {}<br>'
            '<strong>Provider ID:</strong> {}',
            obj.transaction_id or '-',
            obj.provider_transaction_id or '-'
        )
    
    # Actions
    
    @admin.action(description='Đánh dấu hoàn thành')
    def mark_completed(self, request, queryset):
        count = 0
        for payment in queryset.filter(status__in=['pending', 'processing']):
            payment.mark_completed()
            count += 1
        self.message_user(request, f'Đã cập nhật {count} thanh toán.')
    
    @admin.action(description='Đánh dấu hết hạn')
    def mark_expired(self, request, queryset):
        count = 0
        for payment in queryset.filter(status__in=['pending', 'processing']):
            payment.mark_expired()
            count += 1
        self.message_user(request, f'Đã cập nhật {count} thanh toán.')
    
    @admin.action(description='Export CSV')
    def export_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Mã đơn', 'Email', 'Phương thức',
            'Số tiền', 'Trạng thái', 'Mã GD', 'Ngày tạo'
        ])
        
        for obj in queryset:
            writer.writerow([
                str(obj.id)[:8],
                obj.order.order_number,
                obj.user.email,
                obj.get_method_display(),
                obj.amount,
                obj.get_status_display(),
                obj.transaction_id or '',
                obj.created_at.strftime('%d/%m/%Y %H:%M')
            ])
        
        return response


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """Admin for refunds."""
    
    list_display = [
        'id_short', 'payment_link', 'refund_type',
        'amount_display', 'reason', 'status_badge',
        'processed_by', 'created_at'
    ]
    list_filter = ['status', 'refund_type', 'reason', 'created_at']
    search_fields = ['id', 'payment__order__order_number', 'refund_id']
    raw_id_fields = ['payment', 'processed_by']
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
    
    @admin.display(description='ID')
    def id_short(self, obj):
        return str(obj.id)[:8]
    
    @admin.display(description='Payment')
    def payment_link(self, obj):
        return format_html(
            '<a href="/admin/billing/payment/{}/change/">{}</a>',
            obj.payment.id, obj.payment.order.order_number
        )
    
    @admin.display(description='Số tiền')
    def amount_display(self, obj):
        return f"{obj.amount:,.0f}₫"
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'processing': '#1E90FF',
            'completed': '#228B22',
            'failed': '#DC143C'
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    """Admin for payment logs."""
    list_display = ['payment', 'event', 'old_status', 'new_status', 'created_at']
    list_filter = ['event', 'created_at']
    search_fields = ['payment__order__order_number', 'notes']
    raw_id_fields = ['payment']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """Admin for saved payment methods."""
    list_display = ['user', 'display_name', 'method_type', 'provider', 'last_four', 'is_default', 'is_active']
    list_filter = ['method_type', 'provider', 'is_default', 'is_active']
    search_fields = ['user__email', 'display_name']
    raw_id_fields = ['user']
