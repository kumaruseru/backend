"""
Commerce Billing - Django Signals.

Event-driven communication for payment status changes.
This decouples Billing module from Order module.
"""
from django.dispatch import Signal

# ==================== Payment Signals ====================

# Emitted when payment is completed successfully
# Arguments: sender, payment
payment_completed = Signal()

# Emitted when payment fails
# Arguments: sender, payment, reason
payment_failed = Signal()

# Emitted when payment is cancelled
# Arguments: sender, payment, reason
payment_cancelled = Signal()

# Emitted when payment expires
# Arguments: sender, payment
payment_expired = Signal()

# Emitted when refund is completed
# Arguments: sender, refund
refund_completed = Signal()
