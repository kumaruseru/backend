"""Commerce Analytics - Application Services.

Production-ready analytics service layer providing comprehensive
business intelligence for the e-commerce platform.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import date, datetime, timedelta
from collections import defaultdict

from django.db import transaction, models
from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from django.utils import timezone
from django.conf import settings

from apps.commerce.orders.models import Order, OrderItem
from apps.commerce.cart.models import Cart, CartItem
from apps.commerce.returns.models import ReturnRequest
from apps.commerce.shipping.models import Shipment
from apps.store.catalog.models import Product, Category
from apps.users.identity.models import User

from .models import (
    DailyMetric, MonthlyReport, ProductAnalytics,
    CustomerSegment, SalesFunnel, RevenueBreakdown,
    TrafficSource, AbandonedCartMetric
)

logger = logging.getLogger('apps.analytics')


class AnalyticsService:
    """Core analytics engine for computing and aggregating metrics."""
    
    @staticmethod
    def get_date_range(days: int = 30) -> Tuple[date, date]:
        """Get date range for analytics queries."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)
        return start_date, end_date
    
    @classmethod
    def get_dashboard_summary(cls, days: int = 30) -> Dict[str, Any]:
        """Get main dashboard KPIs for the specified period."""
        start_date, end_date = cls.get_date_range(days)
        
        # Get current period metrics
        current_metrics = DailyMetric.objects.filter(
            date__range=(start_date, end_date)
        ).aggregate(
            total_revenue=Coalesce(Sum('total_revenue'), Decimal('0')),
            total_orders=Coalesce(Sum('total_orders'), 0),
            completed_orders=Coalesce(Sum('completed_orders'), 0),
            cancelled_orders=Coalesce(Sum('cancelled_orders'), 0),
            new_customers=Coalesce(Sum('new_customers'), 0),
            total_items_sold=Coalesce(Sum('total_items_sold'), 0),
            total_refunds=Coalesce(Sum('total_refund_amount'), Decimal('0')),
        )
        
        # Calculate previous period for comparison
        prev_start = start_date - timedelta(days=days)
        prev_end = start_date - timedelta(days=1)
        
        prev_metrics = DailyMetric.objects.filter(
            date__range=(prev_start, prev_end)
        ).aggregate(
            total_revenue=Coalesce(Sum('total_revenue'), Decimal('0')),
            total_orders=Coalesce(Sum('total_orders'), 0),
            new_customers=Coalesce(Sum('new_customers'), 0),
        )
        
        # Calculate growth percentages
        def calc_growth(current, previous):
            if previous and previous > 0:
                return round(((current - previous) / previous) * 100, 2)
            return None
        
        # Average order value
        aov = Decimal('0')
        if current_metrics['total_orders'] > 0:
            aov = current_metrics['total_revenue'] / current_metrics['total_orders']
        
        return {
            'period': {'start': start_date, 'end': end_date, 'days': days},
            'revenue': {
                'total': current_metrics['total_revenue'],
                'net': current_metrics['total_revenue'] - current_metrics['total_refunds'],
                'growth': calc_growth(
                    current_metrics['total_revenue'],
                    prev_metrics['total_revenue']
                ),
            },
            'orders': {
                'total': current_metrics['total_orders'],
                'completed': current_metrics['completed_orders'],
                'cancelled': current_metrics['cancelled_orders'],
                'growth': calc_growth(
                    current_metrics['total_orders'],
                    prev_metrics['total_orders']
                ),
            },
            'customers': {
                'new': current_metrics['new_customers'],
                'growth': calc_growth(
                    current_metrics['new_customers'],
                    prev_metrics['new_customers']
                ),
            },
            'average_order_value': aov,
            'items_sold': current_metrics['total_items_sold'],
        }
    
    @classmethod
    def get_revenue_chart_data(cls, days: int = 30) -> List[Dict]:
        """Get daily revenue data for charts."""
        start_date, end_date = cls.get_date_range(days)
        
        metrics = DailyMetric.objects.filter(
            date__range=(start_date, end_date)
        ).values('date').annotate(
            revenue=Sum('total_revenue'),
            orders=Sum('total_orders'),
        ).order_by('date')
        
        return list(metrics)
    
    @classmethod
    def get_orders_by_status(cls, days: int = 30) -> Dict[str, int]:
        """Get order count breakdown by status."""
        start_date, _ = cls.get_date_range(days)
        
        orders = Order.objects.filter(
            created_at__date__gte=start_date
        ).values('status').annotate(
            count=Count('id')
        )
        
        return {item['status']: item['count'] for item in orders}
    
    @classmethod
    def get_top_products(cls, days: int = 30, limit: int = 10) -> List[Dict]:
        """Get top selling products by revenue."""
        start_date, _ = cls.get_date_range(days)
        
        top_products = OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__status__in=['completed', 'delivered', 'shipping']
        ).values(
            'product_id', 'product_name', 'product_sku'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('unit_price') * F('quantity')),
            order_count=Count('order_id', distinct=True),
        ).order_by('-total_revenue')[:limit]
        
        return list(top_products)
    
    @classmethod
    def get_top_categories(cls, days: int = 30, limit: int = 10) -> List[Dict]:
        """Get top categories by revenue."""
        start_date, _ = cls.get_date_range(days)
        
        # Get order items with their product categories
        order_items = OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__status__in=['completed', 'delivered', 'shipping']
        ).select_related('product__category')
        
        category_revenue = defaultdict(lambda: {'revenue': Decimal('0'), 'orders': 0, 'items': 0})
        
        for item in order_items:
            if item.product and item.product.category:
                cat = item.product.category
                category_revenue[cat.name]['revenue'] += item.subtotal
                category_revenue[cat.name]['orders'] += 1
                category_revenue[cat.name]['items'] += item.quantity
        
        sorted_cats = sorted(
            category_revenue.items(),
            key=lambda x: x[1]['revenue'],
            reverse=True
        )[:limit]
        
        return [{'category': k, **v} for k, v in sorted_cats]


