"""
Commerce Returns - Production-Ready Admin Configuration.

Comprehensive admin interface with:
- Inline editing for items and images
- Advanced filtering and search
- Bulk actions
- Status change actions
- Export capability
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import ReturnRequest, ReturnItem, ReturnImage, ReturnStatusHistory


class ReturnItemInline(admin.TabularInline):
    """Inline for return items."""
    model = ReturnItem
    extra = 0
    readonly_fields = ['order_item', 'unit_price', 'subtotal', 'created_at']
    fields = [
        'order_item', 'quantity', 'reason', 'condition',
        'unit_price', 'accepted_quantity', 'refund_amount'
    ]
    
    @admin.display(description='Đơn giá')
    def unit_price(self, obj):
        return f"{obj.unit_price:,.0f}₫"
    
    @admin.display(description='Thành tiền')
    def subtotal(self, obj):
        return f"{obj.subtotal:,.0f}₫"


class ReturnImageInline(admin.TabularInline):
    """Inline for return images."""
    model = ReturnImage
    extra = 0
    readonly_fields = ['image_preview', 'uploaded_by', 'created_at']
    fields = ['image', 'image_preview', 'caption', 'uploaded_by']
    
    @admin.display(description='Preview')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px;"/>',
                obj.image.url
            )
        return '-'


class ReturnStatusHistoryInline(admin.TabularInline):
    """Inline for status history."""
    model = ReturnStatusHistory
    extra = 0
    readonly_fields = ['status', 'changed_by', 'notes', 'created_at']
    can_delete = False
    max_num = 0  # No add button
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    """Admin for return requests."""
    
    list_display = [
        'request_number', 'order_link', 'user_email',
        'status_badge', 'reason', 'total_items_display',
        'requested_refund_display', 'approved_refund_display',
        'days_since_created', 'created_at'
    ]
    list_filter = [
        'status', 'reason', 'refund_method',
        'quality_check_passed', 'created_at'
    ]
    search_fields = [
        'request_number', 'order__order_number',
        'user__email', 'user__first_name', 'user__last_name',
        'description', 'admin_notes'
    ]
    raw_id_fields = ['order', 'user', 'processed_by', 'refund']
    readonly_fields = [
        'request_number', 'created_at', 'updated_at',
        'processed_at', 'received_at', 'refunded_at', 'completed_at',
        'order_info', 'user_info', 'refund_summary'
    ]
    date_hierarchy = 'created_at'
    inlines = [ReturnItemInline, ReturnImageInline, ReturnStatusHistoryInline]
    
    fieldsets = (
        ('Thông tin yêu cầu', {
            'fields': (
                'request_number', 'order', 'order_info',
                'user', 'user_info', 'status'
            )
        }),
        ('Chi tiết', {
            'fields': ('reason', 'description')
        }),
        ('Hoàn tiền', {
            'fields': (
                'refund_method', 'requested_refund', 'approved_refund',
                'bank_name', 'bank_account_number', 'bank_account_name',
                'refund', 'refund_summary'
            )
        }),
        ('Vận chuyển trả hàng', {
            'fields': ('return_tracking_code', 'return_carrier'),
            'classes': ('collapse',)
        }),
        ('Xử lý', {
            'fields': (
                'admin_notes', 'rejection_reason',
                'processed_by', 'processed_at'
            )
        }),
        ('Kiểm tra chất lượng', {
            'fields': ('quality_check_passed', 'quality_check_notes', 'received_at'),
            'classes': ('collapse',)
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at', 'refunded_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'start_review_action',
        'approve_action',
        'receive_action',
        'complete_action',
        'export_csv'
    ]
    
    # Custom displays
    
    @admin.display(description='Đơn hàng', ordering='order__order_number')
    def order_link(self, obj):
        return format_html(
            '<a href="/admin/orders/order/{}/change/">{}</a>',
            obj.order.id, obj.order.order_number
        )
    
    @admin.display(description='Khách hàng', ordering='user__email')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'reviewing': '#1E90FF',
            'approved': '#32CD32',
            'rejected': '#DC143C',
            'awaiting_return': '#FFD700',
            'received': '#9370DB',
            'processing_refund': '#20B2AA',
            'completed': '#228B22',
            'cancelled': '#808080'
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.display(description='Items')
    def total_items_display(self, obj):
        return obj.total_items
    
    @admin.display(description='Yêu cầu')
    def requested_refund_display(self, obj):
        return f"{obj.requested_refund:,.0f}₫"
    
    @admin.display(description='Duyệt')
    def approved_refund_display(self, obj):
        if obj.approved_refund:
            return f"{obj.approved_refund:,.0f}₫"
        return '-'
    
    @admin.display(description='Ngày')
    def days_since_created(self, obj):
        delta = timezone.now() - obj.created_at
        return f"{delta.days}d"
    
    @admin.display(description='Thông tin đơn hàng')
    def order_info(self, obj):
        return format_html(
            '<strong>Mã đơn:</strong> {}<br>'
            '<strong>Tổng tiền:</strong> {:,.0f}₫<br>'
            '<strong>Ngày giao:</strong> {}',
            obj.order.order_number,
            obj.order.total,
            obj.order.delivered_at.strftime('%d/%m/%Y %H:%M') if obj.order.delivered_at else '-'
        )
    
    @admin.display(description='Thông tin khách hàng')
    def user_info(self, obj):
        return format_html(
            '<strong>Email:</strong> {}<br>'
            '<strong>SĐT:</strong> {}',
            obj.user.email,
            obj.user.phone or '-'
        )
    
    @admin.display(description='Tổng kết hoàn tiền')
    def refund_summary(self, obj):
        return format_html(
            '<strong>Yêu cầu:</strong> {:,.0f}₫<br>'
            '<strong>Đã duyệt:</strong> {:,.0f}₫<br>'
            '<strong>Phương thức:</strong> {}',
            obj.requested_refund,
            obj.approved_refund,
            obj.get_refund_method_display()
        )
    
    # Actions
    
    @admin.action(description='Bắt đầu xem xét')
    def start_review_action(self, request, queryset):
        count = 0
        for return_request in queryset.filter(status='pending'):
            return_request.start_review(request.user)
            count += 1
        self.message_user(request, f'Đã bắt đầu xem xét {count} yêu cầu.')
    
    @admin.action(description='Duyệt (hoàn tiền theo yêu cầu)')
    def approve_action(self, request, queryset):
        count = 0
        for return_request in queryset.filter(status__in=['pending', 'reviewing']):
            return_request.approve(
                request.user,
                return_request.requested_refund,
                'Bulk approved from admin'
            )
            count += 1
        self.message_user(request, f'Đã duyệt {count} yêu cầu.')
    
    @admin.action(description='Xác nhận đã nhận hàng (passed)')
    def receive_action(self, request, queryset):
        count = 0
        for return_request in queryset.filter(status__in=['approved', 'awaiting_return']):
            return_request.receive_items(request.user, True, 'Bulk received from admin')
            count += 1
        self.message_user(request, f'Đã xác nhận nhận {count} yêu cầu.')
    
    @admin.action(description='Hoàn tất')
    def complete_action(self, request, queryset):
        count = 0
        for return_request in queryset.filter(status__in=['received', 'processing_refund']):
            return_request.complete(request.user)
            count += 1
        self.message_user(request, f'Đã hoàn tất {count} yêu cầu.')
    
    @admin.action(description='Export CSV')
    def export_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="returns.csv"'
        response.write('\ufeff')  # BOM for Excel UTF-8
        
        writer = csv.writer(response)
        writer.writerow([
            'Mã yêu cầu', 'Mã đơn hàng', 'Email', 'Trạng thái',
            'Lý do', 'Yêu cầu hoàn', 'Đã duyệt', 'Ngày tạo'
        ])
        
        for obj in queryset:
            writer.writerow([
                obj.request_number,
                obj.order.order_number,
                obj.user.email,
                obj.get_status_display(),
                obj.get_reason_display(),
                obj.requested_refund,
                obj.approved_refund,
                obj.created_at.strftime('%d/%m/%Y %H:%M')
            ])
        
        return response


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    """Admin for return items."""
    list_display = ['return_request', 'product_name', 'quantity', 'unit_price', 'refund_amount']
    list_filter = ['reason', 'created_at']
    search_fields = ['return_request__request_number', 'order_item__product_name']
    raw_id_fields = ['return_request', 'order_item']
    
    @admin.display(description='Sản phẩm')
    def product_name(self, obj):
        return obj.order_item.product_name
    
    @admin.display(description='Đơn giá')
    def unit_price(self, obj):
        return f"{obj.order_item.unit_price:,.0f}₫"


@admin.register(ReturnImage)
class ReturnImageAdmin(admin.ModelAdmin):
    """Admin for return images."""
    list_display = ['return_request', 'image_preview', 'caption', 'uploaded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['return_request__request_number', 'caption']
    raw_id_fields = ['return_request', 'uploaded_by']
    
    @admin.display(description='Preview')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px;"/>',
                obj.image.url
            )
        return '-'


@admin.register(ReturnStatusHistory)
class ReturnStatusHistoryAdmin(admin.ModelAdmin):
    """Admin for status history."""
    list_display = ['return_request', 'status', 'changed_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['return_request__request_number']
    raw_id_fields = ['return_request', 'changed_by']
    readonly_fields = ['created_at']
