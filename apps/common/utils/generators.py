"""
Random code/token generators.
"""
import secrets
import string
from django.utils import timezone


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
