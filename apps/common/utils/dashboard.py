"""Common Utils - Dashboard Callback for Django Unfold Admin.

This module provides the dashboard callback that populates the admin
dashboard with KPIs, quick links, and recent activity widgets.
"""
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta


def get_date_range(days=30):
    """Get start and end dates for the specified period."""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def get_order_stats():
    """Get order statistics for dashboard KPIs."""
    try:
        from apps.commerce.orders.models import Order
    except ImportError:
        return None

    start_date, end_date = get_date_range(30)
    start_date_prev, end_date_prev = get_date_range(60)
    end_date_prev = start_date

    # Current period stats
    current_orders = Order.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
    prev_orders = Order.objects.filter(created_at__gte=start_date_prev, created_at__lt=end_date_prev)

    current_revenue = current_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    prev_revenue = prev_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

    current_count = current_orders.count()
    prev_count = prev_orders.count()

    # Calculate percentage changes
    revenue_change = 0
    if prev_revenue > 0:
        revenue_change = round(((current_revenue - prev_revenue) / prev_revenue) * 100, 1)

    count_change = 0
    if prev_count > 0:
        count_change = round(((current_count - prev_count) / prev_count) * 100, 1)

    # Average order value
    aov = current_revenue / current_count if current_count > 0 else Decimal('0')

    # Order status breakdown
    pending_count = current_orders.filter(status='pending').count()
    processing_count = current_orders.filter(status='processing').count()
    shipping_count = current_orders.filter(status='shipping').count()
    completed_count = current_orders.filter(status='completed').count()

    return {
        'revenue': current_revenue,
        'revenue_change': revenue_change,
        'count': current_count,
        'count_change': count_change,
        'aov': aov,
        'pending': pending_count,
        'processing': processing_count,
        'shipping': shipping_count,
        'completed': completed_count,
    }


def get_user_stats():
    """Get user statistics for dashboard KPIs."""
    try:
        from apps.users.identity.models import User
    except ImportError:
        return None

    start_date, end_date = get_date_range(30)
    start_date_prev, end_date_prev = get_date_range(60)
    end_date_prev = start_date

    current_users = User.objects.filter(date_joined__gte=start_date, date_joined__lte=end_date).count()
    prev_users = User.objects.filter(date_joined__gte=start_date_prev, date_joined__lt=end_date_prev).count()

    total_users = User.objects.filter(is_active=True).count()

    user_change = 0
    if prev_users > 0:
        user_change = round(((current_users - prev_users) / prev_users) * 100, 1)

    return {
        'new_users': current_users,
        'user_change': user_change,
        'total_users': total_users,
    }


def get_product_stats():
    """Get product statistics for dashboard KPIs."""
    try:
        from apps.store.catalog.models import Product
        from apps.store.inventory.models import StockItem
    except ImportError:
        return None

    total_products = Product.objects.filter(is_active=True).count()
    low_stock = StockItem.objects.filter(
        quantity__lte=F('low_stock_threshold'),
        quantity__gt=0
    ).count()
    out_of_stock = StockItem.objects.filter(quantity=0).count()

    return {
        'total_products': total_products,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
    }


def get_recent_orders(limit=5):
    """Get recent orders for dashboard widget."""
    try:
        from apps.commerce.orders.models import Order
    except ImportError:
        return []

    orders = Order.objects.select_related('user').order_by('-created_at')[:limit]
    return [
        {
            'order_number': order.order_number,
            'customer': order.user.email if order.user else 'Guest',
            'total': order.total_amount,
            'status': order.get_status_display(),
            'created_at': order.created_at,
        }
        for order in orders
    ]


def get_pending_actions():
    """Get counts of items requiring attention."""
    pending = {
        'pending_orders': 0,
        'pending_returns': 0,
        'low_stock_alerts': 0,
        'pending_reviews': 0,
    }

    try:
        from apps.commerce.orders.models import Order
        pending['pending_orders'] = Order.objects.filter(status='pending').count()
    except ImportError:
        pass

    try:
        from apps.commerce.returns.models import ReturnRequest
        pending['pending_returns'] = ReturnRequest.objects.filter(status='pending').count()
    except ImportError:
        pass

    try:
        from apps.store.inventory.models import StockAlert
        pending['low_stock_alerts'] = StockAlert.objects.filter(is_resolved=False).count()
    except ImportError:
        pass

    try:
        from apps.store.reviews.models import Review
        pending['pending_reviews'] = Review.objects.filter(is_approved=False).count()
    except ImportError:
        pass

    return pending


