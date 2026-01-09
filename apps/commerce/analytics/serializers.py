"""Commerce Analytics - DRF Serializers.

Serializers for analytics API endpoints.
"""
from rest_framework import serializers
from decimal import Decimal

from .models import (
    DailyMetric, MonthlyReport, ProductAnalytics,
    CustomerSegment, SalesFunnel, RevenueBreakdown,
    TrafficSource, AbandonedCartMetric
)


class DailyMetricSerializer(serializers.ModelSerializer):
    """Serializer for daily metrics."""
    net_revenue = serializers.DecimalField(
        max_digits=15, decimal_places=0, read_only=True
    )
    
    class Meta:
        model = DailyMetric
        fields = [
            'id', 'date',
            # Revenue
            'total_revenue', 'gross_revenue', 'total_discount',
            'shipping_revenue', 'net_revenue',
            # Orders
            'total_orders', 'pending_orders', 'confirmed_orders',
            'completed_orders', 'cancelled_orders', 'refunded_orders',
            # Customers
            'new_customers', 'returning_customers', 'unique_customers',
            # Products
            'total_items_sold', 'unique_products_sold',
            # Carts
            'carts_created', 'carts_converted', 'carts_abandoned',
            # Returns
            'return_requests', 'total_refund_amount',
            # Calculated
            'average_order_value', 'conversion_rate',
            'cancellation_rate', 'return_rate',
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class DailyMetricSummarySerializer(serializers.ModelSerializer):
    """Compact serializer for charts and trends."""
    
    class Meta:
        model = DailyMetric
        fields = [
            'date', 'total_revenue', 'total_orders',
            'average_order_value', 'conversion_rate',
        ]


class MonthlyReportSerializer(serializers.ModelSerializer):
    """Serializer for monthly reports."""
    period_label = serializers.CharField(read_only=True)
    
    class Meta:
        model = MonthlyReport
        fields = [
            'id', 'year', 'month', 'period_label',
            # Core metrics
            'total_revenue', 'total_orders', 'completed_orders',
            'cancelled_orders', 'refunded_orders',
            # Customers
            'total_customers', 'new_customers', 'returning_customers',
            # Products
            'total_items_sold', 'total_refunds',
            # Averages
            'average_order_value', 'average_daily_revenue', 'average_daily_orders',
            # Growth
            'revenue_growth', 'order_growth', 'customer_growth',
            # Rates
            'completion_rate', 'cancellation_rate', 'return_rate',
            # Top performance
            'top_products', 'top_categories',
            'revenue_by_source', 'revenue_by_payment',
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ProductAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for product analytics."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_image = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductAnalytics
        fields = [
            'id', 'product_id', 'product_name', 'product_sku', 'product_image',
            # Lifetime
            'total_views', 'total_cart_adds', 'total_purchases',
            'total_quantity_sold', 'total_revenue',
            # Returns
            'total_returns', 'total_return_value',
            # 30 days
            'views_30d', 'cart_adds_30d', 'purchases_30d', 'revenue_30d',
            # Rates
            'view_to_cart_rate', 'cart_to_purchase_rate', 'return_rate',
            # Score
            'performance_score', 'trending_up', 'slow_mover',
            # Timestamps
            'last_calculated_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
    
    def get_product_image(self, obj):
        if obj.product and obj.product.images.exists():
            return obj.product.images.first().image.url
        return None


class ProductAnalyticsSummarySerializer(serializers.ModelSerializer):
    """Compact product analytics for lists."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = ProductAnalytics
        fields = [
            'product_id', 'product_name',
            'total_revenue', 'revenue_30d',
            'performance_score', 'trending_up',
        ]


class CustomerSegmentSerializer(serializers.ModelSerializer):
    """Serializer for customer segments."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    segment_display = serializers.CharField(source='get_segment_display', read_only=True)
    rfm_score = serializers.CharField(read_only=True)
    
    class Meta:
        model = CustomerSegment
        fields = [
            'id', 'user_id', 'user_email', 'user_name',
            'segment', 'segment_display',
            # RFM
            'recency_score', 'frequency_score', 'monetary_score', 'rfm_score',
            # Raw metrics
            'days_since_last_order', 'total_orders',
            'total_spent', 'average_order_value',
            # Engagement
            'first_order_date', 'last_order_date', 'customer_lifetime_days',
            # Predictions
            'churn_risk', 'predicted_next_order_days',
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class CustomerSegmentSummarySerializer(serializers.ModelSerializer):
    """Compact customer segment for lists."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    segment_display = serializers.CharField(source='get_segment_display', read_only=True)
    
    class Meta:
        model = CustomerSegment
        fields = [
            'user_id', 'user_email', 'segment', 'segment_display',
            'total_spent', 'churn_risk',
        ]


class SalesFunnelSerializer(serializers.ModelSerializer):
    """Serializer for sales funnel data."""
    
    class Meta:
        model = SalesFunnel
        fields = [
            'id', 'date',
            # Stages
            'visitors', 'product_views', 'add_to_carts', 'cart_views',
            'checkout_started', 'payment_initiated',
            'payment_completed', 'orders_completed',
            # Rates
            'view_to_cart_rate', 'cart_to_checkout_rate',
            'checkout_to_payment_rate', 'payment_success_rate',
            'overall_conversion_rate',
            # Drop-offs
            'cart_abandonment_rate', 'checkout_abandonment_rate',
            'payment_failure_rate',
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class RevenueBreakdownSerializer(serializers.ModelSerializer):
    """Serializer for revenue breakdowns."""
    breakdown_type_display = serializers.CharField(
        source='get_breakdown_type_display', read_only=True
    )
    
    class Meta:
        model = RevenueBreakdown
        fields = [
            'id', 'date', 'breakdown_type', 'breakdown_type_display',
            'dimension_key', 'dimension_label',
            'revenue', 'order_count', 'item_count',
            'unique_customers', 'revenue_percentage',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class TrafficSourceSerializer(serializers.ModelSerializer):
    """Serializer for traffic source data."""
    
    class Meta:
        model = TrafficSource
        fields = [
            'id', 'date', 'source',
            # Traffic
            'sessions', 'unique_visitors', 'page_views',
            # Conversion
            'orders', 'revenue', 'conversion_rate',
            # Engagement
            'avg_session_duration', 'bounce_rate',
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class AbandonedCartMetricSerializer(serializers.ModelSerializer):
    """Serializer for abandoned cart metrics."""
    
    class Meta:
        model = AbandonedCartMetric
        fields = [
            'id', 'date',
            # Volume
            'total_abandoned', 'total_recovered',
            'total_value_abandoned', 'total_value_recovered',
            # Rates
            'recovery_rate', 'value_recovery_rate',
            # Patterns
            'abandonment_by_hour', 'top_abandoned_products',
            # Averages
            'avg_cart_value', 'avg_items_per_cart', 'avg_time_to_abandon',
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


# === Dashboard Summary Serializers ===

class DashboardKPISerializer(serializers.Serializer):
    """Serializer for dashboard KPI summary."""
    
    period = serializers.DictField()
    revenue = serializers.DictField()
    orders = serializers.DictField()
    customers = serializers.DictField()
    average_order_value = serializers.DecimalField(max_digits=12, decimal_places=0)
    items_sold = serializers.IntegerField()


class ChartDataPointSerializer(serializers.Serializer):
    """Generic chart data point."""
    date = serializers.DateField()
    value = serializers.DecimalField(max_digits=15, decimal_places=2)
    label = serializers.CharField(required=False)


class SegmentDistributionSerializer(serializers.Serializer):
    """Customer segment distribution."""
    segment = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
