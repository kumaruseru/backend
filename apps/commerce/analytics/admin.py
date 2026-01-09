"""Commerce Analytics - Admin Configuration.

Professional Unfold admin interface with Chart.js visualizations.
"""
from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import (
    DailyMetric, MonthlyReport, ProductAnalytics,
    CustomerSegment, SalesFunnel, RevenueBreakdown,
    TrafficSource, AbandonedCartMetric
)
from .services import AnalyticsService, CustomerAnalyticsService


@admin.register(DailyMetric)
class DailyMetricAdmin(ModelAdmin):
    """Admin for daily metrics with trend visualization."""
    list_display = [
        'date', 'revenue_display', 'orders_display',
        'customers_display', 'aov_display', 'conversion_display',
    ]
    list_filter = ['date']
    search_fields = ['date']
    date_hierarchy = 'date'
    ordering = ['-date']
    
    readonly_fields = [
        'date', 'total_revenue', 'gross_revenue', 'total_discount',
        'shipping_revenue', 'total_orders', 'pending_orders',
        'confirmed_orders', 'completed_orders', 'cancelled_orders',
        'refunded_orders', 'new_customers', 'returning_customers',
        'unique_customers', 'total_items_sold', 'unique_products_sold',
        'carts_created', 'carts_converted', 'carts_abandoned',
        'return_requests', 'total_refund_amount', 'average_order_value',
        'conversion_rate', 'cancellation_rate', 'return_rate',
        'created_at', 'updated_at',
    ]
    
    fieldsets = (
        ('Date', {'fields': ('date',)}),
        ('Revenue', {'fields': (
            'total_revenue', 'gross_revenue', 'total_discount', 'shipping_revenue'
        )}),
        ('Orders', {'fields': (
            'total_orders', 'pending_orders', 'confirmed_orders',
            'completed_orders', 'cancelled_orders', 'refunded_orders'
        )}),
        ('Customers', {'fields': (
            'new_customers', 'returning_customers', 'unique_customers'
        )}),
        ('Products', {'fields': ('total_items_sold', 'unique_products_sold')}),
        ('Carts', {'fields': ('carts_created', 'carts_converted', 'carts_abandoned')}),
        ('Returns', {'fields': ('return_requests', 'total_refund_amount')}),
        ('Rates', {'fields': (
            'average_order_value', 'conversion_rate', 'cancellation_rate', 'return_rate'
        )}),
    )
    
    @display(description='Revenue')
    def revenue_display(self, obj):
        return format_html(
            '<span style="font-weight: 600; color: #22c55e;">₫{:,.0f}</span>',
            obj.total_revenue
        )
    
    @display(description='Orders')
    def orders_display(self, obj):
        return format_html(
            '<span style="font-weight: 600;">{}</span> '
            '<span style="color: #6b7280; font-size: 11px;">({} completed)</span>',
            obj.total_orders, obj.completed_orders
        )
    
    @display(description='Customers')
    def customers_display(self, obj):
        return format_html(
            '<span style="color: #3b82f6;">{} new</span> / '
            '<span style="color: #8b5cf6;">{} returning</span>',
            obj.new_customers, obj.returning_customers
        )
    
    @display(description='AOV')
    def aov_display(self, obj):
        return format_html('₫{:,.0f}', obj.average_order_value)
    
    @display(description='Conversion')
    def conversion_display(self, obj):
        color = '#22c55e' if obj.conversion_rate >= 3 else '#f59e0b' if obj.conversion_rate >= 1 else '#ef4444'
        return format_html(
            '<span style="color: {}; font-weight: 600;">{:.2f}%</span>',
            color, obj.conversion_rate
        )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MonthlyReport)
