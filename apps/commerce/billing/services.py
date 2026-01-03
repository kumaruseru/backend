"""
Commerce Billing - Production-Ready Application Services.

Comprehensive payment orchestration with:
- Multi-gateway support
- Payment lifecycle management
- Webhook processing
- Refund handling
- Statistics
"""
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from apps.common.core.exceptions import (
    NotFoundError, BusinessRuleViolation, ValidationError, ExternalServiceError
)
from apps.commerce.orders.models import Order
from .models import Payment, Refund, PaymentLog, PaymentMethod
from .gateways import get_gateway

logger = logging.getLogger('apps.billing')


class PaymentService:
    """
    Payment orchestration service.
    
    Handles:
    - Payment creation and processing
    - Gateway integration
    - Webhook handling
    - Refunds
    - Retry logic
    """
    
    PAYMENT_EXPIRY_MINUTES = 15
    
    @staticmethod
    @transaction.atomic
    def create_payment(
        order: Order,
        method: str,
        return_url: str = '',
        cancel_url: str = '',
        ip_address: str = '',
        user_agent: str = ''
    ) -> Dict[str, Any]:
        """
        Create payment for order.
        
        Args:
            order: Order to pay for
            method: Payment method code
            return_url: URL to return after payment
            cancel_url: URL on payment cancellation
            ip_address: Client IP
            user_agent: Client user agent
            
        Returns:
            Dict with payment_url and payment info
        """
        # Validate order
        if order.payment_status == Order.PaymentStatus.PAID:
            raise BusinessRuleViolation(message='Đơn hàng đã được thanh toán')
        
        if order.status == Order.Status.CANCELLED:
            raise BusinessRuleViolation(message='Đơn hàng đã bị hủy')
        
        # Cancel existing pending payments
        Payment.objects.filter(
            order=order,
            status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING]
        ).update(status=Payment.Status.CANCELLED)
        
        # Create payment record
        expires_at = timezone.now() + timedelta(minutes=PaymentService.PAYMENT_EXPIRY_MINUTES)
        
        payment = Payment.objects.create(
            order=order,
            user=order.user,
            method=method,
            amount=order.total,
            currency='VND',
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else ''
        )
        
        # Log creation
        PaymentLog.objects.create(
            payment=payment,
            event='created',
            new_status=Payment.Status.PENDING,
            notes=f'Payment created for order {order.order_number}'
        )
        
        # Handle COD
        if method == Payment.Method.COD:
            payment.status = Payment.Status.AWAITING_CAPTURE
            payment.save(update_fields=['status', 'updated_at'])
            
            # Auto-confirm order for COD
            if order.status == Order.Status.PENDING:
                order.confirm()
            
            return {
                'success': True,
                'payment_id': payment.id,
                'method': method,
                'message': 'Đơn hàng COD đã được tạo'
            }
        
        # Get gateway and create payment URL
        try:
            gateway = get_gateway(method)
            
            result = gateway.create_payment(
                payment_id=str(payment.id),
                order_id=order.order_number,
                amount=int(order.total),
                description=f'Thanh toan don hang {order.order_number}',
                return_url=return_url or _get_default_return_url(),
                cancel_url=cancel_url,
                ip_address=ip_address
            )
            
            if result.get('success'):
                payment.payment_url = result.get('payment_url', '')
                payment.qr_code_url = result.get('qr_code_url', '')
                payment.transaction_id = result.get('transaction_id', '')
                payment.provider_data = result.get('provider_data', {})
                payment.status = Payment.Status.PROCESSING
                payment.save(update_fields=[
                    'payment_url', 'qr_code_url', 'transaction_id',
                    'provider_data', 'status', 'updated_at'
                ])
                
                logger.info(
                    f"Payment created: {payment.id} for order {order.order_number}, "
                    f"method: {method}"
                )
                
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'payment_url': payment.payment_url,
                    'qr_code_url': payment.qr_code_url,
                    'transaction_id': payment.transaction_id,
                    'expires_at': expires_at,
                    'method': method
                }
            else:
                payment.mark_failed(result.get('error', 'Gateway error'))
                raise ExternalServiceError(
                    message=result.get('error', 'Không thể tạo thanh toán'),
                    service=method
                )
                
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Payment creation failed: {e}", exc_info=True)
            payment.mark_failed(str(e))
            raise ExternalServiceError(
                message='Lỗi kết nối cổng thanh toán',
                service=method
            )
    
    @staticmethod
    def get_payment(payment_id: UUID, user=None) -> Payment:
        """Get payment by ID."""
        queryset = Payment.objects.select_related('order', 'user').prefetch_related(
            'logs', 'refunds'
        )
        
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        
        try:
            return queryset.get(id=payment_id)
        except Payment.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy thanh toán')
    
    @staticmethod
    def get_by_transaction_id(transaction_id: str) -> Payment:
        """Get payment by transaction ID."""
        try:
            return Payment.objects.select_related('order').get(
                transaction_id=transaction_id
            )
        except Payment.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy giao dịch')
    
    @staticmethod
    def get_order_payments(order_id: UUID) -> list:
        """Get all payments for an order."""
        return list(
            Payment.objects.filter(order_id=order_id).prefetch_related('logs')
        )
    
    @staticmethod
    @transaction.atomic
    def process_callback(
        method: str,
        callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process payment callback/webhook from gateway.
        
        Args:
            method: Payment method (vnpay, momo, stripe)
            callback_data: Callback data from gateway
            
        Returns:
            Dict with processing result
        """
        logger.info(
            f"Processing {method} callback",
            extra={'callback_data': callback_data}
        )
        
        try:
            gateway = get_gateway(method)
            
            # Verify callback signature
            if not gateway.verify_callback(callback_data):
                logger.warning(f"Invalid callback signature for {method}")
                return {'success': False, 'error': 'Invalid signature'}
            
            # Parse callback
            result = gateway.parse_callback(callback_data)
            
            payment_id = result.get('payment_id')
            if not payment_id:
                return {'success': False, 'error': 'Missing payment ID'}
            
            try:
                payment = Payment.objects.select_related('order').get(id=payment_id)
            except Payment.DoesNotExist:
                logger.warning(f"Payment not found: {payment_id}")
                return {'success': False, 'error': 'Payment not found'}
            
            # Already processed
            if payment.is_completed:
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'status': 'already_completed'
                }
            
            # Store webhook data
            payment.webhook_data = callback_data
            payment.save(update_fields=['webhook_data', 'updated_at'])
            
            # Process result
            if result.get('success'):
                payment.mark_completed(
                    transaction_id=result.get('transaction_id'),
                    provider_data=result.get('provider_data', {})
                )
                
                logger.info(
                    f"Payment completed: {payment.id}, order: {payment.order.order_number}"
                )
                
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'order_number': payment.order.order_number,
                    'status': 'completed'
                }
            else:
                payment.mark_failed(
                    reason=result.get('error', 'Payment failed'),
                    code=result.get('error_code', '')
                )
                
                return {
                    'success': False,
                    'payment_id': payment.id,
                    'status': 'failed',
                    'error': result.get('error')
                }
                
        except Exception as e:
            logger.error(f"Callback processing error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    @transaction.atomic
    def retry_payment(payment: Payment) -> Dict[str, Any]:
        """Retry a failed payment."""
        if not payment.can_retry:
            raise BusinessRuleViolation(
                message='Không thể thử lại thanh toán này'
            )
        
        payment.increment_retry()
        
        # Create new payment URL
        try:
            gateway = get_gateway(payment.method)
            
            result = gateway.create_payment(
                payment_id=str(payment.id),
                order_id=payment.order.order_number,
                amount=int(payment.amount),
                description=f'Thanh toan don hang {payment.order.order_number} (retry)',
                return_url=_get_default_return_url(),
                ip_address=payment.ip_address or ''
            )
            
            if result.get('success'):
                payment.payment_url = result.get('payment_url', '')
                payment.status = Payment.Status.PROCESSING
                payment.expires_at = timezone.now() + timedelta(
                    minutes=PaymentService.PAYMENT_EXPIRY_MINUTES
                )
                payment.save(update_fields=[
                    'payment_url', 'status', 'expires_at', 'updated_at'
                ])
                
                return {
                    'success': True,
                    'payment_url': payment.payment_url,
                    'retry_count': payment.retry_count
                }
            else:
                payment.mark_failed(result.get('error', 'Retry failed'))
                return {'success': False, 'error': result.get('error')}
                
        except Exception as e:
            payment.mark_failed(str(e))
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def cancel_payment(payment: Payment, reason: str = '') -> Payment:
        """Cancel a pending payment."""
        if payment.is_completed:
            raise BusinessRuleViolation(
                message='Không thể hủy thanh toán đã hoàn thành'
            )
        
        payment.mark_cancelled(reason)
        
        logger.info(f"Payment cancelled: {payment.id}")
        
        return payment
    
    @staticmethod
    def check_expired_payments() -> int:
        """Mark expired payments as expired."""
        expired = Payment.objects.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING],
            expires_at__lt=timezone.now()
        )
        
        count = 0
        for payment in expired:
            payment.mark_expired()
            count += 1
        
        if count > 0:
            logger.info(f"Marked {count} payments as expired")
        
        return count
    
    # --- Refunds ---
    
    @staticmethod
    @transaction.atomic
    def create_refund(
        payment: Payment,
        amount: Decimal = None,
        reason: str = 'customer_request',
        reason_detail: str = '',
        processed_by=None
    ) -> Refund:
        """
        Create refund for payment.
        
        Args:
            payment: Payment to refund
            amount: Refund amount (None for full)
            reason: Refund reason code
            reason_detail: Detailed reason
            processed_by: Admin user processing refund
            
        Returns:
            Created Refund
        """
        if not payment.can_refund:
            raise BusinessRuleViolation(
                message='Thanh toán này không thể hoàn tiền'
            )
        
        refund_amount = amount or payment.refundable_amount
        
        if refund_amount > payment.refundable_amount:
            raise ValidationError(
                message=f'Số tiền hoàn tối đa: {payment.refundable_amount:,.0f}₫'
            )
        
        refund_type = Refund.Type.FULL if refund_amount >= payment.refundable_amount else Refund.Type.PARTIAL
        
        refund = Refund.objects.create(
            payment=payment,
            refund_type=refund_type,
            amount=refund_amount,
            reason=reason,
            reason_detail=reason_detail,
            processed_by=processed_by
        )
        
        # Process with gateway
        if payment.method != Payment.Method.COD:
            try:
                gateway = get_gateway(payment.method)
                
                result = gateway.create_refund(
                    transaction_id=payment.transaction_id,
                    amount=int(refund_amount),
                    reason=reason_detail or reason
                )
                
                if result.get('success'):
                    refund.mark_completed(
                        refund_id=result.get('refund_id'),
                        provider_data=result.get('provider_data', {})
                    )
                else:
                    refund.mark_failed(result.get('error', 'Refund failed'))
                    raise ExternalServiceError(
                        message=result.get('error', 'Không thể hoàn tiền'),
                        service=payment.method
                    )
                    
            except ExternalServiceError:
                raise
            except Exception as e:
                refund.mark_failed(str(e))
                raise ExternalServiceError(
                    message='Lỗi xử lý hoàn tiền',
                    service=payment.method
                )
        else:
            # COD - manual refund
            refund.status = Refund.Status.PROCESSING
            refund.save(update_fields=['status', 'updated_at'])
        
        logger.info(
            f"Refund created: {refund.id} for payment {payment.id}, "
            f"amount: {refund_amount:,.0f}₫"
        )
        
        return refund
    
    @staticmethod
    def complete_manual_refund(refund: Refund, processed_by=None) -> Refund:
        """Complete a manual refund (COD/bank transfer)."""
        if refund.status != Refund.Status.PROCESSING:
            raise BusinessRuleViolation(message='Refund không ở trạng thái xử lý')
        
        refund.processed_by = processed_by
        refund.mark_completed()
        
        return refund
    
    # --- Statistics ---
    
    @staticmethod
    def get_statistics(days: int = 30) -> Dict[str, Any]:
        """Get payment statistics."""
        from django.db.models import Count, Sum, Q
        
        since = timezone.now() - timedelta(days=days)
        
        payments = Payment.objects.filter(created_at__gte=since)
        
        stats = payments.aggregate(
            total_payments=Count('id'),
            total_amount=Sum('amount', filter=Q(status='completed')),
            successful=Count('id', filter=Q(status='completed')),
            failed=Count('id', filter=Q(status='failed')),
            vnpay_count=Count('id', filter=Q(method='vnpay', status='completed')),
            vnpay_amount=Sum('amount', filter=Q(method='vnpay', status='completed')),
            momo_count=Count('id', filter=Q(method='momo', status='completed')),
            momo_amount=Sum('amount', filter=Q(method='momo', status='completed')),
            cod_count=Count('id', filter=Q(method='cod', status='completed')),
            cod_amount=Sum('amount', filter=Q(method='cod', status='completed')),
        )
        
        refunds = Refund.objects.filter(created_at__gte=since, status='completed')
        refund_stats = refunds.aggregate(
            total_refunds=Count('id'),
            total_refunded=Sum('amount')
        )
        
        total = stats['total_payments'] or 1
        successful = stats['successful'] or 0
        
        return {
            'period_days': days,
            'total_payments': stats['total_payments'] or 0,
            'total_amount': stats['total_amount'] or 0,
            'successful_payments': successful,
            'failed_payments': stats['failed'] or 0,
            'success_rate': round(successful / total * 100, 2),
            'by_method': {
                'vnpay': {
                    'count': stats['vnpay_count'] or 0,
                    'amount': stats['vnpay_amount'] or 0
                },
                'momo': {
                    'count': stats['momo_count'] or 0,
                    'amount': stats['momo_amount'] or 0
                },
                'cod': {
                    'count': stats['cod_count'] or 0,
                    'amount': stats['cod_amount'] or 0
                }
            },
            'total_refunds': refund_stats['total_refunds'] or 0,
            'total_refunded': refund_stats['total_refunded'] or 0
        }


def _get_default_return_url() -> str:
    """Get default payment return URL."""
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    return f"{base_url}/checkout/result"
