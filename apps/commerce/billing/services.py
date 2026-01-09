"""Commerce Billing - Payment Services."""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Type
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.commerce.orders.models import Order

from .models import PaymentTransaction, PaymentRefund
from .gateways.base import BasePaymentGateway, PaymentResult, RefundResult
from .gateways.cod import CODGateway
from .gateways.momo import MoMoGateway
from .gateways.vnpay import VNPayGateway
from .gateways.stripe_gateway import StripeGateway

logger = logging.getLogger('apps.billing')


class PaymentService:
    """Orchestrates payment operations across different gateways.
    
    Provides a unified interface for creating payments, verifying callbacks,
    processing webhooks, and handling refunds.
    """
    
    # Gateway registry
    GATEWAYS: Dict[str, Type[BasePaymentGateway]] = {
        'cod': CODGateway,
        'momo': MoMoGateway,
        'vnpay': VNPayGateway,
        'stripe': StripeGateway,
    }
    
    @classmethod
    def get_gateway(cls, gateway_code: str) -> BasePaymentGateway:
        """Get gateway instance by code."""
        gateway_class = cls.GATEWAYS.get(gateway_code.lower())
        if not gateway_class:
            raise ValueError(f"Unknown payment gateway: {gateway_code}")
        return gateway_class()
    
    @classmethod
    @transaction.atomic
    def create_payment(
        cls,
        order: Order,
        gateway_code: str = None,
        return_url: str = '',
        cancel_url: str = '',
        ip_address: str = '',
        user_agent: str = '',
        **kwargs
    ) -> PaymentTransaction:
        """Create a payment transaction for an order.
        
        Args:
            order: Order to pay for
            gateway_code: Payment gateway to use (defaults to order's payment_method)
            return_url: URL to redirect after payment
            cancel_url: URL for cancellation
            ip_address: Client IP address
            user_agent: Client user agent
            **kwargs: Additional gateway-specific parameters
            
        Returns:
            PaymentTransaction instance
        """
        if not gateway_code:
            gateway_code = order.payment_method
        
        gateway = cls.get_gateway(gateway_code)
        
        # Create transaction record
        txn = PaymentTransaction.objects.create(
            order=order,
            user=order.user,
            gateway=gateway_code,
            amount=order.total,
            currency=order.currency,
            return_url=return_url,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        
        # Create payment with gateway
        result = gateway.create_payment(
            order=order,
            amount=order.total,
            currency=order.currency,
            return_url=return_url,
            cancel_url=cancel_url,
            ip_address=ip_address,
            **kwargs
        )
        
        if result.success:
            txn.gateway_transaction_id = result.gateway_transaction_id
            txn.payment_url = result.payment_url
            txn.gateway_response = result.raw_response or {}
            txn.status = PaymentTransaction.Status.PROCESSING
            
            # For COD, mark order as pending payment (not processing)
            if gateway_code == 'cod':
                order.payment_status = Order.PaymentStatus.PENDING
                order.save(update_fields=['payment_status', 'updated_at'])
        else:
            txn.status = PaymentTransaction.Status.FAILED
            txn.error_code = result.error_code
            txn.error_message = result.error_message
            txn.gateway_response = result.raw_response or {}
        
        txn.save()
        logger.info(f"Payment created: {txn.transaction_id} - {txn.status}")
        
        return txn
    
    @classmethod
    @transaction.atomic
    def verify_payment(
        cls,
        transaction_id: str,
        gateway_data: Dict[str, Any]
    ) -> PaymentTransaction:
        """Verify payment from gateway callback/return.
        
        Args:
            transaction_id: Our transaction ID or gateway reference
            gateway_data: Data from gateway callback
            
        Returns:
            Updated PaymentTransaction
        """
        # Find transaction
        try:
            txn = PaymentTransaction.objects.select_for_update().get(
                transaction_id=transaction_id
            )
        except PaymentTransaction.DoesNotExist:
            # Try by gateway transaction ID
            txn = PaymentTransaction.objects.select_for_update().get(
                gateway_transaction_id=gateway_data.get('orderId', '')
            )
        
        if txn.status == PaymentTransaction.Status.COMPLETED:
            logger.info(f"Transaction {transaction_id} already completed")
            return txn
        
        gateway = cls.get_gateway(txn.gateway)
        result = gateway.verify_payment(transaction_id, gateway_data)
        
        if result.success:
            txn.mark_completed(
                gateway_txn_id=result.gateway_transaction_id,
                response=result.raw_response
            )
            logger.info(f"Payment verified: {txn.transaction_id}")
        else:
            txn.mark_failed(
                error_code=result.error_code,
                error_message=result.error_message,
                response=result.raw_response
            )
            logger.warning(f"Payment verification failed: {txn.transaction_id} - {result.error_code}")
        
        return txn
    
    @classmethod
    @transaction.atomic
    def process_webhook(
        cls,
        gateway_code: str,
        payload: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> Optional[PaymentTransaction]:
        """Process webhook from payment gateway.
        
        Args:
            gateway_code: Which gateway sent the webhook
            payload: Webhook payload
            headers: HTTP headers
            
        Returns:
            Updated PaymentTransaction or None
        """
        gateway = cls.get_gateway(gateway_code)
        result = gateway.process_webhook(payload, headers)
        
        if not result.transaction_id and not result.gateway_transaction_id:
            logger.warning(f"Webhook has no transaction reference: {gateway_code}")
            return None
        
        # Find transaction
        try:
            if result.transaction_id:
                txn = PaymentTransaction.objects.select_for_update().get(
                    transaction_id=result.transaction_id
                )
            else:
                txn = PaymentTransaction.objects.select_for_update().get(
                    gateway_transaction_id=result.gateway_transaction_id
                )
        except PaymentTransaction.DoesNotExist:
            logger.warning(f"Transaction not found for webhook: {result.transaction_id or result.gateway_transaction_id}")
            return None
        
        if txn.status == PaymentTransaction.Status.COMPLETED:
            logger.info(f"Transaction {txn.transaction_id} already completed (webhook)")
            return txn
        
        if result.success:
            txn.mark_completed(
                gateway_txn_id=result.gateway_transaction_id,
                response=result.raw_response
            )
            logger.info(f"Webhook payment confirmed: {txn.transaction_id}")
        else:
            txn.mark_failed(
                error_code=result.error_code,
                error_message=result.error_message,
                response=result.raw_response
            )
            logger.warning(f"Webhook payment failed: {txn.transaction_id}")
        
        return txn
    
    @classmethod
    @transaction.atomic
    def create_refund(
        cls,
        order: Order,
        amount: Decimal = None,
        reason: str = '',
        processed_by=None
    ) -> PaymentRefund:
        """Create a refund for an order.
        
        Args:
            order: Order to refund
            amount: Refund amount (defaults to full amount)
            reason: Reason for refund
            processed_by: User processing the refund
            
        Returns:
            PaymentRefund instance
        """
        # Get the successful transaction
        txn = PaymentTransaction.objects.filter(
            order=order,
            status=PaymentTransaction.Status.COMPLETED
        ).first()
        
        if not txn:
            raise ValueError("No completed payment transaction found for this order")
        
        if amount is None:
            amount = txn.amount
        
        is_partial = amount < txn.amount
        
        # Check for existing refunds
        existing_refunds = PaymentRefund.objects.filter(
            transaction=txn,
            status=PaymentRefund.Status.COMPLETED
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        if existing_refunds + amount > txn.amount:
            raise ValueError(f"Refund amount exceeds available: {txn.amount - existing_refunds}")
        
        # Create refund record
        refund = PaymentRefund.objects.create(
            transaction=txn,
            order=order,
            processed_by=processed_by,
            amount=amount,
            is_partial=is_partial,
            reason=reason or PaymentRefund.Reason.CUSTOMER_REQUEST,
            notes=reason,
        )
        
        # Process with gateway
        gateway = cls.get_gateway(txn.gateway)
        result = gateway.create_refund(txn, amount, reason)
        
        if result.success:
            refund.mark_completed(
                gateway_refund_id=result.gateway_refund_id,
                response=result.raw_response
            )
            
            # Update order payment status
            if is_partial:
                order.payment_status = Order.PaymentStatus.PARTIAL_REFUND
            else:
                order.payment_status = Order.PaymentStatus.REFUNDED
                order.status = Order.Status.REFUNDED
            order.save(update_fields=['payment_status', 'status', 'updated_at'])
            
            logger.info(f"Refund processed: {refund.refund_id}")
        else:
            refund.status = PaymentRefund.Status.FAILED
            refund.gateway_response = result.raw_response or {}
            refund.save()
            logger.warning(f"Refund failed: {refund.refund_id} - {result.error_code}")
        
        return refund
    
    @classmethod
    def get_available_gateways(cls) -> list:
        """Get list of available payment gateways."""
        return [
            {
                'code': code,
                'name': gateway().gateway_name,
                'supports_refund': gateway().supports_refund,
            }
            for code, gateway in cls.GATEWAYS.items()
        ]


# Import models for type hints
from django.db import models
