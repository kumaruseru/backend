"""Commerce Returns - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import ReturnRequest, ReturnItem, ReturnImage, ReturnStatusHistory


class ReturnItemInline(TabularInline):
    model = ReturnItem
    extra = 0
    fields = ['order_item', 'quantity', 'reason', 'condition', 'accepted_quantity', 'refund_amount']
    readonly_fields = ['order_item', 'quantity']


class ReturnImageInline(TabularInline):
    model = ReturnImage
    extra = 0
    fields = ['image', 'caption', 'created_at']
    readonly_fields = ['created_at']


class ReturnStatusHistoryInline(TabularInline):
    model = ReturnStatusHistory
    extra = 0
    readonly_fields = ['status', 'changed_by', 'notes', 'created_at']
    ordering = ['-created_at']


@admin.register(ReturnRequest)
class ReturnRequestAdmin(ModelAdmin):
    list_display = ['request_number', 'order_number', 'user_email', 'status_badge', 'reason_badge', 'refund_display', 'created_at']
    list_filter = ['status', 'reason', 'refund_method', 'quality_check_passed', 'created_at']
    search_fields = ['request_number', 'order__order_number', 'user__email']
    raw_id_fields = ['order', 'user', 'processed_by']
    readonly_fields = ['request_number', 'requested_refund', 'processed_at', 'received_at', 'refunded_at', 'completed_at', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    inlines = [ReturnItemInline, ReturnImageInline, ReturnStatusHistoryInline]

    fieldsets = (
        ('Request', {'fields': ('request_number', 'order', 'user', 'status')}),
        ('Reason', {'fields': ('reason', 'description')}),
        ('Refund', {'fields': ('refund_method', 'requested_refund', 'approved_refund')}),
        ('Bank Info', {'fields': ('bank_name', 'bank_account_number', 'bank_account_name'), 'classes': ('collapse',)}),
        ('Return Shipping', {'fields': ('return_tracking_code', 'return_carrier'), 'classes': ('collapse',)}),
        ('Processing', {'fields': ('processed_by', 'processed_at', 'admin_notes', 'rejection_reason')}),
        ('Quality Check', {'fields': ('quality_check_passed', 'quality_check_notes')}),
        ('Timestamps', {'fields': ('received_at', 'refunded_at', 'completed_at', 'created_at'), 'classes': ('collapse',)}),
    )

    actions = ['approve_returns', 'reject_returns', 'mark_received']

    @admin.display(description='Order')
    def order_number(self, obj):
        return obj.order.order_number

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'reviewing': '#17a2b8', 'approved': '#28a745', 'rejected': '#dc3545', 'awaiting_return': '#fd7e14', 'received': '#6f42c1', 'processing_refund': '#17a2b8', 'completed': '#28a745', 'cancelled': '#6c757d'}
        color = colors.get(obj.status, '#6c757d')
        text_color = 'black' if obj.status in ['pending', 'awaiting_return'] else 'white'
        return format_html('<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, text_color, obj.get_status_display())

    @admin.display(description='Reason')
    def reason_badge(self, obj):
        return obj.get_reason_display()

    @admin.display(description='Refund')
    def refund_display(self, obj):
        if obj.approved_refund > 0:
            return f"✅ {obj.approved_refund:,.0f}₫"
        return f"⏳ {obj.requested_refund:,.0f}₫"

    @admin.action(description='Approve selected')
    def approve_returns(self, request, queryset):
        count = 0
        for return_request in queryset.filter(status__in=['pending', 'reviewing']):
            return_request.approve(request.user, return_request.requested_refund, 'Approved via admin action')
            count += 1
        self.message_user(request, f'Approved {count} returns.')

    @admin.action(description='Reject selected')
    def reject_returns(self, request, queryset):
        count = 0
        for return_request in queryset.filter(status__in=['pending', 'reviewing']):
            return_request.reject(request.user, 'Rejected via admin action')
            count += 1
        self.message_user(request, f'Rejected {count} returns.')

    @admin.action(description='Mark as received')
    def mark_received(self, request, queryset):
        count = 0
        for return_request in queryset.filter(status__in=['approved', 'awaiting_return']):
            return_request.receive_items(request.user, True, 'Received via admin action')
            count += 1
        self.message_user(request, f'Marked {count} returns as received.')
