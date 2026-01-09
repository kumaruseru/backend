"""Cash on Delivery (COD) Payment Gateway.

Simple gateway for COD payments - marks payment as pending
until order is delivered and cash is collected.
"""
from decimal import Decimal
from typing import Dict, Any

from .base import BasePaymentGateway, PaymentResult, RefundResult


class CODGateway(BasePaymentGateway):
    """Cash on Delivery payment handler.
    
    COD payments are marked as pending until delivery confirmation,
    at which point they are automatically marked as paid.
    """
    
    gateway_code = 'cod'
    gateway_name = 'Cash on Delivery'
    supports_refund = False
    supports_webhook = False
    
    def create_payment(
        self,
        order,
        amount: Decimal,
        currency: str = 'VND',
        return_url: str = '',
        cancel_url: str = '',
        **kwargs
    ) -> PaymentResult:
        """Create COD payment - immediately returns success.
        
        COD doesn't require online payment, so we just record
        the intent to pay on delivery.
        """
        import secrets
        
        return PaymentResult(
            success=True,
            transaction_id=f"COD{secrets.token_hex(8).upper()}",
            gateway_transaction_id=f"COD-{order.order_number}",
            payment_url='',  # No redirect needed
            raw_response={
                'method': 'cod',
                'message': 'Payment will be collected on delivery',
                'order_number': order.order_number,
            }
        )
    
    def verify_payment(
        self,
        transaction_id: str,
        gateway_data: Dict[str, Any]
    ) -> PaymentResult:
        """Verify COD payment - called when delivery is confirmed."""
        # For COD, payment is verified when delivery is confirmed
        # This is typically triggered by the delivery endpoint
        return PaymentResult(
            success=True,
            transaction_id=transaction_id,
            raw_response=gateway_data
        )
    
    def process_webhook(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> PaymentResult:
        """COD doesn't use webhooks."""
        return PaymentResult(
            success=False,
            error_code='NOT_SUPPORTED',
            error_message='COD does not support webhooks'
        )
