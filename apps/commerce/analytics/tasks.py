"""Commerce Analytics - Celery Tasks.

Background tasks for automated analytics aggregation and data processing.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.commerce.orders.models import Order, OrderItem
from apps.commerce.cart.models import Cart
from apps.commerce.returns.models import ReturnRequest
from apps.store.catalog.models import Product
from apps.users.identity.models import User

from .models import (
    DailyMetric, MonthlyReport, ProductAnalytics,
    CustomerSegment, SalesFunnel, RevenueBreakdown,
    AbandonedCartMetric
)
from .services import (
    AnalyticsService, SalesAnalyticsService, ProductAnalyticsService,
    CustomerAnalyticsService, FunnelAnalyticsService, RevenueAnalyticsService
)

logger = logging.getLogger('apps.analytics.tasks')


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def aggregate_daily_metrics(self, target_date_str: str = None):
    """Aggregate all daily metrics for a specific date.
    
    Run daily at 00:30 via Celery Beat to compute previous day's metrics.
    
    Args:
        target_date_str: Date string in YYYY-MM-DD format. Defaults to yesterday.
    """
    try:
        if target_date_str:
            target_date = date.fromisoformat(target_date_str)
        else:
            target_date = timezone.now().date() - timedelta(days=1)
        
        logger.info(f"Starting daily metrics aggregation for {target_date}")
        
        # Get or create metric record
        metric, created = DailyMetric.objects.get_or_create(date=target_date)
        
        # Define day boundaries
        day_start = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.min.time())
        )
        day_end = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.max.time())
        )
        
        # === Order Metrics ===
        orders = Order.objects.filter(created_at__range=(day_start, day_end))
        
        order_stats = orders.aggregate(
            total=Count('id'),
            revenue=Coalesce(Sum('total'), Decimal('0')),
            gross=Coalesce(Sum('subtotal'), Decimal('0')),
            discount=Coalesce(Sum('discount') + Sum('coupon_discount'), Decimal('0')),
            shipping=Coalesce(Sum('shipping_fee'), Decimal('0')),
        )
        
        metric.total_orders = order_stats['total']
        metric.total_revenue = order_stats['revenue']
        metric.gross_revenue = order_stats['gross']
        metric.total_discount = order_stats['discount']
        metric.shipping_revenue = order_stats['shipping']
        
        # Status breakdown
        status_counts = orders.values('status').annotate(count=Count('id'))
        status_map = {s['status']: s['count'] for s in status_counts}
        
        metric.pending_orders = status_map.get('pending', 0)
        metric.confirmed_orders = status_map.get('confirmed', 0)
        metric.completed_orders = status_map.get('completed', 0) + status_map.get('delivered', 0)
        metric.cancelled_orders = status_map.get('cancelled', 0)
        metric.refunded_orders = status_map.get('refunded', 0)
        
        # === Customer Metrics ===
        unique_customers = orders.values('user').distinct().count()
        metric.unique_customers = unique_customers
        
        # New customers (first order ever was today)
        new_customers = 0
        customer_ids = orders.values_list('user_id', flat=True).distinct()
        for user_id in customer_ids:
            if user_id:
                first_order = Order.objects.filter(user_id=user_id).order_by('created_at').first()
                if first_order and first_order.created_at.date() == target_date:
                    new_customers += 1
        
        metric.new_customers = new_customers
        metric.returning_customers = max(0, unique_customers - new_customers)
        
        # === Product Metrics ===
        order_items = OrderItem.objects.filter(order__created_at__range=(day_start, day_end))
        item_stats = order_items.aggregate(
            total_items=Coalesce(Sum('quantity'), 0),
            unique_products=Count('product_id', distinct=True),
        )
        
        metric.total_items_sold = item_stats['total_items']
        metric.unique_products_sold = item_stats['unique_products']
        
        # === Cart Metrics ===
        carts = Cart.objects.filter(created_at__range=(day_start, day_end))
        metric.carts_created = carts.count()
        
        # Converted carts = carts that led to orders
        converted_users = orders.filter(user__isnull=False).values_list('user_id', flat=True)
        metric.carts_converted = Cart.objects.filter(
            user_id__in=converted_users,
            created_at__range=(day_start, day_end)
        ).count()
        
        metric.carts_abandoned = max(0, metric.carts_created - metric.carts_converted)
        
        # === Returns & Refunds ===
        returns = ReturnRequest.objects.filter(created_at__range=(day_start, day_end))
        refund_stats = returns.aggregate(
            count=Count('id'),
            amount=Coalesce(Sum('approved_refund'), Decimal('0')),
        )
        
        metric.return_requests = refund_stats['count']
        metric.total_refund_amount = refund_stats['amount']
        
        # === Calculated Metrics ===
        if metric.total_orders > 0:
            metric.average_order_value = metric.total_revenue / metric.total_orders
        
        if metric.carts_created > 0:
            metric.conversion_rate = (metric.carts_converted / metric.carts_created) * 100
        
        if metric.total_orders > 0:
            metric.cancellation_rate = (metric.cancelled_orders / metric.total_orders) * 100
            metric.return_rate = (metric.return_requests / metric.total_orders) * 100
        
        metric.save()
        
        logger.info(f"Daily metrics completed for {target_date}: "
                   f"Revenue={metric.total_revenue}, Orders={metric.total_orders}")
        
        # Trigger related tasks
        FunnelAnalyticsService.calculate_daily_funnel(target_date)
        RevenueAnalyticsService.calculate_daily_breakdown(target_date)
        
        return {
            'date': str(target_date),
            'revenue': str(metric.total_revenue),
            'orders': metric.total_orders,
            'status': 'success'
        }
        
    except Exception as e:
        logger.exception(f"Error aggregating daily metrics: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def generate_monthly_report(self, year: int = None, month: int = None):
    """Generate monthly business report.
    
    Run on 1st of each month at 01:00 for the previous month.
    
    Args:
        year: Target year. Defaults to previous month's year.
        month: Target month (1-12). Defaults to previous month.
    """
    try:
        if year is None or month is None:
            today = timezone.now().date()
            first_of_month = today.replace(day=1)
            last_month = first_of_month - timedelta(days=1)
            year = last_month.year
            month = last_month.month
        
        logger.info(f"Generating monthly report for {year}-{month:02d}")
        
        report, created = MonthlyReport.objects.get_or_create(year=year, month=month)
        
        # Aggregate from daily metrics
        daily_metrics = DailyMetric.objects.filter(
            date__year=year,
            date__month=month
        )
        
        daily_count = daily_metrics.count()
        
        aggregated = daily_metrics.aggregate(
            revenue=Coalesce(Sum('total_revenue'), Decimal('0')),
            orders=Coalesce(Sum('total_orders'), 0),
            completed=Coalesce(Sum('completed_orders'), 0),
            cancelled=Coalesce(Sum('cancelled_orders'), 0),
            refunded=Coalesce(Sum('refunded_orders'), 0),
            new_customers=Coalesce(Sum('new_customers'), 0),
            returning_customers=Coalesce(Sum('returning_customers'), 0),
            items=Coalesce(Sum('total_items_sold'), 0),
            refunds=Coalesce(Sum('total_refund_amount'), Decimal('0')),
        )
        
        report.total_revenue = aggregated['revenue']
        report.total_orders = aggregated['orders']
        report.completed_orders = aggregated['completed']
        report.cancelled_orders = aggregated['cancelled']
        report.refunded_orders = aggregated['refunded']
        report.new_customers = aggregated['new_customers']
        report.returning_customers = aggregated['returning_customers']
        report.total_customers = aggregated['new_customers'] + aggregated['returning_customers']
        report.total_items_sold = aggregated['items']
        report.total_refunds = aggregated['refunds']
        
        # Calculated averages
        if report.total_orders > 0:
            report.average_order_value = report.total_revenue / report.total_orders
        if daily_count > 0:
            report.average_daily_revenue = report.total_revenue / daily_count
            report.average_daily_orders = Decimal(report.total_orders) / daily_count
        
        # Rates
        if report.total_orders > 0:
            report.completion_rate = (report.completed_orders / report.total_orders) * 100
            report.cancellation_rate = (report.cancelled_orders / report.total_orders) * 100
            report.return_rate = (report.refunded_orders / report.total_orders) * 100
        
        # Growth calculations (vs previous month)
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        
        try:
            prev_report = MonthlyReport.objects.get(year=prev_year, month=prev_month)
            
            if prev_report.total_revenue > 0:
                report.revenue_growth = (
                    (report.total_revenue - prev_report.total_revenue) / 
                    prev_report.total_revenue
                ) * 100
            
            if prev_report.total_orders > 0:
                report.order_growth = (
                    (report.total_orders - prev_report.total_orders) / 
                    prev_report.total_orders
                ) * 100
            
            if prev_report.total_customers > 0:
                report.customer_growth = (
                    (report.total_customers - prev_report.total_customers) / 
                    prev_report.total_customers
                ) * 100
                
        except MonthlyReport.DoesNotExist:
            pass  # No previous report, growth metrics remain null
        
        # Top products for the month
        top_products = AnalyticsService.get_top_products(days=daily_count, limit=10)
        report.top_products = list(top_products)
        
        # Top categories
        top_categories = AnalyticsService.get_top_categories(days=daily_count, limit=10)
        report.top_categories = top_categories
        
        # Revenue by source
        source_breakdown = RevenueBreakdown.objects.filter(
            date__year=year,
            date__month=month,
            breakdown_type=RevenueBreakdown.BreakdownType.ORDER_SOURCE
        ).values('dimension_key').annotate(
            revenue=Sum('revenue')
        )
        report.revenue_by_source = {s['dimension_key']: float(s['revenue']) for s in source_breakdown}
        
        # Revenue by payment
        payment_breakdown = RevenueBreakdown.objects.filter(
            date__year=year,
            date__month=month,
            breakdown_type=RevenueBreakdown.BreakdownType.PAYMENT_METHOD
        ).values('dimension_key').annotate(
            revenue=Sum('revenue')
        )
        report.revenue_by_payment = {p['dimension_key']: float(p['revenue']) for p in payment_breakdown}
        
        report.save()
        
        logger.info(f"Monthly report completed for {year}-{month:02d}: "
                   f"Revenue={report.total_revenue}, Orders={report.total_orders}")
        
        return {
            'year': year,
            'month': month,
            'revenue': str(report.total_revenue),
            'orders': report.total_orders,
            'status': 'success'
        }
        
    except Exception as e:
        logger.exception(f"Error generating monthly report: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def refresh_product_analytics(self, batch_size: int = 100):
    """Refresh analytics for all products.
    
    Run every 4 hours to keep product performance data current.
    
    Args:
        batch_size: Number of products to process per batch.
    """
    try:
        logger.info("Starting product analytics refresh")
        
        # Get all active products
        products = Product.objects.filter(is_active=True).values_list('id', flat=True)
        
        updated_count = 0
        for product_id in products:
            try:
                ProductAnalyticsService.update_product_analytics(product_id)
                updated_count += 1
            except Exception as e:
                logger.warning(f"Error updating product {product_id}: {e}")
        
        logger.info(f"Product analytics refresh completed: {updated_count} products updated")
        
        return {
            'updated': updated_count,
            'status': 'success'
        }
        
    except Exception as e:
        logger.exception(f"Error refreshing product analytics: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def update_customer_segments(self):
    """Update RFM segments for all customers with orders.
    
    Run weekly on Sunday at 02:00 for customer segmentation refresh.
    """
    try:
        logger.info("Starting customer segment update")
        
        # Get all users with at least one order
        users_with_orders = User.objects.filter(
            orders__isnull=False
        ).distinct()
        
        updated_count = 0
        for user in users_with_orders:
            try:
                CustomerAnalyticsService.update_customer_segment(user)
                updated_count += 1
            except Exception as e:
                logger.warning(f"Error updating segment for user {user.id}: {e}")
        
        logger.info(f"Customer segment update completed: {updated_count} customers updated")
        
        return {
            'updated': updated_count,
            'status': 'success'
        }
        
    except Exception as e:
        logger.exception(f"Error updating customer segments: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def calculate_abandoned_cart_metrics(self, target_date_str: str = None):
    """Calculate abandoned cart metrics for a specific date.
    
    Args:
        target_date_str: Date string in YYYY-MM-DD format. Defaults to yesterday.
    """
    try:
        if target_date_str:
            target_date = date.fromisoformat(target_date_str)
        else:
            target_date = timezone.now().date() - timedelta(days=1)
        
        logger.info(f"Calculating abandoned cart metrics for {target_date}")
        
        metric, _ = AbandonedCartMetric.objects.get_or_create(date=target_date)
        
        # Define day boundaries
        day_start = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.min.time())
        )
        day_end = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.max.time())
        )
        
        # Get all carts from that day that have items
        carts = Cart.objects.filter(
            created_at__range=(day_start, day_end),
            items__isnull=False
        ).distinct()
        
        total_carts = carts.count()
        
        # Get carts that converted (user made an order)
        converted_user_ids = Order.objects.filter(
            created_at__range=(day_start, day_end),
            user__isnull=False
        ).values_list('user_id', flat=True)
        
        converted_carts = carts.filter(user_id__in=converted_user_ids).count()
        abandoned_carts = total_carts - converted_carts
        
        # Calculate values
        abandoned_cart_values = []
        abandoned_item_counts = []
        hourly_abandonment = {}
        top_products = {}
        
        for cart in carts.exclude(user_id__in=converted_user_ids):
            cart_total = cart.subtotal
            item_count = cart.total_items
            hour = cart.created_at.hour
            
            abandoned_cart_values.append(cart_total)
            abandoned_item_counts.append(item_count)
            
            # Track by hour
            hourly_abandonment[hour] = hourly_abandonment.get(hour, 0) + 1
            
            # Track abandoned products
            for item in cart.items.all():
                pid = str(item.product_id)
                if pid not in top_products:
                    top_products[pid] = {
                        'product_id': item.product_id,
                        'product_name': item.product.name if item.product else 'Unknown',
                        'count': 0
                    }
                top_products[pid]['count'] += 1
        
        # Update metric
        metric.total_abandoned = abandoned_carts
        metric.total_recovered = converted_carts
        
        if abandoned_cart_values:
            metric.total_value_abandoned = sum(abandoned_cart_values)
            metric.avg_cart_value = sum(abandoned_cart_values) / len(abandoned_cart_values)
        
        if abandoned_item_counts:
            metric.avg_items_per_cart = Decimal(sum(abandoned_item_counts) / len(abandoned_item_counts))
        
        if total_carts > 0:
            metric.recovery_rate = (converted_carts / total_carts) * 100
        
        metric.abandonment_by_hour = hourly_abandonment
        
        # Sort products by abandonment count
        sorted_products = sorted(
            top_products.values(),
            key=lambda x: x['count'],
            reverse=True
        )[:10]
        metric.top_abandoned_products = sorted_products
        
        metric.save()
        
        logger.info(f"Abandoned cart metrics completed for {target_date}: "
                   f"Abandoned={abandoned_carts}, Recovered={converted_carts}")
        
        return {
            'date': str(target_date),
            'abandoned': abandoned_carts,
            'recovered': converted_carts,
            'status': 'success'
        }
        
    except Exception as e:
        logger.exception(f"Error calculating abandoned cart metrics: {e}")
        raise self.retry(exc=e)


@shared_task
def clean_old_metrics(retention_days: int = 365):
    """Clean up old metric data beyond retention period.
    
    Run monthly to manage data growth.
    
    Args:
        retention_days: Number of days to retain daily metrics.
    """
    try:
        cutoff_date = timezone.now().date() - timedelta(days=retention_days)
        
        logger.info(f"Cleaning metrics older than {cutoff_date}")
        
        deleted_counts = {}
        
        # Clean daily metrics
        deleted, _ = DailyMetric.objects.filter(date__lt=cutoff_date).delete()
        deleted_counts['daily_metrics'] = deleted
        
        # Clean funnels
        deleted, _ = SalesFunnel.objects.filter(date__lt=cutoff_date).delete()
        deleted_counts['sales_funnels'] = deleted
        
        # Clean revenue breakdowns
        deleted, _ = RevenueBreakdown.objects.filter(date__lt=cutoff_date).delete()
        deleted_counts['revenue_breakdowns'] = deleted
        
        # Clean abandoned cart metrics
        deleted, _ = AbandonedCartMetric.objects.filter(date__lt=cutoff_date).delete()
        deleted_counts['abandoned_cart_metrics'] = deleted
        
        logger.info(f"Cleanup completed: {deleted_counts}")
        
        return {
            'cutoff_date': str(cutoff_date),
            'deleted': deleted_counts,
            'status': 'success'
        }
        
    except Exception as e:
        logger.exception(f"Error cleaning old metrics: {e}")
        return {'status': 'error', 'message': str(e)}


# === Utility Tasks for Manual Triggering ===

@shared_task
def recalculate_metrics_range(start_date_str: str, end_date_str: str):
    """Recalculate metrics for a date range.
    
    Useful for backfilling or correcting data.
    """
    start = date.fromisoformat(start_date_str)
    end = date.fromisoformat(end_date_str)
    
    current = start
    while current <= end:
        aggregate_daily_metrics.delay(str(current))
        current += timedelta(days=1)
    
    return {
        'scheduled': f"{start_date_str} to {end_date_str}",
        'status': 'scheduled'
    }
