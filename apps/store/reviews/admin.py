"""Store Reviews - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import Review, ReviewImage, ReviewReply, ReviewVote, ReviewReport, ReviewSummary


class ReviewImageInline(TabularInline):
    model = ReviewImage
    extra = 0
    fields = ['image', 'caption', 'sort_order']


class ReviewReplyInline(TabularInline):
    model = ReviewReply
    extra = 0
    fields = ['user', 'content', 'is_official', 'created_at']
    readonly_fields = ['created_at']


class ReviewReportInline(TabularInline):
    model = ReviewReport
    extra = 0
    fields = ['reporter', 'reason', 'status', 'created_at']
    readonly_fields = ['reporter', 'reason', 'created_at']


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ['product_name', 'user_email', 'rating_stars', 'verified_badge', 'status_badge', 'helpful_display', 'created_at']
    list_filter = ['rating', 'is_approved', 'is_rejected', 'is_verified_purchase', 'is_featured', 'created_at']
    search_fields = ['user__email', 'product__name', 'title', 'comment']
    raw_id_fields = ['user', 'product', 'order', 'moderated_by']
    readonly_fields = ['is_verified_purchase', 'helpful_count', 'not_helpful_count', 'moderated_at']
    date_hierarchy = 'created_at'
    inlines = [ReviewImageInline, ReviewReplyInline, ReviewReportInline]

    fieldsets = (
        ('Info', {'fields': ('user', 'product', 'order')}),
        ('Review', {'fields': ('rating', 'title', 'comment')}),
        ('Detailed Ratings', {'fields': ('quality_rating', 'value_rating', 'delivery_rating'), 'classes': ('collapse',)}),
        ('Verification', {'fields': ('is_verified_purchase',)}),
        ('Moderation', {'fields': ('is_approved', 'is_rejected', 'rejection_reason', 'moderated_by', 'moderated_at')}),
        ('Engagement', {'fields': ('helpful_count', 'not_helpful_count', 'is_featured', 'is_pinned'), 'classes': ('collapse',)}),
    )

    actions = ['approve_reviews', 'reject_reviews', 'feature_reviews']

    @admin.display(description='Product')
    def product_name(self, obj):
        return obj.product.name[:30]

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Rating')
    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        color = '#ffc107' if obj.rating >= 4 else '#dc3545' if obj.rating <= 2 else '#6c757d'
        return format_html('<span style="color: {};">{}</span>', color, stars)

    @admin.display(description='Verified')
    def verified_badge(self, obj):
        if obj.is_verified_purchase:
            return format_html('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">✓ Verified</span>')
        return '-'

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.is_approved:
            return format_html('<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">Approved</span>')
        elif obj.is_rejected:
            return format_html('<span style="background: #dc3545; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">Rejected</span>')
        return format_html('<span style="background: #ffc107; color: black; padding: 2px 8px; border-radius: 3px; font-size: 11px;">Pending</span>')

    @admin.display(description='Helpful')
    def helpful_display(self, obj):
        return f"👍 {obj.helpful_count} / 👎 {obj.not_helpful_count}"

    @admin.action(description='Approve selected reviews')
    def approve_reviews(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(is_approved=True, is_rejected=False, moderated_by=request.user, moderated_at=timezone.now())
        self.message_user(request, f'Approved {count} reviews.')

    @admin.action(description='Reject selected reviews')
    def reject_reviews(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(is_approved=False, is_rejected=True, moderated_by=request.user, moderated_at=timezone.now())
        self.message_user(request, f'Rejected {count} reviews.')

    @admin.action(description='Mark as featured')
    def feature_reviews(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'Featured {count} reviews.')


@admin.register(ReviewReport)
class ReviewReportAdmin(ModelAdmin):
    list_display = ['review', 'reporter', 'reason', 'status_badge', 'created_at']
    list_filter = ['reason', 'status', 'created_at']
    search_fields = ['review__user__email', 'reporter__email']
    raw_id_fields = ['review', 'reporter', 'handled_by']
    readonly_fields = ['created_at']

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'reviewed': '#17a2b8', 'resolved': '#28a745', 'dismissed': '#6c757d'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, obj.get_status_display())


@admin.register(ReviewSummary)
class ReviewSummaryAdmin(ModelAdmin):
    list_display = ['product', 'total_reviews', 'average_rating', 'verified_count', 'updated_at']
    search_fields = ['product__name']
    readonly_fields = ['product', 'total_reviews', 'average_rating', 'rating_5', 'rating_4', 'rating_3', 'rating_2', 'rating_1', 'avg_quality', 'avg_value', 'avg_delivery', 'verified_count', 'with_images_count', 'updated_at']

    actions = ['refresh_summaries']

    @admin.action(description='Refresh selected summaries')
    def refresh_summaries(self, request, queryset):
        for summary in queryset:
            summary.refresh()
        self.message_user(request, f'Refreshed {queryset.count()} summaries.')
