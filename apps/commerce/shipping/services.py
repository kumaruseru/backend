"""Commerce Shipping - Application Services."""
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Sum, Q

from apps.common.core.exceptions import NotFoundError, BusinessRuleViolation
from .models import Shipment, ShipmentEvent, DeliveryAttempt, CODReconciliation

logger = logging.getLogger('apps.shipping')


class ShipmentService:
    @staticmethod
    def get_shipment(shipment_id: UUID) -> Shipment:
        try:
            return Shipment.objects.select_related('order').prefetch_related('events').get(id=shipment_id)
        except Shipment.DoesNotExist:
            raise NotFoundError(message='Shipment not found')

    @staticmethod
    def get_by_tracking(tracking_code: str) -> Shipment:
        try:
            return Shipment.objects.select_related('order').prefetch_related('events').get(tracking_code=tracking_code)
        except Shipment.DoesNotExist:
            raise NotFoundError(message='Shipment not found')

    @staticmethod
    def get_by_order(order_id: UUID) -> Optional[Shipment]:
        return Shipment.objects.filter(order_id=order_id).first()

    @staticmethod
    @transaction.atomic
    def create_shipment(order, provider: str = 'ghn', tracking_code: str = '', cod_amount: Decimal = 0, weight: int = 500, note: str = '', **kwargs) -> Shipment:
        if Shipment.objects.filter(order=order).exists():
            raise BusinessRuleViolation(message='Shipment already exists for this order')
        if not tracking_code:
            import uuid
            tracking_code = f"SHP{str(uuid.uuid4())[:8].upper()}"
        shipment = Shipment.objects.create(order=order, provider=provider, tracking_code=tracking_code, cod_amount=cod_amount, weight=weight, note=note, **kwargs)
        ShipmentEvent.objects.create(shipment=shipment, status='created', description='Shipment created', occurred_at=timezone.now())
        logger.info(f"Shipment created: {tracking_code} for order {order.order_number}")
        return shipment

    @staticmethod
    @transaction.atomic
    def update_status(shipment: Shipment, new_status: str, provider_status: str = '', location: str = '', description: str = '', timestamp=None) -> ShipmentEvent:
        shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
        event = shipment.update_status(new_status, provider_status, location, description, timestamp)
        logger.info(f"Shipment {shipment.tracking_code} status updated to {new_status}")
        return event

    @staticmethod
    def cancel_shipment(shipment: Shipment, reason: str = '') -> bool:
        if not shipment.can_cancel:
            raise BusinessRuleViolation(message='Cannot cancel shipment in current status')
        result = shipment.cancel(reason)
        if result:
            logger.info(f"Shipment {shipment.tracking_code} cancelled")
        return result

    @staticmethod
    def get_active_shipments(provider: str = None) -> List[Shipment]:
        queryset = Shipment.objects.filter(status__in=[Shipment.Status.PENDING, Shipment.Status.PICKING, Shipment.Status.PICKED_UP, Shipment.Status.IN_TRANSIT, Shipment.Status.SORTING, Shipment.Status.OUT_FOR_DELIVERY]).select_related('order')
        if provider:
            queryset = queryset.filter(provider=provider)
        return list(queryset.order_by('-created_at'))

    @staticmethod
    def get_failed_shipments() -> List[Shipment]:
        return list(Shipment.objects.filter(status__in=[Shipment.Status.FAILED, Shipment.Status.EXCEPTION]).select_related('order').order_by('-updated_at'))

    @staticmethod
    def get_pending_cod() -> List[Shipment]:
        return list(Shipment.objects.filter(status=Shipment.Status.DELIVERED, cod_amount__gt=0, cod_transferred=False).select_related('order').order_by('delivered_at'))

    @staticmethod
    @transaction.atomic
    def record_delivery_attempt(shipment: Shipment, fail_reason: str, notes: str = '', rescheduled_to=None) -> DeliveryAttempt:
        attempt = DeliveryAttempt.objects.create(shipment=shipment, attempt_number=shipment.delivery_attempts + 1, attempted_at=timezone.now(), fail_reason=fail_reason, notes=notes, rescheduled_to=rescheduled_to)
        shipment.mark_failed(fail_reason)
        return attempt