class MonthlyReportAdmin(ModelAdmin):
    """Admin for monthly business reports."""
    list_display = [
        'period_display', 'revenue_display', 'orders_display',
        'customers_display', 'growth_display',
    ]
    list_filter = ['year']
    ordering = ['-year', '-month']
    
    readonly_fields = [
        'year', 'month', 'total_revenue', 'total_orders',
        'completed_orders', 'cancelled_orders', 'refunded_orders',
        'total_customers', 'new_customers', 'returning_customers',
        'total_items_sold', 'total_refunds', 'average_order_value',
        'average_daily_revenue', 'average_daily_orders',
        'revenue_growth', 'order_growth', 'customer_growth',
        'completion_rate', 'cancellation_rate', 'return_rate',
        'top_products', 'top_categories', 'revenue_by_source', 'revenue_by_payment',
        'created_at', 'updated_at',
    ]
    
    @display(description='Period')
    def period_display(self, obj):
        return format_html(
            '<span style="font-weight: 600;">{}</span>',
            obj.period_label
        )
    
    @display(description='Revenue')
    def revenue_display(self, obj):
        return format_html(
            '<span style="font-weight: 600; color: #22c55e;">₫{:,.0f}</span>',
            obj.total_revenue
        )
    
    @display(description='Orders')
    def orders_display(self, obj):
        return format_html('{:,}', obj.total_orders)
    
    @display(description='Customers')
    def customers_display(self, obj):
        return format_html(
            '{:,} <span style="color: #6b7280;">({:,} new)</span>',
            obj.total_customers, obj.new_customers
        )
    
    @display(description='Growth')
    def growth_display(self, obj):
        if obj.revenue_growth is None:
            return '-'
        color = '#22c55e' if obj.revenue_growth >= 0 else '#ef4444'
        arrow = '↑' if obj.revenue_growth >= 0 else '↓'
        return format_html(
            '<span style="color: {};">{} {:.1f}%</span>',
            color, arrow, abs(obj.revenue_growth)
        )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductAnalytics)
class ProductAnalyticsAdmin(ModelAdmin):
    """Admin for product performance analytics."""
    list_display = [
        'product_display', 'revenue_display', 'sales_display',
        'conversion_display', 'score_display', 'status_display',
    ]
    list_filter = ['trending_up', 'slow_mover']
    search_fields = ['product_name', 'product_id']
    ordering = ['-performance_score', '-total_revenue']
    
    readonly_fields = [
        'product_id', 'product_name', 'total_views', 'total_cart_adds', 'total_purchases',
        'total_quantity_sold', 'total_revenue', 'total_returns',
        'total_return_value', 'views_30d', 'cart_adds_30d',
        'purchases_30d', 'revenue_30d', 'view_to_cart_rate',
        'cart_to_purchase_rate', 'return_rate', 'performance_score',
        'trending_up', 'slow_mover', 'last_calculated_at',
    ]
    
    @display(description='Product')
    def product_display(self, obj):
        return obj.product_name or f'Product #{obj.product_id}'
    
    @display(description='Revenue')
    def revenue_display(self, obj):
        return format_html(
            '<div>₫{:,.0f}</div>'
            '<div style="color: #6b7280; font-size: 11px;">30d: ₫{:,.0f}</div>',
            obj.total_revenue, obj.revenue_30d
        )
    
    @display(description='Sales')
    def sales_display(self, obj):
        return format_html(
            '<div>{:,} units</div>'
            '<div style="color: #6b7280; font-size: 11px;">30d: {:,}</div>',
            obj.total_quantity_sold, obj.purchases_30d
        )
    
    @display(description='Conversion')
    def conversion_display(self, obj):
        return format_html(
            '<div>View→Cart: {:.1f}%</div>'
            '<div>Cart→Buy: {:.1f}%</div>',
            obj.view_to_cart_rate, obj.cart_to_purchase_rate
        )
    
    @display(description='Score')
    def score_display(self, obj):
        if obj.performance_score >= 70:
            color = '#22c55e'
        elif obj.performance_score >= 40:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 9999px; font-size: 12px; font-weight: 600;">{:.0f}</span>',
            color, obj.performance_score
        )
    
    @display(description='Status')
    def status_display(self, obj):
        badges = []
        if obj.trending_up:
            badges.append('<span style="background: #22c55e; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">↑ TRENDING</span>')
        if obj.slow_mover:
            badges.append('<span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">SLOW</span>')
        return format_html(' '.join(badges)) if badges else '-'
    
    def has_add_permission(self, request):
        return False


