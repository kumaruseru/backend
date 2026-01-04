"""
Order Signals.

Allows decoupled communication between Orders and other modules (Notifications, Analytics).
"""
from django.dispatch import Signal

# Fired when a new order is created
order_created = Signal()  # Sends: order, user

# Fired when order status changes
order_status_changed = Signal()  # Sends: order, old_status, new_status

# Fired when order is confirmed
order_confirmed = Signal()  # Sends: order

# Fired when order is paid
order_paid = Signal()  # Sends: order, payment

# Fired when order is shipped
order_shipped = Signal()  # Sends: order, shipment

# Fired when order is delivered
order_delivered = Signal()  # Sends: order

# Fired when order is cancelled
order_cancelled = Signal()  # Sends: order, reason
