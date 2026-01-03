"""
Commerce Shipping - Production-Ready Services.

Comprehensive shipping services with:
- Shipment creation and management
- GHN API integration
- Webhook processing
- COD reconciliation
- Multi-provider support
"""
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from uuid import UUID
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import requests

from apps.common.core.exceptions import (
    NotFoundError, BusinessRuleViolation, ExternalServiceError
)
from apps.commerce.orders.models import Order
from .models import Shipment, ShipmentEvent, DeliveryAttempt, CODReconciliation

logger = logging.getLogger('apps.shipping')


class GHNService:
    """
    Giao Hang Nhanh (GHN) shipping provider.
    
    Production-ready integration with:
    - Shipping fee calculation
    - Order creation
    - Webhook processing
    - Tracking
    - Order cancellation
    """
    
    PRODUCTION_URL = 'https://online-gateway.ghn.vn/shiip/public-api'
    SANDBOX_URL = 'https://dev-online-gateway.ghn.vn/shiip/public-api'
    
    # Status mapping
    STATUS_MAP = {
        'ready_to_pick': Shipment.Status.PENDING,
        'picking': Shipment.Status.PICKING,
        'money_collect_picking': Shipment.Status.PICKING,
        'picked': Shipment.Status.PICKED_UP,
        'storing': Shipment.Status.IN_TRANSIT,
        'transporting': Shipment.Status.IN_TRANSIT,
        'sorting': Shipment.Status.SORTING,
        'delivering': Shipment.Status.OUT_FOR_DELIVERY,
        'money_collect_delivering': Shipment.Status.OUT_FOR_DELIVERY,
        'delivered': Shipment.Status.DELIVERED,
        'delivery_fail': Shipment.Status.FAILED,
        'waiting_to_return': Shipment.Status.WAITING_RETURN,
        'return': Shipment.Status.RETURNING,
        'return_transporting': Shipment.Status.RETURNING,
        'return_sorting': Shipment.Status.RETURNING,
        'returning': Shipment.Status.RETURNING,
        'return_fail': Shipment.Status.FAILED,
        'returned': Shipment.Status.RETURNED,
        'cancel': Shipment.Status.CANCELLED,
        'exception': Shipment.Status.EXCEPTION,
        'lost': Shipment.Status.EXCEPTION,
        'damage': Shipment.Status.EXCEPTION,
    }
    
    def __init__(self):
        self.token = getattr(settings, 'GHN_API_TOKEN', '')
        self.shop_id = getattr(settings, 'GHN_SHOP_ID', '')
        self.is_sandbox = getattr(settings, 'GHN_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if self.is_sandbox else self.PRODUCTION_URL
        self.timeout = 30
    
    @property
    def _headers(self) -> Dict[str, str]:
        return {
            'Token': self.token,
            'ShopId': str(self.shop_id),
            'Content-Type': 'application/json'
        }
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        timeout: int = None
    ) -> Dict:
        """Make API request to GHN."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers,
                json=data,
                timeout=timeout or self.timeout
            )
            result = response.json()
            
            if result.get('code') != 200:
                logger.warning(
                    f"GHN API error: {endpoint} - {result.get('message')}",
                    extra={'response': result}
                )
            
            return result
            
        except requests.Timeout:
            logger.error(f"GHN API timeout: {endpoint}")
            raise ExternalServiceError(
                message='GHN API timeout',
                service='GHN'
            )
        except requests.RequestException as e:
            logger.error(f"GHN API request failed: {e}")
            raise ExternalServiceError(
                message=f'GHN API error: {str(e)}',
                service='GHN'
            )
    
    # --- Location APIs ---
    
    def get_provinces(self) -> List[Dict]:
        """Get all provinces."""
        result = self._request('GET', '/master-data/province')
        return result.get('data') or []
    
    def get_districts(self, province_id: int) -> List[Dict]:
        """Get districts of a province."""
        result = self._request('POST', '/master-data/district', {
            'province_id': province_id
        })
        return result.get('data') or []
    
    def get_wards(self, district_id: int) -> List[Dict]:
        """Get wards of a district."""
        result = self._request('POST', '/master-data/ward', {
            'district_id': district_id
        })
        return result.get('data') or []
    
    # --- Service & Fee APIs ---
    
    def get_available_services(self, to_district_id: int) -> List[Dict]:
        """Get available shipping services for destination."""
        result = self._request('POST', '/v2/shipping-order/available-services', {
            'shop_id': int(self.shop_id),
            'to_district': to_district_id
        })
        return result.get('data') or []
    
    def calculate_fee(
        self,
        to_district_id: int,
        to_ward_code: str,
        weight: int = 500,
        insurance_value: int = 0,
        cod_amount: int = 0,
        service_id: int = None
    ) -> Dict[str, Any]:
        """Calculate shipping fee."""
        # Get service if not specified
        if not service_id:
            services = self.get_available_services(to_district_id)
            if not services:
                return {'success': False, 'error': 'No services available'}
            service_id = services[0]['service_id']
        
        result = self._request('POST', '/v2/shipping-order/fee', {
            'service_id': service_id,
            'insurance_value': insurance_value,
            'coupon': None,
            'to_ward_code': to_ward_code,
            'to_district_id': to_district_id,
            'weight': weight,
            'cod_value': cod_amount
        })
        
        if result.get('code') == 200:
            data = result.get('data', {})
            return {
                'success': True,
                'total': data.get('total', 0),
                'service_fee': data.get('service_fee', 0),
                'insurance_fee': data.get('insurance_fee', 0),
                'cod_fee': data.get('cod_fee', 0),
                'service_id': service_id,
                'expected_delivery_time': data.get('expected_delivery_time')
            }
        
        return {
            'success': False,
            'error': result.get('message', 'Unknown error')
        }
    
    # --- Order APIs ---
    
    def create_order(
        self,
        order: Order,
        weight: int = None,
        note: str = '',
        required_note: str = 'CHOTHUHANG',
        service_id: int = None
    ) -> Dict[str, Any]:
        """
        Create shipping order from Order object.
        
        Args:
            order: Order to ship
            weight: Override weight in grams
            note: Delivery note
            required_note: GHN required note code
            service_id: Specific service ID
            
        Returns:
            Dict with order_code and shipment info
        """
        # Calculate weight if not provided
        if not weight:
            weight = order.items.count() * 500  # Estimate 500g per item
        
        # Get service
        if not service_id:
            services = self.get_available_services(order.district_id)
            if services:
                service_id = services[0]['service_id']
        
        # Build items list
        items = []
        for item in order.items.all():
            items.append({
                'name': item.product_name[:50],
                'code': item.product_sku or '',
                'quantity': item.quantity,
                'price': int(item.unit_price),
                'weight': 200  # Estimate per item
            })
        
        # Calculate COD
        cod_amount = 0
        if order.payment_method == Order.PaymentMethod.COD:
            cod_amount = int(order.total)
        
        payload = {
            'payment_type_id': 1,  # Seller pays shipping
            'note': note or order.note or '',
            'required_note': required_note,
            'client_order_code': order.order_number,
            'to_name': order.recipient_name,
            'to_phone': order.phone,
            'to_address': order.address,
            'to_ward_code': order.ward_code,
            'to_district_id': order.district_id,
            'cod_amount': cod_amount,
            'weight': weight,
            'length': 30,
            'width': 20,
            'height': 10,
            'service_id': service_id,
            'service_type_id': 2,
            'items': items
        }
        
        result = self._request('POST', '/v2/shipping-order/create', payload)
        
        if result.get('code') == 200:
            data = result.get('data', {})
            
            logger.info(
                f"GHN order created: {data.get('order_code')} "
                f"for order {order.order_number}"
            )
            
            return {
                'success': True,
                'order_code': data.get('order_code'),
                'sort_code': data.get('sort_code'),
                'expected_delivery': data.get('expected_delivery_time'),
                'total_fee': data.get('total_fee'),
                'service_id': service_id,
                'raw_data': data
            }
        
        logger.warning(
            f"GHN order creation failed for {order.order_number}: "
            f"{result.get('message')}"
        )
        
        return {
            'success': False,
            'error': result.get('message', 'Unknown error'),
            'code': result.get('code')
        }
    
    def get_order_detail(self, order_code: str) -> Dict[str, Any]:
        """Get order details from GHN."""
        result = self._request('POST', '/v2/shipping-order/detail', {
            'order_code': order_code
        })
        
        if result.get('code') == 200:
            return {
                'success': True,
                'data': result.get('data', {})
            }
        
        return {
            'success': False,
            'error': result.get('message', 'Unknown error')
        }
    
    def cancel_order(self, order_codes: List[str]) -> Dict[str, Any]:
        """Cancel shipping orders."""
        result = self._request('POST', '/v2/switch-status/cancel', {
            'order_codes': order_codes
        })
        
        return {
            'success': result.get('code') == 200,
            'message': result.get('message', '')
        }
    
    # --- Webhook Processing ---
    
    def process_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process GHN webhook payload.
        
        Updates shipment status and creates event log.
        
        Args:
            payload: Raw webhook payload
            
        Returns:
            Dict with processed info
        """
        order_code = payload.get('OrderCode')
        ghn_status = payload.get('Status', '').lower()
        
        if not order_code:
            logger.warning("GHN webhook missing OrderCode")
            return {'success': False, 'error': 'Missing OrderCode'}
        
        # Map to internal status
        internal_status = self.STATUS_MAP.get(ghn_status, Shipment.Status.PENDING)
        
        result = {
            'order_code': order_code,
            'ghn_status': ghn_status,
            'status': internal_status,
            'description': payload.get('Description', ''),
            'reason': payload.get('Reason', ''),
            'reason_code': payload.get('ReasonCode', ''),
            'warehouse': payload.get('Warehouse', ''),
            'weight': payload.get('Weight'),
            'fee': payload.get('Fee'),
            'cod_amount': payload.get('CODAmount'),
            'cod_collected': ghn_status == 'delivered',
            'cod_transfer_date': payload.get('CODTransferDate'),
            'timestamp': payload.get('Time'),
            'raw_payload': payload
        }
        
        logger.info(
            f"GHN webhook processed: {order_code} -> {internal_status}",
            extra={'payload': payload}
        )
        
        return result
    
    @staticmethod
    def is_final_status(status: str) -> bool:
        """Check if status is terminal."""
        return status in [
            Shipment.Status.DELIVERED,
            Shipment.Status.RETURNED,
            Shipment.Status.CANCELLED
        ]


