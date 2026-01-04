"""
Date/Time utilities.
"""
from datetime import datetime, timedelta
from django.utils import timezone


def get_date_range(period: str) -> tuple:
    """
    Get date range for common periods.
    
    Args:
        period: 'today', 'yesterday', 'this_week', 'last_week', 
                'this_month', 'last_month', 'this_year'
    
    Returns:
        (start_date, end_date) tuple
    """
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if period == 'today':
        return today, now
    
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, today
    
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start, now
    
    elif period == 'last_week':
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
        return start, end
    
    elif period == 'this_month':
        start = today.replace(day=1)
        return start, now
    
    elif period == 'last_month':
        end = today.replace(day=1)
        if end.month == 1:
            start = end.replace(year=end.year - 1, month=12)
        else:
            start = end.replace(month=end.month - 1)
        return start, end
    
    elif period == 'this_year':
        start = today.replace(month=1, day=1)
        return start, now
    
    # Default: last 30 days
    return today - timedelta(days=30), now


def format_relative_time(dt: datetime) -> str:
    """Format datetime as relative time."""
    now = timezone.now()
    delta = now - dt
    
    if delta.seconds < 60:
        return 'Vừa xong'
    elif delta.seconds < 3600:
        minutes = delta.seconds // 60
        return f'{minutes} phút trước'
    elif delta.days == 0:
        hours = delta.seconds // 3600
        return f'{hours} giờ trước'
    elif delta.days == 1:
        return 'Hôm qua'
    elif delta.days < 7:
        return f'{delta.days} ngày trước'
    elif delta.days < 30:
        weeks = delta.days // 7
        return f'{weeks} tuần trước'
    elif delta.days < 365:
        months = delta.days // 30
        return f'{months} tháng trước'
    else:
        years = delta.days // 365
        return f'{years} năm trước'