@admin.register(CustomerSegment)
class CustomerSegmentAdmin(ModelAdmin):
    """Admin for customer RFM segments."""
    list_display = [
        'customer_display', 'segment_display', 'rfm_display',
        'value_display', 'churn_display',
    ]
    list_filter = ['segment']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    ordering = ['-total_spent']
    raw_id_fields = ['user']
    
    readonly_fields = [
        'user', 'segment', 'recency_score', 'frequency_score',
        'monetary_score', 'days_since_last_order', 'total_orders',
        'total_spent', 'average_order_value', 'first_order_date',
        'last_order_date', 'customer_lifetime_days', 'churn_risk',
        'predicted_next_order_days',
    ]
    
    @display(description='Customer')
    def customer_display(self, obj):
        return format_html(
            '<div style="font-weight: 600;">{}</div>'
            '<div style="color: #6b7280; font-size: 11px;">{}</div>',
            obj.user.email, obj.user.full_name or '-'
        )
    
    @display(description='Segment')
    def segment_display(self, obj):
        colors = {
            'champions': '#22c55e',
            'loyal': '#3b82f6',
            'potential_loyalist': '#8b5cf6',
            'recent': '#06b6d4',
            'promising': '#10b981',
            'need_attention': '#f59e0b',
            'about_to_sleep': '#f97316',
            'at_risk': '#ef4444',
            'cant_lose': '#dc2626',
            'hibernating': '#6b7280',
            'lost': '#374151',
        }
        color = colors.get(obj.segment, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_segment_display()
        )
    
    @display(description='RFM')
    def rfm_display(self, obj):
        return format_html(
            '<span style="font-family: monospace; font-weight: 600;">{}{}{}</span>',
            obj.recency_score, obj.frequency_score, obj.monetary_score
        )
    
    @display(description='Value')
    def value_display(self, obj):
        return format_html(
            '<div>₫{:,.0f}</div>'
            '<div style="color: #6b7280; font-size: 11px;">{} orders</div>',
            obj.total_spent, obj.total_orders
        )
    
    @display(description='Churn Risk')
    def churn_display(self, obj):
        if obj.churn_risk >= 70:
            color = '#ef4444'
        elif obj.churn_risk >= 40:
            color = '#f59e0b'
        else:
            color = '#22c55e'
        
        return format_html(
            '<span style="color: {}; font-weight: 600;">{:.0f}%</span>',
            color, obj.churn_risk
        )
    
    def has_add_permission(self, request):
        return False


@admin.register(SalesFunnel)
class SalesFunnelAdmin(ModelAdmin):
    """Admin for sales funnel data."""
    list_display = [
        'date', 'carts_display', 'checkout_display',
        'payments_display', 'conversion_display',
    ]
    list_filter = ['date']
    date_hierarchy = 'date'
    ordering = ['-date']
    
    readonly_fields = [
        'date', 'visitors', 'product_views', 'add_to_carts',
        'cart_views', 'checkout_started', 'payment_initiated',
        'payment_completed', 'orders_completed', 'view_to_cart_rate',
        'cart_to_checkout_rate', 'checkout_to_payment_rate',
        'payment_success_rate', 'overall_conversion_rate',
        'cart_abandonment_rate', 'checkout_abandonment_rate',
        'payment_failure_rate',
    ]
    
    @display(description='Carts')
    def carts_display(self, obj):
        return format_html(
            '{:,} added → {:,} viewed',
            obj.add_to_carts, obj.cart_views
        )
    
    @display(description='Checkout')
    def checkout_display(self, obj):
        return format_html('{:,} started', obj.checkout_started)
    
    @display(description='Payments')
    def payments_display(self, obj):
        return format_html(
            '{:,} initiated → {:,} completed',
            obj.payment_initiated, obj.payment_completed
        )
    
    @display(description='Conversion')
    def conversion_display(self, obj):
        return format_html(
            '<span style="font-weight: 600; color: #22c55e;">{:.2f}%</span>',
            obj.overall_conversion_rate
        )
    
    def has_add_permission(self, request):
        return False


