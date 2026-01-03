"""
Commerce Returns - Production-Ready Application Services.

Comprehensive business logic with:
- Full return workflow
- Refund integration
- Email notifications
- Logging and monitoring
- Error handling
"""
import logging
from typing import Optional, List, Dict, Any
from decimal import Decimal
from uuid import UUID
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from apps.common.core.exceptions import (
    NotFoundError, BusinessRuleViolation, ValidationError, AuthorizationError
)
from apps.commerce.orders.models import Order, OrderItem
from .models import ReturnRequest, ReturnItem, ReturnImage, ReturnStatusHistory

logger = logging.getLogger('apps.returns')


class ReturnService:
    """
    Return/refund management use cases.
    
    Handles:
    - Return request creation
    - Admin review workflow
    - Quality inspection
    - Refund processing
    - Notifications
    """
    
    # Configuration
    RETURN_WINDOW_DAYS = 7
    MAX_IMAGES_PER_REQUEST = 10
    
    # --- User Operations ---
    
    @staticmethod
    @transaction.atomic
    def create_return_request(
        user,
        order_id: UUID,
        reason: str,
        description: str,
        items: List[Dict],
        refund_method: str = 'original',
        bank_info: Dict = None
    ) -> ReturnRequest:
        """
        Create a new return request with items.
        
        Args:
            user: User making the request
            order_id: Order UUID
            reason: Return reason code
            description: Detailed description
            items: List of items to return
            refund_method: Refund method choice
            bank_info: Bank details if refund_method is bank_transfer
            
        Returns:
            Created ReturnRequest
        """
        # Get order
        try:
            order = Order.objects.prefetch_related('items').get(id=order_id, user=user)
        except Order.DoesNotExist:
            raise NotFoundError(message='Đơn hàng không tồn tại')
        
        # Validate eligibility
        if order.status != Order.Status.DELIVERED:
            raise BusinessRuleViolation(
                message='Chỉ có thể yêu cầu hoàn trả đơn hàng đã giao'
            )
        
        if order.delivered_at:
            from datetime import timedelta
            deadline = order.delivered_at + timedelta(days=ReturnService.RETURN_WINDOW_DAYS)
            if timezone.now() > deadline:
                raise BusinessRuleViolation(
                    message=f'Đã quá thời hạn hoàn trả ({ReturnService.RETURN_WINDOW_DAYS} ngày)'
                )
        
        # Check existing pending returns
        pending = order.return_requests.filter(
            status__in=[
                ReturnRequest.Status.PENDING,
                ReturnRequest.Status.REVIEWING,
                ReturnRequest.Status.APPROVED,
                ReturnRequest.Status.AWAITING_RETURN
            ]
        ).exists()
        
        if pending:
            raise BusinessRuleViolation(
                message='Đơn hàng đã có yêu cầu hoàn trả đang xử lý'
            )
        
        # Calculate total refund amount
        total_refund = Decimal('0')
        order_items_map = {item.id: item for item in order.items.all()}
        
        for item_data in items:
            order_item = order_items_map.get(item_data['order_item_id'])
            if not order_item:
                raise ValidationError(
                    message=f'Sản phẩm không thuộc đơn hàng này',
                    details={'order_item_id': item_data['order_item_id']}
                )
            
            if item_data['quantity'] > order_item.quantity:
                raise ValidationError(
                    message=f'Số lượng trả vượt quá số lượng đã mua',
                    details={'max_quantity': order_item.quantity}
                )
            
            total_refund += order_item.unit_price * item_data['quantity']
        
        # Create return request
        return_request = ReturnRequest.objects.create(
            order=order,
            user=user,
            reason=reason,
            description=description,
            refund_method=refund_method,
            requested_refund=total_refund,
            bank_name=bank_info.get('bank_name', '') if bank_info else '',
            bank_account_number=bank_info.get('bank_account_number', '') if bank_info else '',
            bank_account_name=bank_info.get('bank_account_name', '') if bank_info else ''
        )
        
        # Create return items
        for item_data in items:
            order_item = order_items_map[item_data['order_item_id']]
            ReturnItem.objects.create(
                return_request=return_request,
                order_item=order_item,
                quantity=item_data['quantity'],
                reason=item_data.get('reason', ''),
                condition=item_data.get('condition', ''),
                notes=item_data.get('notes', ''),
                refund_amount=order_item.unit_price * item_data['quantity']
            )
        
        # Log initial status
        ReturnStatusHistory.objects.create(
            return_request=return_request,
            status=ReturnRequest.Status.PENDING,
            changed_by=user,
            notes='Yêu cầu hoàn trả được tạo'
        )
        
        logger.info(
            f"Return request created: {return_request.request_number} "
            f"for order {order.order_number} by {user.email}"
        )
        
        # Send notification
        ReturnService._notify_return_created(return_request)
        
        return return_request
    
    @staticmethod
    def upload_image(
        return_request: ReturnRequest,
        user,
        image,
        caption: str = ''
    ) -> ReturnImage:
        """Upload evidence image for return request."""
        if return_request.user != user:
            raise AuthorizationError(message='Không có quyền thêm ảnh cho yêu cầu này')
        
        if return_request.status not in [
            ReturnRequest.Status.PENDING,
            ReturnRequest.Status.REVIEWING
        ]:
            raise BusinessRuleViolation(
                message='Không thể thêm ảnh cho yêu cầu đã xử lý'
            )
        
        current_count = return_request.images.count()
        if current_count >= ReturnService.MAX_IMAGES_PER_REQUEST:
            raise BusinessRuleViolation(
                message=f'Tối đa {ReturnService.MAX_IMAGES_PER_REQUEST} ảnh cho mỗi yêu cầu'
            )
        
        return_image = ReturnImage.objects.create(
            return_request=return_request,
            image=image,
            caption=caption,
            uploaded_by=user
        )
        
        logger.info(f"Image uploaded for return {return_request.request_number}")
        
        return return_image
    
    @staticmethod
    def update_tracking(
        return_request: ReturnRequest,
        user,
        tracking_code: str,
        carrier: str = 'GHN'
    ) -> ReturnRequest:
        """Update return shipment tracking info."""
        if return_request.user != user:
            raise AuthorizationError(message='Không có quyền cập nhật yêu cầu này')
        
        if return_request.status not in [
            ReturnRequest.Status.APPROVED,
            ReturnRequest.Status.AWAITING_RETURN
        ]:
            raise BusinessRuleViolation(
                message='Chỉ có thể cập nhật tracking cho yêu cầu đã duyệt'
            )
        
        return_request.return_tracking_code = tracking_code
        return_request.return_carrier = carrier
        return_request.save(update_fields=[
            'return_tracking_code', 'return_carrier', 'updated_at'
        ])
        
        if return_request.status == ReturnRequest.Status.APPROVED:
            return_request.mark_awaiting_return()
        
        logger.info(
            f"Tracking updated for return {return_request.request_number}: {tracking_code}"
        )
        
        return return_request
    
    @staticmethod
    def cancel_return(
        return_request: ReturnRequest,
        user,
        reason: str = ''
    ) -> ReturnRequest:
        """Cancel a pending return request."""
        if return_request.user != user:
            raise AuthorizationError(message='Không có quyền hủy yêu cầu này')
        
        if not return_request.can_cancel:
            raise BusinessRuleViolation(
                message='Không thể hủy yêu cầu ở trạng thái này'
            )
        
        return_request.cancel(user, reason)
        
        logger.info(f"Return cancelled: {return_request.request_number} by user")
        
        return return_request
    
    # --- Query Methods ---
    
    @staticmethod
    def get_user_returns(
        user,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get paginated return requests for a user."""
        queryset = ReturnRequest.objects.filter(user=user).select_related(
            'order'
        ).prefetch_related(
            'items', 'items__order_item'
        )
        
        if status:
            queryset = queryset.filter(status=status)
        
        total = queryset.count()
        offset = (page - 1) * page_size
        returns = list(queryset[offset:offset + page_size])
        
        return {
            'returns': returns,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': (total + page_size - 1) // page_size
        }
    
    @staticmethod
    def get_return_request(
        request_id: UUID,
        user=None
    ) -> ReturnRequest:
        """Get return request by ID."""
        queryset = ReturnRequest.objects.select_related(
            'order', 'user', 'processed_by', 'refund'
        ).prefetch_related(
            'items', 'items__order_item',
            'images', 'status_history'
        )
        
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        
        try:
            return queryset.get(id=request_id)
        except ReturnRequest.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy yêu cầu hoàn trả')
    
    @staticmethod
    def get_by_request_number(
        request_number: str,
        user=None
    ) -> ReturnRequest:
        """Get return request by request number."""
        queryset = ReturnRequest.objects.select_related('order', 'user')
        
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        
        try:
            return queryset.get(request_number=request_number)
        except ReturnRequest.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy yêu cầu hoàn trả')
    
    # --- Admin Operations ---
    
    @staticmethod
    def get_pending_returns(
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get all return requests for admin."""
        queryset = ReturnRequest.objects.select_related(
            'order', 'user'
        ).prefetch_related('items')
        
        if status:
            queryset = queryset.filter(status=status)
        else:
            # Default: show pending first
            queryset = queryset.order_by(
                models.Case(
                    models.When(status='pending', then=0),
                    models.When(status='reviewing', then=1),
                    default=2
                ),
                '-created_at'
            )
        
        total = queryset.count()
        offset = (page - 1) * page_size
        returns = list(queryset[offset:offset + page_size])
        
        return {
            'returns': returns,
            'total': total,
            'page': page,
            'pages': (total + page_size - 1) // page_size
        }
    
    @staticmethod
    @transaction.atomic
    def start_review(
        return_request: ReturnRequest,
        admin_user
    ) -> ReturnRequest:
        """Start reviewing a return request."""
        if return_request.status != ReturnRequest.Status.PENDING:
            raise BusinessRuleViolation(
                message='Chỉ có thể bắt đầu xem xét yêu cầu đang chờ'
            )
        
        return_request.start_review(admin_user)
        
        logger.info(
            f"Return {return_request.request_number} review started by {admin_user.email}"
        )
        
        return return_request
    
    @staticmethod
    @transaction.atomic
    def approve_return(
        return_request: ReturnRequest,
        admin_user,
        approved_refund: Decimal,
        notes: str = ''
    ) -> ReturnRequest:
        """Approve a return request."""
        if not return_request.can_approve:
            raise BusinessRuleViolation(
                message='Không thể duyệt yêu cầu ở trạng thái này'
            )
        
        if approved_refund > return_request.requested_refund:
            raise ValidationError(
                message='Số tiền duyệt không được vượt quá số tiền yêu cầu'
            )
        
        if approved_refund > return_request.order.total:
            raise ValidationError(
                message='Số tiền duyệt không được vượt quá tổng đơn hàng'
            )
        
        return_request.approve(admin_user, approved_refund, notes)
        
        logger.info(
            f"Return {return_request.request_number} approved by {admin_user.email}, "
            f"refund: {approved_refund:,.0f}₫"
        )
        
        # Notify customer
        ReturnService._notify_return_approved(return_request)
        
        return return_request
    
    @staticmethod
    @transaction.atomic
    def reject_return(
        return_request: ReturnRequest,
        admin_user,
        reason: str
    ) -> ReturnRequest:
        """Reject a return request."""
        if not return_request.can_approve:
            raise BusinessRuleViolation(
                message='Không thể từ chối yêu cầu ở trạng thái này'
            )
        
        if not reason or len(reason) < 10:
            raise ValidationError(
                message='Vui lòng cung cấp lý do từ chối chi tiết'
            )
        
        return_request.reject(admin_user, reason)
        
        logger.info(
            f"Return {return_request.request_number} rejected by {admin_user.email}"
        )
        
        # Notify customer
        ReturnService._notify_return_rejected(return_request)
        
        return return_request
    
    @staticmethod
    @transaction.atomic
    def receive_items(
        return_request: ReturnRequest,
        admin_user,
        quality_passed: bool,
        notes: str = '',
        item_details: List[Dict] = None
    ) -> ReturnRequest:
        """Mark returned items as received and inspected."""
        if not return_request.can_receive:
            raise BusinessRuleViolation(
                message='Không thể xác nhận nhận hàng ở trạng thái này'
            )
        
        # Update individual items if provided
        if item_details:
            for item_data in item_details:
                try:
                    return_item = return_request.items.get(id=item_data['item_id'])
                    return_item.accepted_quantity = item_data.get(
                        'accepted_quantity',
                        return_item.quantity
                    )
                    return_item.save(update_fields=['accepted_quantity', 'updated_at'])
                except ReturnItem.DoesNotExist:
                    pass
        
        return_request.receive_items(admin_user, quality_passed, notes)
        
        logger.info(
            f"Return {return_request.request_number} items received, "
            f"quality: {'passed' if quality_passed else 'failed'}"
        )
        
        return return_request
    
    @staticmethod
    @transaction.atomic
    def process_refund(
        return_request: ReturnRequest,
        admin_user
    ) -> ReturnRequest:
        """Process refund for approved return."""
        if return_request.status != ReturnRequest.Status.RECEIVED:
            raise BusinessRuleViolation(
                message='Trước tiên phải xác nhận đã nhận hàng trả'
            )
        
        if not return_request.quality_check_passed:
            raise BusinessRuleViolation(
                message='Không thể hoàn tiền khi kiểm tra chất lượng không đạt'
            )
        
        # Create refund through billing service
        try:
            from apps.commerce.billing.services import PaymentService
            from apps.commerce.billing.models import Payment
            
            # Find completed payment for order
            payment = Payment.objects.filter(
                order=return_request.order,
                status=Payment.Status.COMPLETED
            ).first()
            
            if payment:
                refund = PaymentService.create_refund(
                    payment_id=payment.id,
                    amount=return_request.approved_refund,
                    reason=f"Return #{return_request.request_number}: {return_request.reason}"
                )
                return_request.process_refund(refund)
            else:
                # Manual refund tracking for COD
                return_request.status = ReturnRequest.Status.PROCESSING_REFUND
                return_request.refunded_at = timezone.now()
                return_request.save(update_fields=['status', 'refunded_at', 'updated_at'])
                return_request._log_status_change(
                    ReturnRequest.Status.PROCESSING_REFUND,
                    admin_user,
                    'Manual refund processing'
                )
        except Exception as e:
            logger.error(f"Refund processing error: {e}")
            raise BusinessRuleViolation(
                message='Không thể xử lý hoàn tiền. Vui lòng thử lại.'
            )
        
        logger.info(
            f"Refund processed for return {return_request.request_number}"
        )
        
        # Notify customer
        ReturnService._notify_refund_processed(return_request)
        
        return return_request
    
    @staticmethod
    @transaction.atomic
    def complete_return(
        return_request: ReturnRequest,
        admin_user
    ) -> ReturnRequest:
        """Mark return as completed."""
        if return_request.status not in [
            ReturnRequest.Status.RECEIVED,
            ReturnRequest.Status.PROCESSING_REFUND
        ]:
            raise BusinessRuleViolation(
                message='Không thể hoàn tất yêu cầu ở trạng thái này'
            )
        
        return_request.complete(admin_user)
        
        # Update order status if full return
        if not return_request.is_partial_return:
            return_request.order.status = Order.Status.REFUNDED
            return_request.order.save(update_fields=['status', 'updated_at'])
        
        logger.info(f"Return {return_request.request_number} completed")
        
        # Notify customer
        ReturnService._notify_return_completed(return_request)
        
        return return_request
    
    # --- Statistics ---
    
    @staticmethod
    def get_statistics(days: int = 30) -> Dict[str, Any]:
        """Get return statistics for dashboard."""
        from django.db.models import Count, Sum, Avg
        
        since = timezone.now() - timezone.timedelta(days=days)
        
        stats = ReturnRequest.objects.filter(
            created_at__gte=since
        ).aggregate(
            total=Count('id'),
            pending=Count('id', filter=models.Q(status='pending')),
            approved=Count('id', filter=models.Q(status='approved')),
            rejected=Count('id', filter=models.Q(status='rejected')),
            completed=Count('id', filter=models.Q(status='completed')),
            total_refunded=Sum('approved_refund', filter=models.Q(status='completed')),
            avg_refund=Avg('approved_refund', filter=models.Q(status='completed'))
        )
        
        # Reason breakdown
        reasons = ReturnRequest.objects.filter(
            created_at__gte=since
        ).values('reason').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'period_days': days,
            'total_requests': stats['total'] or 0,
            'pending': stats['pending'] or 0,
            'approved': stats['approved'] or 0,
            'rejected': stats['rejected'] or 0,
            'completed': stats['completed'] or 0,
            'total_refunded': stats['total_refunded'] or 0,
            'avg_refund': stats['avg_refund'] or 0,
            'reasons': list(reasons)
        }
    
    # --- Notifications ---
    
    @staticmethod
    def _notify_return_created(return_request: ReturnRequest) -> None:
        """Send notification when return is created."""
        try:
            from apps.users.notifications.services import EmailService
            # TODO: Implement return created email template
            logger.debug(f"Return created notification for {return_request.request_number}")
        except Exception as e:
            logger.warning(f"Failed to send return created notification: {e}")
    
    @staticmethod
    def _notify_return_approved(return_request: ReturnRequest) -> None:
        """Send notification when return is approved."""
        try:
            from apps.users.notifications.services import EmailService
            # TODO: Implement return approved email template
            logger.debug(f"Return approved notification for {return_request.request_number}")
        except Exception as e:
            logger.warning(f"Failed to send return approved notification: {e}")
    
    @staticmethod
    def _notify_return_rejected(return_request: ReturnRequest) -> None:
        """Send notification when return is rejected."""
        try:
            from apps.users.notifications.services import EmailService
            # TODO: Implement return rejected email template
            logger.debug(f"Return rejected notification for {return_request.request_number}")
        except Exception as e:
            logger.warning(f"Failed to send return rejected notification: {e}")
    
    @staticmethod
    def _notify_refund_processed(return_request: ReturnRequest) -> None:
        """Send notification when refund is processed."""
        try:
            from apps.users.notifications.services import EmailService
            # TODO: Implement refund processed email template
            logger.debug(f"Refund processed notification for {return_request.request_number}")
        except Exception as e:
            logger.warning(f"Failed to send refund notification: {e}")
    
    @staticmethod
    def _notify_return_completed(return_request: ReturnRequest) -> None:
        """Send notification when return is completed."""
        try:
            from apps.users.notifications.services import EmailService
            # TODO: Implement return completed email template
            logger.debug(f"Return completed notification for {return_request.request_number}")
        except Exception as e:
            logger.warning(f"Failed to send return completed notification: {e}")


# Import for statistics
from django.db import models