class ShippingService:
    """
    Shipping management use cases.
    
    Handles:
    - Shipment creation
    - Status updates
    - Webhook processing
    - COD reconciliation
    """
    
    @staticmethod
    @transaction.atomic
    def create_shipment(
        order: Order,
        weight: int = None,
        note: str = '',
        auto_create_ghn: bool = True
    ) -> Shipment:
        """
        Create shipment for order.
        
        Args:
            order: Order to create shipment for
            weight: Package weight in grams
            note: Delivery note
            auto_create_ghn: Whether to create GHN order
            
        Returns:
            Created Shipment
        """
        # Check if shipment already exists
        if hasattr(order, 'shipment'):
            raise BusinessRuleViolation(
                message='Đơn hàng đã có vận đơn'
            )
        
        # Calculate COD
        cod_amount = Decimal('0')
        if order.payment_method == Order.PaymentMethod.COD:
            cod_amount = order.total
        
        # Create GHN order if enabled
        tracking_code = ''
        shipping_fee = order.shipping_fee
        provider_data = {}
        expected_delivery = None
        service_id = None
        
        if auto_create_ghn:
            ghn = GHNService()
            result = ghn.create_order(order, weight=weight, note=note)
            
            if result['success']:
                tracking_code = result['order_code']
                shipping_fee = Decimal(result.get('total_fee', order.shipping_fee))
                provider_data = result.get('raw_data', {})
                service_id = result.get('service_id')
                
                if result.get('expected_delivery'):
                    from dateutil import parser
                    try:
                        expected_delivery = parser.parse(result['expected_delivery'])
                    except:
                        pass
            else:
                raise ExternalServiceError(
                    message=f"Không thể tạo vận đơn GHN: {result.get('error')}",
                    service='GHN'
                )
        else:
            # Manual tracking code for non-GHN
            import time
            tracking_code = f"MANUAL{int(time.time())}"
        
        # Create shipment
        shipment = Shipment.objects.create(
            order=order,
            provider=Shipment.Provider.GHN if auto_create_ghn else Shipment.Provider.MANUAL,
            tracking_code=tracking_code,
            provider_order_id=tracking_code,
            weight=weight or 500,
            shipping_fee=shipping_fee,
            cod_amount=cod_amount,
            total_fee=shipping_fee,
            provider_data=provider_data,
            expected_delivery=expected_delivery,
            service_id=service_id,
            note=note
        )
        
        # Update order
        order.tracking_code = tracking_code
        order.save(update_fields=['tracking_code', 'updated_at'])
        
        # Create initial event
        ShipmentEvent.objects.create(
            shipment=shipment,
            status='created',
            description='Đã tạo vận đơn',
            location='',
            occurred_at=timezone.now()
        )
        
        logger.info(
            f"Shipment created: {tracking_code} for order {order.order_number}"
        )
        
        return shipment
    
    @staticmethod
    def get_shipment(shipment_id: UUID) -> Shipment:
        """Get shipment by ID."""
        try:
            return Shipment.objects.select_related('order').prefetch_related(
                'events', 'attempt_logs'
            ).get(id=shipment_id)
        except Shipment.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy vận đơn')
    
    @staticmethod
    def get_by_tracking_code(tracking_code: str) -> Shipment:
        """Get shipment by tracking code."""
        try:
            return Shipment.objects.select_related('order').prefetch_related(
                'events'
            ).get(tracking_code=tracking_code)
        except Shipment.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy vận đơn')
    
    @staticmethod
    def get_order_shipments(order_id: UUID) -> List[Shipment]:
        """Get shipments for an order."""
        return list(
            Shipment.objects.filter(order_id=order_id).prefetch_related('events')
        )
    
    @staticmethod
    @transaction.atomic
    def process_webhook(
        provider: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process provider webhook.
        
        Updates shipment and order status based on webhook data.
        """
        if provider != 'ghn':
            return {'success': False, 'error': 'Unsupported provider'}
        
        ghn = GHNService()
        result = ghn.process_webhook(payload)
        
        if not result.get('order_code'):
            return result
        
        tracking_code = result['order_code']
        new_status = result['status']
        
        try:
            shipment = Shipment.objects.select_related('order').get(
                tracking_code=tracking_code
            )
        except Shipment.DoesNotExist:
            logger.warning(f"Shipment not found for webhook: {tracking_code}")
            return {'success': False, 'error': 'Shipment not found'}
        
        old_status = shipment.status
        
        # Update shipment status
        shipment.update_status(
            new_status=new_status,
            provider_status=result['ghn_status'],
            location=result.get('warehouse', ''),
            description=result.get('description', ''),
            timestamp=timezone.now()
        )
        
        # Update COD info
        if result.get('cod_collected'):
            shipment.cod_collected = True
            shipment.save(update_fields=['cod_collected', 'updated_at'])
        
        if result.get('cod_transfer_date'):
            from dateutil import parser
            try:
                shipment.cod_transfer_date = parser.parse(result['cod_transfer_date']).date()
                shipment.cod_transferred = True
                shipment.save(update_fields=['cod_transfer_date', 'cod_transferred', 'updated_at'])
            except:
                pass
        
        # Update order status
        ShippingService._sync_order_status(shipment, new_status, result)
        
        # Create delivery attempt if failed
        if new_status == Shipment.Status.FAILED:
            DeliveryAttempt.objects.create(
                shipment=shipment,
                attempt_number=shipment.delivery_attempts,
                attempted_at=timezone.now(),
                fail_reason=DeliveryAttempt.FailReason.OTHER,
                notes=result.get('reason', '')
            )
        
        logger.info(
            f"Webhook processed: {tracking_code} {old_status} -> {new_status}"
        )
        
        return {
            'success': True,
            'tracking_code': tracking_code,
            'old_status': old_status,
            'new_status': new_status
        }
    
    @staticmethod
    def _sync_order_status(
        shipment: Shipment,
        shipping_status: str,
        webhook_data: Dict
    ) -> None:
        """Sync order status with shipment status."""
        order = shipment.order
        
        status_map = {
            Shipment.Status.PICKED_UP: Order.Status.SHIPPING,
            Shipment.Status.IN_TRANSIT: Order.Status.SHIPPING,
            Shipment.Status.SORTING: Order.Status.SHIPPING,
            Shipment.Status.OUT_FOR_DELIVERY: Order.Status.SHIPPING,
            Shipment.Status.DELIVERED: Order.Status.DELIVERED,
        }
        
        new_order_status = status_map.get(shipping_status)
        
        if new_order_status and order.status != new_order_status:
            if shipping_status == Shipment.Status.DELIVERED:
                order.deliver()
                
                # Mark as paid if COD
                if order.payment_method == Order.PaymentMethod.COD:
                    order.payment_status = Order.PaymentStatus.PAID
                    order.save(update_fields=['payment_status', 'updated_at'])
            
            elif shipping_status in [
                Shipment.Status.PICKED_UP,
                Shipment.Status.IN_TRANSIT,
                Shipment.Status.OUT_FOR_DELIVERY
            ]:
                if order.status == Order.Status.CONFIRMED:
                    order.ship(shipment.tracking_code)
    
    @staticmethod
    def cancel_shipment(shipment: Shipment, reason: str = '') -> Shipment:
        """Cancel a shipment."""
        if not shipment.can_cancel:
            raise BusinessRuleViolation(
                message='Không thể hủy vận đơn ở trạng thái này'
            )
        
        # Cancel with provider
        if shipment.provider == Shipment.Provider.GHN:
            ghn = GHNService()
            result = ghn.cancel_order([shipment.tracking_code])
            
            if not result['success']:
                raise ExternalServiceError(
                    message=f"Không thể hủy vận đơn GHN: {result.get('message')}",
                    service='GHN'
                )
        
        shipment.cancel(reason)
        
        logger.info(f"Shipment cancelled: {shipment.tracking_code}")
        
        return shipment
    
    @staticmethod
    def sync_tracking(shipment: Shipment) -> Shipment:
        """Sync tracking info from provider."""
        if shipment.provider != Shipment.Provider.GHN:
            return shipment
        
        ghn = GHNService()
        result = ghn.get_order_detail(shipment.tracking_code)
        
        if result['success']:
            data = result['data']
            ghn_status = data.get('status', '').lower()
            
            if ghn_status:
                internal_status = GHNService.STATUS_MAP.get(
                    ghn_status,
                    shipment.status
                )
                
                if internal_status != shipment.status:
                    shipment.update_status(
                        new_status=internal_status,
                        provider_status=ghn_status,
                        timestamp=timezone.now()
                    )
            
            # Update provider data
            shipment.provider_data = data
            shipment.save(update_fields=['provider_data', 'updated_at'])
        
        return shipment
    
    # --- Statistics ---
    
    @staticmethod
    def get_statistics(
        days: int = 30,
        provider: str = None
    ) -> Dict[str, Any]:
        """Get shipping statistics."""
        from django.db.models import Count, Sum, Avg
        
        since = timezone.now() - timezone.timedelta(days=days)
        queryset = Shipment.objects.filter(created_at__gte=since)
        
        if provider:
            queryset = queryset.filter(provider=provider)
        
        stats = queryset.aggregate(
            total=Count('id'),
            pending=Count('id', filter=models.Q(status='pending')),
            in_transit=Count('id', filter=models.Q(status__in=['picked_up', 'in_transit', 'sorting'])),
            out_for_delivery=Count('id', filter=models.Q(status='out_for_delivery')),
            delivered=Count('id', filter=models.Q(status='delivered')),
            failed=Count('id', filter=models.Q(status='failed')),
            returned=Count('id', filter=models.Q(status='returned')),
            cancelled=Count('id', filter=models.Q(status='cancelled')),
            total_cod=Sum('cod_amount', filter=models.Q(cod_collected=True)),
            total_shipping_fee=Sum('shipping_fee'),
            avg_delivery_days=Avg('days_in_transit', filter=models.Q(status='delivered'))
        )
        
        # Calculate delivery rate
        delivery_rate = 0
        if stats['total'] > 0:
            delivery_rate = (stats['delivered'] or 0) / stats['total'] * 100
        
        return {
            'period_days': days,
            'total': stats['total'] or 0,
            'pending': stats['pending'] or 0,
            'in_transit': stats['in_transit'] or 0,
            'out_for_delivery': stats['out_for_delivery'] or 0,
            'delivered': stats['delivered'] or 0,
            'failed': stats['failed'] or 0,
            'returned': stats['returned'] or 0,
            'cancelled': stats['cancelled'] or 0,
            'delivery_rate': round(delivery_rate, 2),
            'total_cod_collected': stats['total_cod'] or 0,
            'total_shipping_fee': stats['total_shipping_fee'] or 0
        }


# Import for statistics
from django.db import models
