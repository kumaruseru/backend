"""Commerce Billing - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import PaymentTransaction, PaymentRefund


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(ModelAdmin):
    """Admin for payment transactions."""
    list_display = [
        'transaction_id', 'order_display', 'gateway_display',
        'amount_display', 'status_display', 'created_at',
    ]
    list_filter = ['gateway', 'status', 'created_at']
    search_fields = ['transaction_id', 'gateway_transaction_id', 'order__order_number']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    raw_id_fields = ['order', 'user']
    
    readonly_fields = [
        'id', 'transaction_id', 'order', 'user', 'gateway', 'status',
        'amount', 'currency', 'fee', 'gateway_transaction_id',
        'gateway_response', 'payment_url', 'return_url',
        'initiated_at', 'completed_at', 'expires_at',
        'error_code', 'error_message', 'ip_address', 'metadata',
        'created_at', 'updated_at',
    ]
    
    fieldsets = (
        ('Transaction', {
            'fields': ('transaction_id', 'order', 'user', 'gateway', 'status')
        }),
        ('Amount', {
            'fields': ('amount', 'currency', 'fee')
        }),
        ('Gateway Details', {
            'fields': ('gateway_transaction_id', 'payment_url', 'gateway_response')
        }),
        ('Timestamps', {
            'fields': ('initiated_at', 'completed_at', 'expires_at')
        }),
        ('Errors', {
            'fields': ('error_code', 'error_message'),
            'classes': ['collapse'],
        }),
        ('Metadata', {
            'fields': ('ip_address', 'metadata'),
            'classes': ['collapse'],
        }),
    )
    
    @display(description='Order')
    def order_display(self, obj):
        return format_html(
            '<a href="/admin/orders/order/{}/">{}</a>',
            obj.order_id, obj.order.order_number
        )
    
    @display(description='Gateway')
    def gateway_display(self, obj):
        colors = {
            'cod': '#6b7280',
            'momo': '#a855f7',
            'vnpay': '#3b82f6',
            'stripe': '#6366f1',
        }
        color = colors.get(obj.gateway, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_gateway_display()
        )
    
    @display(description='Amount')
    def amount_display(self, obj):
        return format_html('₫{:,.0f}', obj.amount)
    
    @display(description='Status')
    def status_display(self, obj):
        colors = {
            'pending': '#f59e0b',
            'processing': '#3b82f6',
            'completed': '#22c55e',
            'failed': '#ef4444',
            'cancelled': '#6b7280',
            'expired': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PaymentRefund)
class PaymentRefundAdmin(ModelAdmin):
    """Admin for payment refunds."""
    list_display = [
        'refund_id', 'order_display', 'amount_display',
        'status_display', 'reason', 'created_at',
    ]
    list_filter = ['status', 'reason', 'created_at']
    search_fields = ['refund_id', 'order__order_number', 'transaction__transaction_id']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    raw_id_fields = ['transaction', 'order', 'processed_by']
    
    readonly_fields = [
        'id', 'refund_id', 'transaction', 'order', 'processed_by',
        'status', 'reason', 'notes', 'amount', 'is_partial',
        'gateway_refund_id', 'gateway_response',
        'requested_at', 'completed_at', 'created_at', 'updated_at',
    ]
    
    @display(description='Order')
    def order_display(self, obj):
        return obj.order.order_number
    
    @display(description='Amount')
    def amount_display(self, obj):
        label = 'Partial' if obj.is_partial else 'Full'
        return format_html(
            '₫{:,.0f} <span style="color: #6b7280; font-size: 11px;">({})</span>',
            obj.amount, label
        )
    
    @display(description='Status')
    def status_display(self, obj):
        colors = {
            'pending': '#f59e0b',
            'processing': '#3b82f6',
            'completed': '#22c55e',
            'failed': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    def has_add_permission(self, request):
        return False