class ShippingCalculatorService:
    @staticmethod
    def calculate_fee(provider: str, district_id: int, ward_code: str, weight: int, cod_amount: Decimal = 0) -> Dict[str, Decimal]:
        base_fee = Decimal('30000')
        if weight > 500:
            extra_weight = weight - 500
            base_fee += Decimal(extra_weight // 500 * 5000)
        cod_fee = Decimal('0')
        if cod_amount > 0:
            cod_fee = max(Decimal('10000'), cod_amount * Decimal('0.01'))
        return {'shipping_fee': base_fee, 'cod_fee': cod_fee, 'insurance_fee': Decimal('0'), 'total_fee': base_fee + cod_fee}

    @staticmethod
    def get_available_services(district_id: int, ward_code: str) -> List[Dict[str, Any]]:
        return [{'service_id': 1, 'name': 'Standard', 'fee': 30000, 'expected_days': '3-5'}, {'service_id': 2, 'name': 'Express', 'fee': 50000, 'expected_days': '1-2'}]


class CODService:
    @staticmethod
    def get_pending_reconciliation(provider: str) -> List[Shipment]:
        return list(Shipment.objects.filter(provider=provider, status=Shipment.Status.DELIVERED, cod_amount__gt=0, cod_transferred=False).order_by('delivered_at'))

    @staticmethod
    @transaction.atomic
    def create_reconciliation(provider: str, date, shipment_ids: List[UUID]) -> CODReconciliation:
        shipments = Shipment.objects.filter(id__in=shipment_ids, provider=provider, cod_transferred=False)
        total_cod = sum(s.cod_amount for s in shipments)
        total_shipping = sum(s.total_fee for s in shipments)
        net_amount = total_cod - total_shipping
        recon = CODReconciliation.objects.create(provider=provider, reconciliation_date=date, total_orders=shipments.count(), total_cod=total_cod, total_shipping_fee=total_shipping, net_amount=net_amount)
        recon.shipments.set(shipments)
        return recon

    @staticmethod
    @transaction.atomic
    def mark_transferred(recon: CODReconciliation, reference: str = '') -> None:
        recon.status = CODReconciliation.Status.TRANSFERRED
        recon.transferred_at = timezone.now()
        recon.transfer_reference = reference
        recon.save()
        recon.shipments.update(cod_transferred=True, cod_transfer_date=timezone.now().date())


class ShippingStatisticsService:
    @staticmethod
    def get_statistics(days: int = 30) -> Dict[str, Any]:
        since = timezone.now() - timezone.timedelta(days=days)
        queryset = Shipment.objects.filter(created_at__gte=since)
        stats = queryset.aggregate(total=Count('id'), delivered=Count('id', filter=Q(status=Shipment.Status.DELIVERED)), failed=Count('id', filter=Q(status=Shipment.Status.FAILED)), returned=Count('id', filter=Q(status=Shipment.Status.RETURNED)), cancelled=Count('id', filter=Q(status=Shipment.Status.CANCELLED)), total_cod=Sum('cod_amount', filter=Q(cod_collected=True)), pending_cod=Sum('cod_amount', filter=Q(cod_collected=True, cod_transferred=False)))
        total = stats['total'] or 1
        return {'period_days': days, 'total_shipments': stats['total'] or 0, 'delivered': stats['delivered'] or 0, 'failed': stats['failed'] or 0, 'returned': stats['returned'] or 0, 'cancelled': stats['cancelled'] or 0, 'delivery_rate': round((stats['delivered'] or 0) / total * 100, 2), 'total_cod_collected': stats['total_cod'] or 0, 'pending_cod_transfer': stats['pending_cod'] or 0}
