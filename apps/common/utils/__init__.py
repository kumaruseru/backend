"""
Common Utils Package.

Organized utilities for the application.
"""
# Currency
from .currency import format_money, parse_money

# Phone
from .phone import normalize_phone, format_phone_display, mask_phone

# String
from .string import (
    truncate, mask_email, 
    remove_vietnamese_accents, generate_slug_from_vietnamese, generate_unique_slug
)

# Generators
from .generators import (
    generate_random_string, generate_random_code, 
    generate_order_number, generate_tracking_code, generate_token
)

# DateTime
from .datetime import get_date_range, format_relative_time

# Collections
from .collections import (
    hash_string, short_hash, deep_merge, pick, omit, chunk, flatten, unique
)

# Security (required by logging config)
from .security import SensitiveDataFilter

__all__ = [
    # Currency
    'format_money', 'parse_money',
    # Phone
    'normalize_phone', 'format_phone_display', 'mask_phone',
    # String
    'truncate', 'mask_email', 'remove_vietnamese_accents', 'generate_slug_from_vietnamese',
    # Generators
    'generate_random_string', 'generate_random_code', 'generate_order_number', 
    'generate_tracking_code', 'generate_token',
    # DateTime
    'get_date_range', 'format_relative_time',
    # Collections
    'hash_string', 'short_hash', 'deep_merge', 'pick', 'omit', 'chunk', 'flatten', 'unique',
    # Security
    'SensitiveDataFilter',
]
