"""
Phone number utilities.
"""
import re


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to +84 format.
    
    Examples:
    - 0901234567 -> +84901234567
    - +84901234567 -> +84901234567
    - 84901234567 -> +84901234567
    """
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


def mask_phone(phone: str) -> str:
    """Mask phone for display."""
    if len(phone) < 6:
        return phone
    
    return phone[:3] + '*' * (len(phone) - 6) + phone[-3:]
