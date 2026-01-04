"""
GHN Data Adapter - Data Transformation Layer.

This adapter is responsible for:
- Transforming system data to GHN API format
- Transforming GHN responses to system format
- Status code mapping
- Error normalization

No HTTP communication here - that's the client's job.
"""
import logging
from typing import Dict, Any, Optional
from apps.commerce.orders.models import Order

logger = logging.getLogger('apps.shipping.ghn')


class GHNAdapter:
    """
    Data transformation adapter for GHN API.
    
    Converts between internal system format and GHN API format.
    """
    
    # GHN Status Code Mapping to Internal Status
    STATUS_MAPPING = {
        'ready_to_pick': 'pending',
        'picking': 'pending',
        'picked': 'picked_up',
        'storing': 'in_transit',
        'transporting': 'in_transit',
        'sorting': 'sorting',
        'delivering': 'out_for_delivery',
        'delivered': 'delivered',
        'delivery_fail': 'failed',
        'return': 'return_in_progress',
        'returned': 'returned',
        'cancel': 'cancelled',
        'exception': 'exception',
        'lost': 'lost',
        'damage': 'damaged'
    }
    
    # Required Note Codes
    REQUIRED_NOTES = {
        'CHOTHUHANG': 'Cho thử hàng',
        'CHOXEMHANGKHONGTHU': 'Cho xem hàng, không cho thử',
        'KHONGCHOXEMHANG': 'Không cho xem hàng'
    }
    
    @classmethod
    def order_to_ghn_payload(
        cls,
        order: Order,
        weight: int = None,
        note: str = '',
        required_note: str = 'CHOTHUHANG',
        service_id: int = None
    ) -> Dict[str, Any]:
        """
        Transform Order to GHN create order payload.
        
        Args:
            order: Order instance
            weight: Package weight in grams
            note: Delivery note
            required_note: GHN required note code
            service_id: GHN service ID
            
        Returns:
            Dict ready for GHN API
        """
        from django.conf import settings
        
        # Calculate COD
        is_cod = order.payment_method == Order.PaymentMethod.COD
        cod_amount = int(order.total) if is_cod else 0
        
        # Build items list
        items = []
        for item in order.items.all():
            items.append({
                'name': item.product_name[:50],  # GHN limit
                'code': item.product_sku or '',
                'quantity': item.quantity,
                'price': int(item.unit_price),
                'weight': 200,  # Default item weight
            })
        
        # Calculate total weight
        total_weight = weight or (len(items) * 200) or 500
        
        payload = {
            'shop_id': int(getattr(settings, 'GHN_SHOP_ID', '')),
            'from_name': getattr(settings, 'GHN_FROM_NAME', 'Shop'),
            'from_phone': getattr(settings, 'GHN_FROM_PHONE', ''),
            'from_address': getattr(settings, 'GHN_FROM_ADDRESS', ''),
            'from_ward_name': getattr(settings, 'GHN_FROM_WARD_NAME', ''),
            'from_district_name': getattr(settings, 'GHN_FROM_DISTRICT_NAME', ''),
            'from_province_name': getattr(settings, 'GHN_FROM_PROVINCE_NAME', ''),
            
            'to_name': order.recipient_name,
            'to_phone': order.recipient_phone,
            'to_address': order.shipping_address,
            'to_ward_code': str(order.ward_code or ''),
            'to_district_id': order.district_id,
            
            'weight': total_weight,
            'length': 20,
            'width': 15,
            'height': 10,
            
            'service_type_id': 2,  # E-commerce
            'payment_type_id': 2 if is_cod else 1,
            'required_note': required_note,
            'note': note or order.guest_note or '',
            
            'cod_amount': cod_amount,
            'insurance_value': min(int(order.subtotal), 5000000),
            
            'items': items,
            'client_order_code': order.order_number,
        }
        
        if service_id:
            payload['service_id'] = service_id
        
        return payload
    
    @classmethod
    def parse_create_response(cls, response: Dict) -> Dict[str, Any]:
        """
        Parse GHN create order response.
        
        Returns normalized data with tracking_code, expected_delivery, etc.
        """
        data = response.get('data', {})
        
        return {
            'tracking_code': data.get('order_code', ''),
            'provider_order_id': data.get('order_code', ''),
            'expected_delivery_time': data.get('expected_delivery_time'),
            'total_fee': data.get('total_fee', 0),
            'service_fee': data.get('service_fee', 0),
            'insurance_fee': data.get('insurance_fee', 0),
            'cod_fee': data.get('cod_fee', 0),
            'raw_response': data
        }
    
    @classmethod
    def parse_fee_response(cls, response: Dict) -> Dict[str, Any]:
        """Parse GHN calculate fee response."""
        data = response.get('data', {})
        
        return {
            'total_fee': data.get('total', 0),
            'service_fee': data.get('service_fee', 0),
            'insurance_fee': data.get('insurance_fee', 0),
            'cod_fee': 0,  # COD fee calculated separately
            'raw_response': data
        }
    
    @classmethod
    def parse_webhook_payload(cls, payload: Dict) -> Dict[str, Any]:
        """
        Parse GHN webhook payload.
        
        Normalizes status codes and extracts relevant data.
        """
        ghn_status = payload.get('Status', '').lower()
        internal_status = cls.STATUS_MAPPING.get(ghn_status, 'unknown')
        
        return {
            'tracking_code': payload.get('OrderCode', ''),
            'ghn_status': ghn_status,
            'status': internal_status,
            'client_order_code': payload.get('ClientOrderCode', ''),
            'warehouse': payload.get('Warehouse', ''),
            'description': payload.get('Description', ''),
            'reason': payload.get('Reason', ''),
            'reason_code': payload.get('ReasonCode', ''),
            'cod_collected': payload.get('CODCollected', False),
            'cod_amount': payload.get('CODAmount', 0),
            'cod_transfer_date': payload.get('CODTransferDate'),
            'weight': payload.get('Weight', 0),
            'updated_at': payload.get('Time'),
            'raw_payload': payload
        }
    
    @classmethod
    def is_final_status(cls, status: str) -> bool:
        """Check if status is terminal (no more updates expected)."""
        final_statuses = ['delivered', 'returned', 'cancelled', 'lost', 'damaged']
        return status in final_statuses