class SalesAnalyticsService:
    """Sales metrics, trends, and revenue analysis."""
    
    @classmethod
    def get_sales_summary(cls, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get comprehensive sales summary for date range."""
        orders = Order.objects.filter(
            created_at__date__range=(start_date, end_date)
        )
        
        summary = orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Coalesce(Sum('total'), Decimal('0')),
            gross_revenue=Coalesce(Sum('subtotal'), Decimal('0')),
            total_discount=Coalesce(Sum('discount') + Sum('coupon_discount'), Decimal('0')),
            shipping_revenue=Coalesce(Sum('shipping_fee'), Decimal('0')),
            avg_order_value=Coalesce(Avg('total'), Decimal('0')),
        )
        
        # Status breakdown
        status_counts = orders.values('status').annotate(
            count=Count('id')
        )
        summary['by_status'] = {s['status']: s['count'] for s in status_counts}
        
        # Payment method breakdown
        payment_counts = orders.values('payment_method').annotate(
            count=Count('id'),
            revenue=Sum('total')
        )
        summary['by_payment'] = {
            p['payment_method']: {'count': p['count'], 'revenue': p['revenue']}
            for p in payment_counts
        }
        
        # Source breakdown
        source_counts = orders.values('source').annotate(
            count=Count('id'),
            revenue=Sum('total')
        )
        summary['by_source'] = {
            s['source']: {'count': s['count'], 'revenue': s['revenue']}
            for s in source_counts
        }
        
        return summary
    
    @classmethod
    def get_daily_sales_trend(cls, days: int = 30) -> List[Dict]:
        """Get daily sales trend data."""
        start_date = timezone.now().date() - timedelta(days=days - 1)
        
        daily_data = Order.objects.filter(
            created_at__date__gte=start_date
        ).annotate(
            order_date=TruncDate('created_at')
        ).values('order_date').annotate(
            orders=Count('id'),
            revenue=Coalesce(Sum('total'), Decimal('0')),
            items=Coalesce(Sum('items__quantity'), 0),
        ).order_by('order_date')
        
        return list(daily_data)
    
    @classmethod
    def get_hourly_distribution(cls, days: int = 7) -> Dict[int, Dict]:
        """Get order distribution by hour of day."""
        start_date = timezone.now() - timedelta(days=days)
        
        orders = Order.objects.filter(created_at__gte=start_date)
        
        hourly = defaultdict(lambda: {'orders': 0, 'revenue': Decimal('0')})
        
        for order in orders:
            hour = order.created_at.hour
            hourly[hour]['orders'] += 1
            hourly[hour]['revenue'] += order.total
        
        return dict(hourly)
    
    @classmethod
    def calculate_aov_trend(cls, days: int = 30) -> List[Dict]:
        """Calculate Average Order Value trend."""
        start_date = timezone.now().date() - timedelta(days=days - 1)
        
        aov_data = Order.objects.filter(
            created_at__date__gte=start_date,
            status__in=['completed', 'delivered', 'shipping', 'confirmed']
        ).annotate(
            order_date=TruncDate('created_at')
        ).values('order_date').annotate(
            aov=Avg('total'),
            order_count=Count('id'),
        ).order_by('order_date')
        
        return list(aov_data)


class ProductAnalyticsService:
    """Product performance insights and recommendations."""
    
    @classmethod
    def update_product_analytics(cls, product_id: int) -> ProductAnalytics:
        """Update analytics for a specific product."""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            logger.warning(f"Product {product_id} not found for analytics update")
            return None
        
        analytics, created = ProductAnalytics.objects.get_or_create(product=product)
        
        # Calculate lifetime metrics from order items
        order_data = OrderItem.objects.filter(product=product).aggregate(
            total_purchases=Count('id'),
            total_quantity=Coalesce(Sum('quantity'), 0),
            total_revenue=Coalesce(Sum(F('unit_price') * F('quantity')), Decimal('0')),
        )
        
        analytics.total_purchases = order_data['total_purchases']
        analytics.total_quantity_sold = order_data['total_quantity']
        analytics.total_revenue = order_data['total_revenue']
        
        # Calculate 30-day metrics
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_data = OrderItem.objects.filter(
            product=product,
            order__created_at__gte=thirty_days_ago
        ).aggregate(
            purchases=Count('id'),
            revenue=Coalesce(Sum(F('unit_price') * F('quantity')), Decimal('0')),
        )
        
        analytics.purchases_30d = recent_data['purchases']
        analytics.revenue_30d = recent_data['revenue']
        
        # Calculate returns
        return_data = ReturnRequest.objects.filter(
            items__order_item__product=product,
            status='completed'
        ).aggregate(
            total_returns=Count('id'),
            return_value=Coalesce(Sum('approved_refund'), Decimal('0')),
        )
        
        analytics.total_returns = return_data['total_returns'] or 0
        analytics.total_return_value = return_data['return_value'] or Decimal('0')
        
        # Calculate rates
        analytics.calculate_rates()
        
        # Determine trending status
        prev_30d_revenue = OrderItem.objects.filter(
            product=product,
            order__created_at__range=(
                timezone.now() - timedelta(days=60),
                timezone.now() - timedelta(days=30)
            )
        ).aggregate(
            revenue=Coalesce(Sum(F('unit_price') * F('quantity')), Decimal('0'))
        )['revenue']
        
        if prev_30d_revenue > 0:
            growth = ((analytics.revenue_30d - prev_30d_revenue) / prev_30d_revenue) * 100
            analytics.trending_up = growth > 10
            analytics.slow_mover = growth < -20
        else:
            analytics.trending_up = analytics.revenue_30d > 0
            analytics.slow_mover = analytics.revenue_30d == 0 and analytics.total_revenue > 0
        
        # Performance score calculation (simple algorithm)
        score = 50  # Base score
        if analytics.purchases_30d > 0:
            score += min(20, analytics.purchases_30d)
        if analytics.return_rate < 5:
            score += 15
        elif analytics.return_rate > 20:
            score -= 20
        if analytics.cart_to_purchase_rate > 50:
            score += 15
        analytics.performance_score = max(0, min(100, score))
        
        analytics.save()
        return analytics
    
    @classmethod
    def get_top_performers(cls, limit: int = 10) -> List[ProductAnalytics]:
        """Get top performing products."""
        return ProductAnalytics.objects.select_related('product').order_by(
            '-performance_score', '-revenue_30d'
        )[:limit]
    
    @classmethod
    def get_slow_movers(cls, limit: int = 10) -> List[ProductAnalytics]:
        """Get slow-moving products that need attention."""
        return ProductAnalytics.objects.filter(
            slow_mover=True
        ).select_related('product').order_by('revenue_30d')[:limit]
    
    @classmethod
    def get_trending_products(cls, limit: int = 10) -> List[ProductAnalytics]:
        """Get currently trending products."""
        return ProductAnalytics.objects.filter(
            trending_up=True
        ).select_related('product').order_by('-revenue_30d')[:limit]


class CustomerAnalyticsService:
    """Customer behavior analysis and RFM segmentation."""
    
    # RFM Segment mapping based on scores
    RFM_SEGMENTS = {
        (5, 5, 5): CustomerSegment.SegmentType.CHAMPIONS,
        (5, 5, 4): CustomerSegment.SegmentType.CHAMPIONS,
        (5, 4, 5): CustomerSegment.SegmentType.CHAMPIONS,
        (4, 5, 5): CustomerSegment.SegmentType.CHAMPIONS,
        (5, 4, 4): CustomerSegment.SegmentType.LOYAL,
        (4, 4, 5): CustomerSegment.SegmentType.LOYAL,
        (4, 5, 4): CustomerSegment.SegmentType.LOYAL,
        (4, 4, 4): CustomerSegment.SegmentType.LOYAL,
        (5, 3, 3): CustomerSegment.SegmentType.POTENTIAL_LOYALIST,
        (4, 3, 3): CustomerSegment.SegmentType.POTENTIAL_LOYALIST,
        (3, 3, 3): CustomerSegment.SegmentType.POTENTIAL_LOYALIST,
        (5, 1, 1): CustomerSegment.SegmentType.RECENT,
        (5, 2, 1): CustomerSegment.SegmentType.RECENT,
        (5, 1, 2): CustomerSegment.SegmentType.RECENT,
        (4, 1, 1): CustomerSegment.SegmentType.PROMISING,
        (3, 1, 1): CustomerSegment.SegmentType.PROMISING,
        (3, 2, 2): CustomerSegment.SegmentType.NEED_ATTENTION,
        (2, 3, 3): CustomerSegment.SegmentType.NEED_ATTENTION,
        (2, 2, 3): CustomerSegment.SegmentType.ABOUT_TO_SLEEP,
        (2, 2, 2): CustomerSegment.SegmentType.ABOUT_TO_SLEEP,
        (2, 3, 2): CustomerSegment.SegmentType.AT_RISK,
        (1, 3, 3): CustomerSegment.SegmentType.AT_RISK,
        (1, 4, 4): CustomerSegment.SegmentType.CANT_LOSE,
        (1, 5, 5): CustomerSegment.SegmentType.CANT_LOSE,
        (1, 2, 2): CustomerSegment.SegmentType.HIBERNATING,
        (1, 2, 1): CustomerSegment.SegmentType.HIBERNATING,
        (1, 1, 1): CustomerSegment.SegmentType.LOST,
        (1, 1, 2): CustomerSegment.SegmentType.LOST,
    }
    
    @classmethod
    def calculate_rfm_scores(cls, user) -> Tuple[int, int, int]:
        """Calculate RFM scores for a user."""
        orders = Order.objects.filter(
            user=user,
            status__in=['completed', 'delivered']
        )
        
        if not orders.exists():
            return (1, 1, 1)
        
        # Recency: Days since last order
        last_order = orders.order_by('-created_at').first()
        days_since = (timezone.now().date() - last_order.created_at.date()).days
        
        if days_since <= 7:
            recency = 5
        elif days_since <= 30:
            recency = 4
        elif days_since <= 90:
            recency = 3
        elif days_since <= 180:
            recency = 2
        else:
            recency = 1
        
        # Frequency: Total orders
        order_count = orders.count()
        
        if order_count >= 10:
            frequency = 5
        elif order_count >= 5:
            frequency = 4
        elif order_count >= 3:
            frequency = 3
        elif order_count >= 2:
            frequency = 2
        else:
            frequency = 1
        
        # Monetary: Total spent
        total_spent = orders.aggregate(total=Sum('total'))['total'] or 0
        
        if total_spent >= 10000000:  # 10M VND
            monetary = 5
        elif total_spent >= 5000000:
            monetary = 4
        elif total_spent >= 2000000:
            monetary = 3
        elif total_spent >= 500000:
            monetary = 2
        else:
            monetary = 1
        
        return (recency, frequency, monetary)
    
    @classmethod
    def get_segment_from_rfm(cls, rfm: Tuple[int, int, int]) -> str:
        """Determine customer segment from RFM scores."""
        # Direct match
        if rfm in cls.RFM_SEGMENTS:
            return cls.RFM_SEGMENTS[rfm]
        
        # Fallback logic based on score patterns
        r, f, m = rfm
        avg = (r + f + m) / 3
        
        if avg >= 4:
            return CustomerSegment.SegmentType.LOYAL
        elif r >= 4:
            return CustomerSegment.SegmentType.RECENT
        elif f >= 4 or m >= 4:
            return CustomerSegment.SegmentType.AT_RISK
        elif avg >= 2.5:
            return CustomerSegment.SegmentType.NEED_ATTENTION
        else:
            return CustomerSegment.SegmentType.HIBERNATING
    
    @classmethod
    def update_customer_segment(cls, user) -> CustomerSegment:
        """Update RFM segment for a customer."""
        segment, created = CustomerSegment.objects.get_or_create(user=user)
        
        # Get order statistics
        orders = Order.objects.filter(
            user=user,
            status__in=['completed', 'delivered', 'shipping']
        )
        
        if not orders.exists():
            segment.segment = CustomerSegment.SegmentType.RECENT
            segment.save()
            return segment
        
        order_stats = orders.aggregate(
            total=Count('id'),
            spent=Coalesce(Sum('total'), Decimal('0')),
            avg=Coalesce(Avg('total'), Decimal('0')),
        )
        
        first_order = orders.order_by('created_at').first()
        last_order = orders.order_by('-created_at').first()
        
        # Update raw metrics
        segment.total_orders = order_stats['total']
        segment.total_spent = order_stats['spent']
        segment.average_order_value = order_stats['avg']
        segment.first_order_date = first_order.created_at.date()
        segment.last_order_date = last_order.created_at.date()
        segment.days_since_last_order = (timezone.now().date() - segment.last_order_date).days
        segment.customer_lifetime_days = (timezone.now().date() - segment.first_order_date).days
        
        # Calculate RFM scores
        rfm = cls.calculate_rfm_scores(user)
        segment.recency_score, segment.frequency_score, segment.monetary_score = rfm
        
        # Determine segment
        segment.segment = cls.get_segment_from_rfm(rfm)
        
        # Calculate churn risk
        if segment.days_since_last_order > 180:
            segment.churn_risk = 90
        elif segment.days_since_last_order > 90:
            segment.churn_risk = 70
        elif segment.days_since_last_order > 60:
            segment.churn_risk = 50
        elif segment.days_since_last_order > 30:
            segment.churn_risk = 30
        else:
            segment.churn_risk = 10
        
        # Predict next order (simple average gap calculation)
        if segment.total_orders > 1:
            avg_gap = segment.customer_lifetime_days / (segment.total_orders - 1)
            segment.predicted_next_order_days = max(0, int(avg_gap - segment.days_since_last_order))
        
        segment.save()
        return segment
    
    @classmethod
    def get_segment_distribution(cls) -> Dict[str, int]:
        """Get customer count by segment."""
        distribution = CustomerSegment.objects.values('segment').annotate(
            count=Count('id')
        )
        return {d['segment']: d['count'] for d in distribution}
    
    @classmethod
    def get_high_value_customers(cls, limit: int = 20) -> List[CustomerSegment]:
        """Get highest value customers."""
        return CustomerSegment.objects.select_related('user').order_by(
            '-total_spent'
        )[:limit]
    
    @classmethod
    def get_at_risk_customers(cls, limit: int = 20) -> List[CustomerSegment]:
        """Get customers at risk of churning."""
        return CustomerSegment.objects.filter(
            segment__in=[
                CustomerSegment.SegmentType.AT_RISK,
                CustomerSegment.SegmentType.CANT_LOSE,
                CustomerSegment.SegmentType.ABOUT_TO_SLEEP,
            ]
        ).select_related('user').order_by('-total_spent')[:limit]


class FunnelAnalyticsService:
    """Conversion funnel tracking and analysis."""
    
    @classmethod
    def calculate_daily_funnel(cls, target_date: date) -> SalesFunnel:
        """Calculate funnel metrics for a specific day."""
        funnel, _ = SalesFunnel.objects.get_or_create(date=target_date)
        
        # Start and end of day
        day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(target_date, datetime.max.time()))
        
        # Cart metrics
        carts = Cart.objects.filter(
            created_at__range=(day_start, day_end)
        )
        funnel.add_to_carts = carts.count()
        
        # Checkout started = carts that have items and were active
        checkout_started = carts.filter(items__isnull=False).distinct().count()
        funnel.checkout_started = checkout_started
        
        # Orders created
        orders = Order.objects.filter(
            created_at__range=(day_start, day_end)
        )
        
        # Payment initiated = all orders (they're created when payment starts)
        funnel.payment_initiated = orders.count()
        
        # Payment completed = paid orders
        funnel.payment_completed = orders.filter(
            payment_status__in=['paid', 'partial_refund']
        ).count()
        
        # Orders completed
        funnel.orders_completed = orders.filter(
            status__in=['completed', 'delivered']
        ).count()
        
        # Calculate rates
        funnel.calculate_rates()
        funnel.save()
        
        return funnel
    
    @classmethod
    def get_funnel_trend(cls, days: int = 30) -> List[Dict]:
        """Get funnel metrics trend over time."""
        start_date = timezone.now().date() - timedelta(days=days - 1)
        
        funnels = SalesFunnel.objects.filter(
            date__gte=start_date
        ).values(
            'date', 'add_to_carts', 'checkout_started',
            'payment_initiated', 'payment_completed', 'orders_completed',
            'overall_conversion_rate'
        ).order_by('date')
        
        return list(funnels)
    
    @classmethod
    def get_drop_off_analysis(cls, days: int = 30) -> Dict[str, Any]:
        """Analyze where customers drop off in the funnel."""
        start_date = timezone.now().date() - timedelta(days=days - 1)
        
        totals = SalesFunnel.objects.filter(
            date__gte=start_date
        ).aggregate(
            add_to_carts=Sum('add_to_carts'),
            checkout_started=Sum('checkout_started'),
            payment_initiated=Sum('payment_initiated'),
            payment_completed=Sum('payment_completed'),
            orders_completed=Sum('orders_completed'),
        )
        
        stages = [
            ('Add to Cart', totals['add_to_carts'] or 0),
            ('Checkout Started', totals['checkout_started'] or 0),
            ('Payment Initiated', totals['payment_initiated'] or 0),
            ('Payment Completed', totals['payment_completed'] or 0),
            ('Order Completed', totals['orders_completed'] or 0),
        ]
        
        drop_offs = []
        for i in range(1, len(stages)):
            prev_name, prev_count = stages[i - 1]
            curr_name, curr_count = stages[i]
            
            if prev_count > 0:
                drop_rate = ((prev_count - curr_count) / prev_count) * 100
            else:
                drop_rate = 0
            
            drop_offs.append({
                'from_stage': prev_name,
                'to_stage': curr_name,
                'drop_count': prev_count - curr_count,
                'drop_rate': round(drop_rate, 2),
            })
        
        return {
            'stages': stages,
            'drop_offs': drop_offs,
        }


class RevenueAnalyticsService:
    """Revenue breakdown and profit analysis."""
    
    @classmethod
    def calculate_daily_breakdown(cls, target_date: date):
        """Calculate revenue breakdowns for a specific day."""
        day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(target_date, datetime.max.time()))
        
        orders = Order.objects.filter(
            created_at__range=(day_start, day_end),
            status__in=['completed', 'delivered', 'shipping', 'confirmed']
        )
        
        total_revenue = orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        # By Payment Method
        by_payment = orders.values('payment_method').annotate(
            revenue=Sum('total'),
            count=Count('id'),
        )
        
        for item in by_payment:
            RevenueBreakdown.objects.update_or_create(
                date=target_date,
                breakdown_type=RevenueBreakdown.BreakdownType.PAYMENT_METHOD,
                dimension_key=item['payment_method'],
                defaults={
                    'dimension_label': dict(Order.PaymentMethod.choices).get(
                        item['payment_method'], item['payment_method']
                    ),
                    'revenue': item['revenue'] or 0,
                    'order_count': item['count'],
                    'revenue_percentage': (
                        (item['revenue'] / total_revenue) * 100
                        if total_revenue > 0 else 0
                    ),
                }
            )
        
        # By Source
        by_source = orders.values('source').annotate(
            revenue=Sum('total'),
            count=Count('id'),
        )
        
        for item in by_source:
            RevenueBreakdown.objects.update_or_create(
                date=target_date,
                breakdown_type=RevenueBreakdown.BreakdownType.ORDER_SOURCE,
                dimension_key=item['source'],
                defaults={
                    'dimension_label': dict(Order.Source.choices).get(
                        item['source'], item['source']
                    ),
                    'revenue': item['revenue'] or 0,
                    'order_count': item['count'],
                    'revenue_percentage': (
                        (item['revenue'] / total_revenue) * 100
                        if total_revenue > 0 else 0
                    ),
                }
            )
        
        # By City (Region)
        by_city = orders.values('city').annotate(
            revenue=Sum('total'),
            count=Count('id'),
            unique_customers=Count('user', distinct=True),
        )
        
        for item in by_city:
            if item['city']:
                RevenueBreakdown.objects.update_or_create(
                    date=target_date,
                    breakdown_type=RevenueBreakdown.BreakdownType.REGION,
                    dimension_key=item['city'],
                    defaults={
                        'dimension_label': item['city'],
                        'revenue': item['revenue'] or 0,
                        'order_count': item['count'],
                        'unique_customers': item['unique_customers'],
                        'revenue_percentage': (
                            (item['revenue'] / total_revenue) * 100
                            if total_revenue > 0 else 0
                        ),
                    }
                )
    
    @classmethod
    def get_breakdown_summary(cls, breakdown_type: str, days: int = 30) -> List[Dict]:
        """Get revenue breakdown by type for the period."""
        start_date = timezone.now().date() - timedelta(days=days - 1)
        
        breakdown = RevenueBreakdown.objects.filter(
            date__gte=start_date,
            breakdown_type=breakdown_type
        ).values(
            'dimension_key', 'dimension_label'
        ).annotate(
            total_revenue=Sum('revenue'),
            total_orders=Sum('order_count'),
        ).order_by('-total_revenue')
        
        return list(breakdown)
    
    @classmethod
    def get_revenue_by_region(cls, days: int = 30) -> List[Dict]:
        """Get revenue distribution by region."""
        return cls.get_breakdown_summary(
            RevenueBreakdown.BreakdownType.REGION, days
        )
    
    @classmethod
    def get_revenue_by_payment_method(cls, days: int = 30) -> List[Dict]:
        """Get revenue distribution by payment method."""
        return cls.get_breakdown_summary(
            RevenueBreakdown.BreakdownType.PAYMENT_METHOD, days
        )
