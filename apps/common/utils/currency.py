"""
Currency formatting utilities.
"""
from decimal import Decimal


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