@admin.register(RevenueBreakdown)
class RevenueBreakdownAdmin(ModelAdmin):
    """Admin for revenue breakdowns."""
    list_display = [
        'date', 'breakdown_type', 'dimension_label',
        'revenue_display', 'orders_display', 'percentage_display',
    ]
    list_filter = ['breakdown_type', 'date']
    search_fields = ['dimension_label']
    ordering = ['-date', '-revenue']
    
    @display(description='Revenue')
    def revenue_display(self, obj):
        return format_html('₫{:,.0f}', obj.revenue)
    
    @display(description='Orders')
    def orders_display(self, obj):
        return format_html('{:,}', obj.order_count)
    
    @display(description='%')
    def percentage_display(self, obj):
        return format_html('{:.1f}%', obj.revenue_percentage)
    
    def has_add_permission(self, request):
        return False


@admin.register(TrafficSource)
class TrafficSourceAdmin(ModelAdmin):
    """Admin for traffic source analytics."""
    list_display = [
        'date', 'source_display', 'visitors_display',
        'orders_display', 'revenue_display', 'conversion_display',
    ]
    list_filter = ['source', 'date']
    search_fields = ['source']
    date_hierarchy = 'date'
    ordering = ['-date', '-revenue']
    
    readonly_fields = [
        'date', 'source', 'sessions', 'unique_visitors', 'page_views',
        'bounce_rate', 'avg_session_duration',
        'orders', 'revenue', 'conversion_rate',
    ]
    
    @display(description='Source')
    def source_display(self, obj):
        source_colors = {
            'organic': '#22c55e',
            'google': '#4285f4',
            'facebook': '#1877f2',
            'direct': '#6b7280',
            'referral': '#8b5cf6',
            'email': '#ef4444',
        }
        color = source_colors.get(obj.source.lower(), '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.source
        )
    
    @display(description='Visitors')
    def visitors_display(self, obj):
        return format_html('{:,}', obj.unique_visitors)
    
    @display(description='Orders')
    def orders_display(self, obj):
        return format_html('{:,}', obj.orders)
    
    @display(description='Revenue')
    def revenue_display(self, obj):
        return format_html('₫{:,.0f}', obj.revenue)
    
    @display(description='Conversion')
    def conversion_display(self, obj):
        color = '#22c55e' if obj.conversion_rate >= 3 else '#f59e0b' if obj.conversion_rate >= 1 else '#ef4444'
        return format_html(
            '<span style="color: {}; font-weight: 600;">{:.2f}%</span>',
            color, obj.conversion_rate
        )
    
    def has_add_permission(self, request):
        return False


@admin.register(AbandonedCartMetric)
class AbandonedCartMetricAdmin(ModelAdmin):
    """Admin for abandoned cart analytics."""
    list_display = [
        'date', 'abandoned_display', 'recovered_display',
        'value_display', 'recovery_display',
    ]
    list_filter = ['date']
    date_hierarchy = 'date'
    ordering = ['-date']
    
    readonly_fields = [
        'date', 'total_abandoned', 'total_recovered',
        'total_value_abandoned', 'total_value_recovered',
        'recovery_rate', 'value_recovery_rate',
        'abandonment_by_hour', 'top_abandoned_products',
        'avg_cart_value', 'avg_items_per_cart', 'avg_time_to_abandon',
    ]
    
    @display(description='Abandoned')
    def abandoned_display(self, obj):
        return format_html(
            '<span style="color: #ef4444; font-weight: 600;">{:,}</span>',
            obj.total_abandoned
        )
    
    @display(description='Recovered')
    def recovered_display(self, obj):
        return format_html(
            '<span style="color: #22c55e; font-weight: 600;">{:,}</span>',
            obj.total_recovered
        )
    
    @display(description='Value Lost')
    def value_display(self, obj):
        return format_html('₫{:,.0f}', obj.total_value_abandoned)
    
    @display(description='Recovery Rate')
    def recovery_display(self, obj):
        color = '#22c55e' if obj.recovery_rate >= 10 else '#f59e0b' if obj.recovery_rate >= 5 else '#ef4444'
        return format_html(
            '<span style="color: {}; font-weight: 600;">{:.1f}%</span>',
            color, obj.recovery_rate
        )
    
    def has_add_permission(self, request):
        return False
