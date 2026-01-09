"""Commerce Analytics - Advanced Analytics Models.

Production-ready analytics data models for comprehensive e-commerce insights.
Tracks all orders (including pending) for complete funnel analysis.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.common.core.models import TimeStampedModel


class DailyMetric(TimeStampedModel):
    """Daily aggregated KPIs for the e-commerce platform.
    
    Generated automatically by Celery task at end of each day.
    Provides core metrics for dashboard and trend analysis.
    """
    date = models.DateField(unique=True, db_index=True, verbose_name='Date')
    
    # Revenue Metrics
    total_revenue = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name='Total Revenue'
    )
    gross_revenue = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name='Gross Revenue',
        help_text='Revenue before discounts'
    )
    total_discount = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name='Total Discounts'
    )
    shipping_revenue = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Shipping Revenue'
    )
    
    # Order Metrics
    total_orders = models.PositiveIntegerField(default=0, verbose_name='Total Orders')
    pending_orders = models.PositiveIntegerField(default=0, verbose_name='Pending Orders')
    confirmed_orders = models.PositiveIntegerField(default=0, verbose_name='Confirmed Orders')
    completed_orders = models.PositiveIntegerField(default=0, verbose_name='Completed Orders')
    cancelled_orders = models.PositiveIntegerField(default=0, verbose_name='Cancelled Orders')
    refunded_orders = models.PositiveIntegerField(default=0, verbose_name='Refunded Orders')
    
    # Customer Metrics
    new_customers = models.PositiveIntegerField(default=0, verbose_name='New Customers')
    returning_customers = models.PositiveIntegerField(default=0, verbose_name='Returning Customers')
    unique_customers = models.PositiveIntegerField(default=0, verbose_name='Unique Customers')
    
    # Product Metrics
    total_items_sold = models.PositiveIntegerField(default=0, verbose_name='Items Sold')
    unique_products_sold = models.PositiveIntegerField(default=0, verbose_name='Unique Products')
    
    # Cart Metrics
    carts_created = models.PositiveIntegerField(default=0, verbose_name='Carts Created')
    carts_converted = models.PositiveIntegerField(default=0, verbose_name='Carts Converted')
    carts_abandoned = models.PositiveIntegerField(default=0, verbose_name='Carts Abandoned')
    
    # Returns & Refunds
    return_requests = models.PositiveIntegerField(default=0, verbose_name='Return Requests')
    total_refund_amount = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name='Total Refunds'
    )
    
    # Calculated Metrics (stored for performance)
    average_order_value = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Avg Order Value'
    )
    conversion_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Conversion Rate %'
    )
    cancellation_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Cancellation Rate %'
    )
    return_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Return Rate %'
    )
    
    class Meta:
        verbose_name = 'Daily Metric'
        verbose_name_plural = 'Daily Metrics'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['date', 'total_revenue']),
        ]
    
    def __str__(self):
        return f"Metrics for {self.date}"
    
    @property
    def net_revenue(self):
        """Revenue after refunds."""
        return self.total_revenue - self.total_refund_amount
    
    @classmethod
    def get_or_create_for_date(cls, date):
        """Get or create metrics for a specific date."""
        metric, _ = cls.objects.get_or_create(date=date)
        return metric


class MonthlyReport(TimeStampedModel):
    """Monthly business summary with trend analysis.
    
    Aggregates daily metrics and provides month-over-month comparisons.
    """
    year = models.PositiveIntegerField(verbose_name='Year')
    month = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name='Month'
    )
    
    # Core Metrics (Aggregated)
    total_revenue = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name='Total Revenue')
    total_orders = models.PositiveIntegerField(default=0, verbose_name='Total Orders')
    completed_orders = models.PositiveIntegerField(default=0, verbose_name='Completed Orders')
    cancelled_orders = models.PositiveIntegerField(default=0, verbose_name='Cancelled Orders')
    refunded_orders = models.PositiveIntegerField(default=0, verbose_name='Refunded Orders')
    
    total_customers = models.PositiveIntegerField(default=0, verbose_name='Total Customers')
    new_customers = models.PositiveIntegerField(default=0, verbose_name='New Customers')
    returning_customers = models.PositiveIntegerField(default=0, verbose_name='Returning Customers')
    
    total_items_sold = models.PositiveIntegerField(default=0, verbose_name='Items Sold')
    total_refunds = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Total Refunds')
    
    # Calculated Metrics
    average_order_value = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Avg Order Value')
    average_daily_revenue = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Avg Daily Revenue')
    average_daily_orders = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Avg Daily Orders')
    
    # Growth Metrics (vs previous month)
    revenue_growth = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Revenue Growth %'
    )
    order_growth = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Order Growth %'
    )
    customer_growth = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Customer Growth %'
    )
    
    # Rates
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Completion Rate %')
    cancellation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Cancellation Rate %')
    return_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Return Rate %')
    
    # Top Performance (JSON for flexibility)
    top_products = models.JSONField(default=list, blank=True, verbose_name='Top Products')
    top_categories = models.JSONField(default=list, blank=True, verbose_name='Top Categories')
    revenue_by_source = models.JSONField(default=dict, blank=True, verbose_name='Revenue by Source')
    revenue_by_payment = models.JSONField(default=dict, blank=True, verbose_name='Revenue by Payment')
    
    class Meta:
        verbose_name = 'Monthly Report'
        verbose_name_plural = 'Monthly Reports'
        ordering = ['-year', '-month']
        unique_together = ['year', 'month']
        indexes = [
            models.Index(fields=['-year', '-month']),
        ]
    
    def __str__(self):
        return f"Report {self.year}-{self.month:02d}"
    
    @property
    def period_label(self):
        """Human-readable period label."""
        from calendar import month_name
        return f"{month_name[self.month]} {self.year}"


class ProductAnalytics(TimeStampedModel):
    """Product-level performance analytics.
    
    Tracks sales, views, conversions per product for optimization.
    Note: Uses product_id (IntegerField) instead of ForeignKey to avoid
    migration dependencies on catalog app. Link products at query time.
    """
    # Using IntegerField instead of ForeignKey to avoid migration dependency
    product_id = models.PositiveIntegerField(
        unique=True,
        db_index=True,
        verbose_name='Product ID'
    )
    product_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Product Name',
        help_text='Denormalized for display purposes'
    )
    
    # Lifetime Metrics
    total_views = models.PositiveIntegerField(default=0, verbose_name='Total Views')
    total_cart_adds = models.PositiveIntegerField(default=0, verbose_name='Add to Cart')
    total_purchases = models.PositiveIntegerField(default=0, verbose_name='Purchases')
    total_quantity_sold = models.PositiveIntegerField(default=0, verbose_name='Qty Sold')
    total_revenue = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Total Revenue')
    
    # Returns
    total_returns = models.PositiveIntegerField(default=0, verbose_name='Returns')
    total_return_value = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Return Value')
    
    # Last 30 Days (Rolling)
    views_30d = models.PositiveIntegerField(default=0, verbose_name='Views (30d)')
    cart_adds_30d = models.PositiveIntegerField(default=0, verbose_name='Cart Adds (30d)')
    purchases_30d = models.PositiveIntegerField(default=0, verbose_name='Purchases (30d)')
    revenue_30d = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Revenue (30d)')
    
    # Calculated Rates
    view_to_cart_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='View-to-Cart %'
    )
    cart_to_purchase_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Cart-to-Purchase %'
    )
    return_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Return Rate %'
    )
    
    # Performance Score (0-100)
    performance_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Performance Score'
    )
    
    # Trend Indicators
    trending_up = models.BooleanField(default=False, verbose_name='Trending Up')
    slow_mover = models.BooleanField(default=False, verbose_name='Slow Mover')
    
    last_calculated_at = models.DateTimeField(auto_now=True, verbose_name='Last Calculated')
    
    class Meta:
        verbose_name = 'Product Analytics'
        verbose_name_plural = 'Product Analytics'
        ordering = ['-total_revenue']
        indexes = [
            models.Index(fields=['-total_revenue']),
            models.Index(fields=['-performance_score']),
            models.Index(fields=['trending_up', '-revenue_30d']),
        ]
    
    def __str__(self):
        return f"Analytics: {self.product_name or f'Product #{self.product_id}'}"
    
    def calculate_rates(self):
        """Recalculate conversion rates."""
        if self.total_views > 0:
            self.view_to_cart_rate = (self.total_cart_adds / self.total_views) * 100
        if self.total_cart_adds > 0:
            self.cart_to_purchase_rate = (self.total_purchases / self.total_cart_adds) * 100
        if self.total_purchases > 0:
            self.return_rate = (self.total_returns / self.total_purchases) * 100


class CustomerSegment(TimeStampedModel):
    """Customer RFM (Recency, Frequency, Monetary) Segmentation.
    
    Categorizes customers for targeted marketing and retention.
    """
    class SegmentType(models.TextChoices):
        CHAMPIONS = 'champions', 'Champions'
        LOYAL = 'loyal', 'Loyal Customers'
        POTENTIAL_LOYALIST = 'potential_loyalist', 'Potential Loyalists'
        RECENT = 'recent', 'Recent Customers'
        PROMISING = 'promising', 'Promising'
        NEED_ATTENTION = 'need_attention', 'Need Attention'
        ABOUT_TO_SLEEP = 'about_to_sleep', 'About to Sleep'
        AT_RISK = 'at_risk', 'At Risk'
        CANT_LOSE = 'cant_lose', "Can't Lose Them"
        HIBERNATING = 'hibernating', 'Hibernating'
        LOST = 'lost', 'Lost'
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_segment',
        verbose_name='Customer'
    )
    
    segment = models.CharField(
        max_length=30,
        choices=SegmentType.choices,
        default=SegmentType.RECENT,
        db_index=True,
        verbose_name='Segment'
    )
    
    # RFM Scores (1-5)
    recency_score = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Recency Score'
    )
    frequency_score = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Frequency Score'
    )
    monetary_score = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Monetary Score'
    )
    
    # Raw Metrics
    days_since_last_order = models.PositiveIntegerField(default=0, verbose_name='Days Since Last Order')
    total_orders = models.PositiveIntegerField(default=0, verbose_name='Total Orders')
    total_spent = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Total Spent')
    average_order_value = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Avg Order Value')
    
    # Engagement
    first_order_date = models.DateField(null=True, blank=True, verbose_name='First Order')
    last_order_date = models.DateField(null=True, blank=True, verbose_name='Last Order')
    customer_lifetime_days = models.PositiveIntegerField(default=0, verbose_name='Customer Lifetime (days)')
    
    # Predictions
    churn_risk = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Churn Risk %'
    )
    predicted_next_order_days = models.PositiveIntegerField(null=True, blank=True, verbose_name='Predicted Next Order (days)')
    
    class Meta:
        verbose_name = 'Customer Segment'
        verbose_name_plural = 'Customer Segments'
        ordering = ['-total_spent']
        indexes = [
            models.Index(fields=['segment']),
            models.Index(fields=['-total_spent']),
            models.Index(fields=['churn_risk']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_segment_display()}"
    
    @property
    def rfm_score(self):
        """Combined RFM score string."""
        return f"{self.recency_score}{self.frequency_score}{self.monetary_score}"


class SalesFunnel(TimeStampedModel):
    """Daily conversion funnel tracking.
    
    Tracks customer journey: Visit → Cart → Checkout → Payment → Complete
    """
    date = models.DateField(unique=True, db_index=True, verbose_name='Date')
    
    # Funnel Stages
    visitors = models.PositiveIntegerField(default=0, verbose_name='Visitors')
    product_views = models.PositiveIntegerField(default=0, verbose_name='Product Views')
    add_to_carts = models.PositiveIntegerField(default=0, verbose_name='Add to Cart')
    cart_views = models.PositiveIntegerField(default=0, verbose_name='Cart Views')
    checkout_started = models.PositiveIntegerField(default=0, verbose_name='Checkout Started')
    payment_initiated = models.PositiveIntegerField(default=0, verbose_name='Payment Initiated')
    payment_completed = models.PositiveIntegerField(default=0, verbose_name='Payment Completed')
    orders_completed = models.PositiveIntegerField(default=0, verbose_name='Orders Completed')
    
    # Calculated Conversion Rates
    view_to_cart_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='View→Cart %')
    cart_to_checkout_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Cart→Checkout %')
    checkout_to_payment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Checkout→Payment %')
    payment_success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Payment Success %')
    overall_conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Overall Conversion %')
    
    # Drop-off Points
    cart_abandonment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Cart Abandonment %')
    checkout_abandonment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Checkout Abandonment %')
    payment_failure_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Payment Failure %')
    
    class Meta:
        verbose_name = 'Sales Funnel'
        verbose_name_plural = 'Sales Funnels'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date']),
        ]
    
    def __str__(self):
        return f"Funnel {self.date}"
    
    def calculate_rates(self):
        """Calculate all conversion rates."""
        if self.product_views > 0:
            self.view_to_cart_rate = (self.add_to_carts / self.product_views) * 100
        if self.add_to_carts > 0:
            self.cart_to_checkout_rate = (self.checkout_started / self.add_to_carts) * 100
            self.cart_abandonment_rate = ((self.add_to_carts - self.checkout_started) / self.add_to_carts) * 100
        if self.checkout_started > 0:
            self.checkout_to_payment_rate = (self.payment_initiated / self.checkout_started) * 100
            self.checkout_abandonment_rate = ((self.checkout_started - self.payment_initiated) / self.checkout_started) * 100
        if self.payment_initiated > 0:
            self.payment_success_rate = (self.payment_completed / self.payment_initiated) * 100
            self.payment_failure_rate = ((self.payment_initiated - self.payment_completed) / self.payment_initiated) * 100
        if self.visitors > 0:
            self.overall_conversion_rate = (self.orders_completed / self.visitors) * 100


class RevenueBreakdown(TimeStampedModel):
    """Revenue breakdown by various dimensions.
    
    Provides detailed revenue analysis for business decisions.
    """
    class BreakdownType(models.TextChoices):
        CATEGORY = 'category', 'By Category'
        BRAND = 'brand', 'By Brand'
        PAYMENT_METHOD = 'payment', 'By Payment Method'
        ORDER_SOURCE = 'source', 'By Order Source'
        REGION = 'region', 'By Region (City)'
        CUSTOMER_SEGMENT = 'segment', 'By Customer Segment'
    
    date = models.DateField(db_index=True, verbose_name='Date')
    breakdown_type = models.CharField(
        max_length=20,
        choices=BreakdownType.choices,
        db_index=True,
        verbose_name='Breakdown Type'
    )
    dimension_key = models.CharField(max_length=100, db_index=True, verbose_name='Dimension Key')
    dimension_label = models.CharField(max_length=200, verbose_name='Dimension Label')
    
    # Metrics
    revenue = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Revenue')
    order_count = models.PositiveIntegerField(default=0, verbose_name='Order Count')
    item_count = models.PositiveIntegerField(default=0, verbose_name='Item Count')
    unique_customers = models.PositiveIntegerField(default=0, verbose_name='Unique Customers')
    
    # Percentage of total (calculated)
    revenue_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Revenue %'
    )
    
    class Meta:
        verbose_name = 'Revenue Breakdown'
        verbose_name_plural = 'Revenue Breakdowns'
        ordering = ['-date', 'breakdown_type', '-revenue']
        unique_together = ['date', 'breakdown_type', 'dimension_key']
        indexes = [
            models.Index(fields=['-date', 'breakdown_type']),
            models.Index(fields=['breakdown_type', '-revenue']),
        ]
    
    def __str__(self):
        return f"{self.dimension_label}: {self.revenue:,.0f}"


class TrafficSource(TimeStampedModel):
    """Traffic source attribution analytics.
    
    Tracks where orders originate from (web, mobile, admin, API).
    """
    date = models.DateField(db_index=True, verbose_name='Date')
    source = models.CharField(max_length=50, db_index=True, verbose_name='Source')
    
    # Traffic Metrics
    sessions = models.PositiveIntegerField(default=0, verbose_name='Sessions')
    unique_visitors = models.PositiveIntegerField(default=0, verbose_name='Unique Visitors')
    page_views = models.PositiveIntegerField(default=0, verbose_name='Page Views')
    
    # Conversion Metrics
    orders = models.PositiveIntegerField(default=0, verbose_name='Orders')
    revenue = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Revenue')
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Conversion Rate %')
    
    # Engagement Metrics
    avg_session_duration = models.PositiveIntegerField(default=0, verbose_name='Avg Session (sec)')
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Bounce Rate %')
    
    class Meta:
        verbose_name = 'Traffic Source'
        verbose_name_plural = 'Traffic Sources'
        ordering = ['-date', '-revenue']
        unique_together = ['date', 'source']
        indexes = [
            models.Index(fields=['-date', 'source']),
        ]
    
    def __str__(self):
        return f"{self.source} - {self.date}"


class AbandonedCartMetric(TimeStampedModel):
    """Abandoned cart analysis metrics.
    
    Tracks cart abandonment patterns for recovery optimization.
    """
    date = models.DateField(unique=True, db_index=True, verbose_name='Date')
    
    # Volume
    total_abandoned = models.PositiveIntegerField(default=0, verbose_name='Total Abandoned')
    total_recovered = models.PositiveIntegerField(default=0, verbose_name='Recovered')
    total_value_abandoned = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Value Abandoned')
    total_value_recovered = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Value Recovered')
    
    # Recovery Rate
    recovery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Recovery Rate %')
    value_recovery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Value Recovery %')
    
    # Abandonment Timing (JSON breakdown by hour)
    abandonment_by_hour = models.JSONField(default=dict, blank=True, verbose_name='By Hour')
    
    # Top Abandoned Products (JSON list)
    top_abandoned_products = models.JSONField(default=list, blank=True, verbose_name='Top Abandoned Products')
    
    # Average metrics
    avg_cart_value = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Avg Cart Value')
    avg_items_per_cart = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Avg Items/Cart')
    avg_time_to_abandon = models.PositiveIntegerField(default=0, verbose_name='Avg Time to Abandon (min)')
    
    class Meta:
        verbose_name = 'Abandoned Cart Metric'
        verbose_name_plural = 'Abandoned Cart Metrics'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date']),
        ]
    
    def __str__(self):
        return f"Abandoned Carts {self.date}"
