"""
Common Core - Utility Functions.

General purpose utilities used across the application.
"""
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from django.utils import timezone


# ==================== Random Generation ====================

def generate_random_string(length: int = 32, charset: str = None) -> str:
    """Generate a random string."""
    if charset is None:
        charset = string.ascii_letters + string.digits
    return ''.join(secrets.choice(charset) for _ in range(length))


def generate_random_code(length: int = 6, digits_only: bool = True) -> str:
    """Generate a random code (for OTP, verification codes)."""
    if digits_only:
        charset = string.digits
    else:
        charset = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(charset) for _ in range(length))


def generate_order_number() -> str:
    """Generate unique order number."""
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    random_part = generate_random_code(4, digits_only=True)
    return f"ORD-{timestamp}-{random_part}"


def generate_tracking_code() -> str:
    """Generate tracking code."""
    return generate_random_string(12, string.ascii_uppercase + string.digits)


def generate_token() -> str:
    """Generate secure token."""
    return secrets.token_urlsafe(32)


# ==================== Hashing ====================

def hash_string(value: str, algorithm: str = 'sha256') -> str:
    """Hash a string value."""
    hasher = hashlib.new(algorithm)
    hasher.update(value.encode('utf-8'))
    return hasher.hexdigest()


def short_hash(value: str, length: int = 8) -> str:
    """Generate short hash for IDs."""
    return hash_string(value)[:length]


# ==================== Money Formatting ====================

def format_money(amount: Decimal, currency: str = 'VND') -> str:
    """Format money amount for display."""
    if currency == 'VND':
        return f"{amount:,.0f}₫"
    elif currency == 'USD':
        return f"${amount:,.2f}"
    return f"{amount:,.0f} {currency}"


def parse_money(value: str) -> Decimal:
    """Parse money string to Decimal."""
    # Remove currency symbols and formatting
    value = value.replace('₫', '').replace('$', '').replace(',', '').strip()
    return Decimal(value)


# ==================== Date/Time Utilities ====================

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


# ==================== String Utilities ====================

def truncate(text: str, length: int = 100, suffix: str = '...') -> str:
    """Truncate text to specified length."""
    if len(text) <= length:
        return text
    return text[:length - len(suffix)] + suffix


def mask_email(email: str) -> str:
    """Mask email for display."""
    if '@' not in email:
        return email
    
    local, domain = email.rsplit('@', 1)
    
    if len(local) <= 2:
        masked_local = local[0] + '*'
    else:
        masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
    
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    """Mask phone for display."""
    if len(phone) < 6:
        return phone
    
    return phone[:3] + '*' * (len(phone) - 6) + phone[-3:]


# ==================== Dict Utilities ====================

def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def pick(obj: Dict, keys: List[str]) -> Dict:
    """Pick specified keys from dict."""
    return {k: v for k, v in obj.items() if k in keys}


def omit(obj: Dict, keys: List[str]) -> Dict:
    """Omit specified keys from dict."""
    return {k: v for k, v in obj.items() if k not in keys}


# ==================== List Utilities ====================

def chunk(lst: List, size: int) -> List[List]:
    """Split list into chunks."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def flatten(nested_list: List) -> List:
    """Flatten nested list."""
    result = []
    for item in nested_list:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def unique(lst: List, key=None) -> List:
    """Get unique items from list."""
    seen = set()
    result = []
    
    for item in lst:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)
    
    return result


# ==================== Phone Utilities ====================

def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to +84 format.
    
    Examples:
    - 0901234567 -> +84901234567
    - +84901234567 -> +84901234567
    - 84901234567 -> +84901234567
    """
    import re
    if not phone:
        return phone
    
    # Remove all spaces, dashes, dots, parentheses
    phone = re.sub(r'[\s\-\.\(\)]', '', phone)
    
    # Convert 0-prefix to +84
    if phone.startswith('0'):
        phone = '+84' + phone[1:]
    # Add + if starts with 84
    elif phone.startswith('84') and not phone.startswith('+84'):
        phone = '+' + phone
    
    return phone


def format_phone_display(phone: str) -> str:
    """
    Format phone for display.
    
    Example:
    - +84901234567 -> 0901 234 567
    """
    if not phone:
        return phone
    
    # Normalize first
    phone = normalize_phone(phone)
    
    # Convert to local format
    if phone.startswith('+84'):
        phone = '0' + phone[3:]
    
    # Format with spaces
    if len(phone) == 10:
        return f"{phone[:4]} {phone[4:7]} {phone[7:]}"
    
    return phone


# ==================== Vietnamese Text Utilities ====================

def remove_vietnamese_accents(text: str) -> str:
    """Remove Vietnamese diacritics from text."""
    accents = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        'đ': 'd',
        'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
        'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
        'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
        'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
        'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
        'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
        'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
        'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
        'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
        'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
        'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
        'Đ': 'D'
    }
    
    for viet, latin in accents.items():
        text = text.replace(viet, latin)
    
    return text


def generate_slug_from_vietnamese(text: str) -> str:
    """Generate slug from Vietnamese text."""
    from django.utils.text import slugify
    
    # Remove accents
    text = remove_vietnamese_accents(text)
    
    # Generate slug
    return slugify(text, allow_unicode=False)
