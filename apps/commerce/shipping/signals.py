"""
Commerce Shipping - Django Signals.

Event-driven communication for shipment status changes.
This decouples Shipping module from Order module.

Order module listens to these signals via receivers.py
"""
from django.dispatch import Signal

# ==================== Shipment Signals ====================

# Emitted when shipment status changes (e.g., picked_up, delivered)
# Arguments: sender, shipment, old_status, new_status, webhook_data
shipment_status_changed = Signal()

# Emitted when shipment is created
# Arguments: sender, shipment
shipment_created = Signal()

# Emitted when shipment is cancelled
# Arguments: sender, shipment, reason
shipment_cancelled = Signal()

# Emitted when COD is collected
# Arguments: sender, shipment, amount
cod_collected = Signal()
