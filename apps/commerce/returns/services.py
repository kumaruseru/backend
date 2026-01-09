"""Commerce Returns - Application Services."""
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Sum, Q

from apps.common.core.exceptions import NotFoundError, BusinessRuleViolation
from .models import ReturnRequest, ReturnItem, ReturnImage, ReturnStatusHistory

logger = logging.getLogger('apps.returns')


class ReturnService:
    @staticmethod
    def get_return(return_id: UUID, user=None) -> ReturnRequest:
        queryset = ReturnRequest.objects.select_related('order', 'user').prefetch_related('items__order_item', 'images', 'status_history')
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        try:
            return queryset.get(id=return_id)
        except ReturnRequest.DoesNotExist:
            raise NotFoundError(message='Return request not found')

    @staticmethod
    def get_by_number(request_number: str, user=None) -> ReturnRequest:
        queryset = ReturnRequest.objects.select_related('order', 'user').prefetch_related('items', 'images')
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        try:
            return queryset.get(request_number=request_number)
        except ReturnRequest.DoesNotExist:
            raise NotFoundError(message='Return request not found')

    @staticmethod
    def get_user_returns(user, status: str = None) -> List[ReturnRequest]:
        queryset = ReturnRequest.objects.filter(user=user).select_related('order').prefetch_related('items')
        if status:
            queryset = queryset.filter(status=status)
        return list(queryset.order_by('-created_at'))

    @staticmethod
    @transaction.atomic
    def create_return(user, order, reason: str, description: str, items: List[Dict], refund_method: str = 'original', bank_info: Dict = None) -> ReturnRequest:
        from apps.commerce.orders.models import Order
        if order.status not in [Order.Status.DELIVERED, Order.Status.COMPLETED]:
            raise BusinessRuleViolation(message='Order must be delivered first')
        existing = ReturnRequest.objects.filter(order=order, status__in=[ReturnRequest.Status.PENDING, ReturnRequest.Status.REVIEWING, ReturnRequest.Status.APPROVED]).exists()
        if existing:
            raise BusinessRuleViolation(message='Return request already exists for this order')
        requested_refund = sum(item.get('refund_amount', 0) for item in items)
        return_request = ReturnRequest.objects.create(user=user, order=order, reason=reason, description=description, refund_method=refund_method, requested_refund=requested_refund, bank_name=bank_info.get('bank_name', '') if bank_info else '', bank_account_number=bank_info.get('account_number', '') if bank_info else '', bank_account_name=bank_info.get('account_name', '') if bank_info else '')
        for item_data in items:
            ReturnItem.objects.create(return_request=return_request, order_item_id=item_data['order_item_id'], quantity=item_data.get('quantity', 1), reason=item_data.get('reason', ''), notes=item_data.get('notes', ''), refund_amount=item_data.get('refund_amount', 0))
        ReturnStatusHistory.objects.create(return_request=return_request, status=ReturnRequest.Status.PENDING, changed_by=user, notes='Return request created')
        logger.info(f"Return request created: {return_request.request_number}")
        return return_request

    @staticmethod
    def cancel_return(return_request: ReturnRequest, user, reason: str = '') -> ReturnRequest:
        if not return_request.can_cancel:
            raise BusinessRuleViolation(message='Cannot cancel return in current status')
        return_request.cancel(user, reason)
        logger.info(f"Return cancelled: {return_request.request_number}")
        return return_request

    @staticmethod
    def add_image(return_request: ReturnRequest, image, caption: str = '', user=None) -> ReturnImage:
        return ReturnImage.objects.create(return_request=return_request, image=image, caption=caption, uploaded_by=user)

    @staticmethod
    @transaction.atomic
    def approve_return(return_request: ReturnRequest, admin_user, approved_refund: Decimal, notes: str = '') -> ReturnRequest:
        if not return_request.can_approve:
            raise BusinessRuleViolation(message='Cannot approve return in current status')
        return_request.approve(admin_user, approved_refund, notes)
        logger.info(f"Return approved: {return_request.request_number}")
        return return_request

    @staticmethod
    @transaction.atomic
    def reject_return(return_request: ReturnRequest, admin_user, reason: str) -> ReturnRequest:
        if not return_request.can_approve:
            raise BusinessRuleViolation(message='Cannot reject return in current status')
        return_request.reject(admin_user, reason)
        logger.info(f"Return rejected: {return_request.request_number}")
        return return_request

    @staticmethod
    @transaction.atomic
    def receive_items(return_request: ReturnRequest, admin_user, quality_passed: bool, notes: str = '') -> ReturnRequest:
        if not return_request.can_receive:
            raise BusinessRuleViolation(message='Cannot receive items in current status')
        return_request.receive_items(admin_user, quality_passed, notes)
        logger.info(f"Return items received: {return_request.request_number}")
        return return_request

    @staticmethod
    @transaction.atomic
    def complete_return(return_request: ReturnRequest, admin_user) -> ReturnRequest:
        return_request.complete(admin_user)
        logger.info(f"Return completed: {return_request.request_number}")
        return return_request


class ReturnStatisticsService:
    @staticmethod
    def get_statistics(days: int = 30) -> Dict[str, Any]:
        since = timezone.now() - timezone.timedelta(days=days)
        queryset = ReturnRequest.objects.filter(created_at__gte=since)
        stats = queryset.aggregate(total=Count('id'), pending=Count('id', filter=Q(status=ReturnRequest.Status.PENDING)), approved=Count('id', filter=Q(status=ReturnRequest.Status.APPROVED)), rejected=Count('id', filter=Q(status=ReturnRequest.Status.REJECTED)), completed=Count('id', filter=Q(status=ReturnRequest.Status.COMPLETED)), total_refunded=Sum('approved_refund', filter=Q(status=ReturnRequest.Status.COMPLETED)))
        total = stats['total'] or 1
        by_reason = queryset.values('reason').annotate(count=Count('id')).order_by('-count')
        return {'period_days': days, 'total_returns': stats['total'] or 0, 'pending': stats['pending'] or 0, 'approved': stats['approved'] or 0, 'rejected': stats['rejected'] or 0, 'completed': stats['completed'] or 0, 'total_refunded': stats['total_refunded'] or 0, 'approval_rate': round((stats['approved'] or 0) / total * 100, 2), 'by_reason': list(by_reason)}