def format_currency(value, symbol='₫'):
    """Format a number as currency."""
    if value is None:
        return f"0{symbol}"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B{symbol}"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M{symbol}"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K{symbol}"
    return f"{value:,.0f}{symbol}"


def dashboard_callback(request, context):
    """
    Callback function for Django Unfold Dashboard.
    
    Populates the admin dashboard with:
    - KPI cards (Revenue, Orders, Users, Products)
    - Quick action links
    - Recent orders widget
    - Pending actions summary
    
    Args:
        request: The HTTP request object
        context: The template context dict
        
    Returns:
        Updated context dict with dashboard data
    """
    # Initialize KPI list
    kpis = []

    # ----- Order Stats -----
    order_stats = get_order_stats()
    if order_stats:
        kpis.extend([
            {
                "title": _("Revenue (30d)"),
                "metric": format_currency(order_stats['revenue']),
                "footer": {
                    "text": f"{'+' if order_stats['revenue_change'] >= 0 else ''}{order_stats['revenue_change']}% vs last period",
                    "trend": "up" if order_stats['revenue_change'] >= 0 else "down",
                },
                "icon": "payments",
            },
            {
                "title": _("Orders (30d)"),
                "metric": f"{order_stats['count']:,}",
                "footer": {
                    "text": f"{'+' if order_stats['count_change'] >= 0 else ''}{order_stats['count_change']}% vs last period",
                    "trend": "up" if order_stats['count_change'] >= 0 else "down",
                },
                "icon": "shopping_bag",
            },
            {
                "title": _("Avg. Order Value"),
                "metric": format_currency(order_stats['aov']),
                "footer": {
                    "text": _("Based on last 30 days"),
                },
                "icon": "trending_up",
            },
        ])

    # ----- User Stats -----
    user_stats = get_user_stats()
    if user_stats:
        kpis.append({
            "title": _("New Users (30d)"),
            "metric": f"{user_stats['new_users']:,}",
            "footer": {
                "text": f"Total: {user_stats['total_users']:,} active users",
            },
            "icon": "person_add",
        })

    # ----- Product Stats -----
    product_stats = get_product_stats()
    if product_stats:
        kpis.append({
            "title": _("Products"),
            "metric": f"{product_stats['total_products']:,}",
            "footer": {
                "text": f"⚠️ {product_stats['low_stock']} low stock | 🚫 {product_stats['out_of_stock']} out",
            },
            "icon": "inventory_2",
        })

    # ----- Quick Links -----
    navigation = [
        {
            "title": _("Quick Actions"),
            "items": [
                {"title": _("New Order"), "link": "/admin-login/orders/order/add/", "icon": "add_shopping_cart"},
                {"title": _("New Product"), "link": "/admin-login/catalog/product/add/", "icon": "add_box"},
                {"title": _("New Coupon"), "link": "/admin-login/marketing/coupon/add/", "icon": "local_offer"},
                {"title": _("View Reports"), "link": "/admin-login/analytics/dailymetric/", "icon": "analytics"},
            ],
        },
    ]

    # ----- Pending Actions -----
    pending = get_pending_actions()
    pending_items = []
    if pending['pending_orders'] > 0:
        pending_items.append({
            "title": _("Pending Orders"),
            "count": pending['pending_orders'],
            "link": "/admin-login/orders/order/?status__exact=pending",
            "icon": "pending",
            "color": "warning",
        })
    if pending['pending_returns'] > 0:
        pending_items.append({
            "title": _("Pending Returns"),
            "count": pending['pending_returns'],
            "link": "/admin-login/returns/returnrequest/?status__exact=pending",
            "icon": "assignment_return",
            "color": "info",
        })
    if pending['low_stock_alerts'] > 0:
        pending_items.append({
            "title": _("Low Stock Alerts"),
            "count": pending['low_stock_alerts'],
            "link": "/admin-login/inventory/stockalert/?is_resolved__exact=0",
            "icon": "warning",
            "color": "danger",
        })
    if pending['pending_reviews'] > 0:
        pending_items.append({
            "title": _("Reviews to Approve"),
            "count": pending['pending_reviews'],
            "link": "/admin-login/reviews/review/?is_approved__exact=0",
            "icon": "rate_review",
            "color": "secondary",
        })

    # ----- Recent Orders -----
    recent_orders = get_recent_orders(5)

    # ----- Update Context -----
    context.update({
        "kpi": kpis,
        "navigation": navigation,
        "pending_actions": pending_items,
        "recent_orders": recent_orders,
        # Additional context for custom widgets
        "order_stats": order_stats,
        "user_stats": user_stats,
        "product_stats": product_stats,
    })

    return context
