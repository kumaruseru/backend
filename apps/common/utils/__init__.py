"""Common Utils Package."""
from .middleware import (
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    SuspiciousActivityMiddleware,
    SensitiveDataFilter,
    Admin2FAEnforcementMiddleware,
)
from .security import (
    verify_turnstile,
    block_ip,
    unblock_ip,
    is_ip_blocked,
    generate_secure_token,
    generate_otp,
    hash_token,
    get_client_ip,
    mask_email,
    mask_phone,
)
from .string import (
    remove_vietnamese_accents,
    slugify_vietnamese,
    sanitize_html,
    truncate_words,
    truncate_chars,
    generate_excerpt,
    normalize_whitespace,
)

__all__ = [
    'SecurityHeadersMiddleware',
    'RequestLoggingMiddleware',
    'SuspiciousActivityMiddleware',
    'SensitiveDataFilter',
    'Admin2FAEnforcementMiddleware',
    'verify_turnstile',
    'block_ip',
    'unblock_ip',
    'is_ip_blocked',
    'generate_secure_token',
    'generate_otp',
    'hash_token',
    'get_client_ip',
    'mask_email',
    'mask_phone',
    'remove_vietnamese_accents',
    'slugify_vietnamese',
    'sanitize_html',
    'truncate_words',
    'truncate_chars',
    'generate_excerpt',
    'normalize_whitespace',
]
