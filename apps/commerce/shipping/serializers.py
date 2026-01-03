"""
Commerce Shipping - Production-Ready Serializers.

Comprehensive DTOs with nested event serialization
and validation.
"""
from rest_framework import serializers
from .models import Shipment, ShipmentEvent, DeliveryAttempt, CODReconciliation


# --- Output Serializers ---

class ShipmentEventSerializer(serializers.ModelSerializer):
    """Tracking event DTO."""
    
    class Meta:
        model = ShipmentEvent
        fields = [
            'id', 'status', 'description', 'location',
            'occurred_at', 'created_at'
        ]


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    """Delivery attempt DTO."""
    fail_reason_display = serializers.CharField(
        source='get_fail_reason_display',
        read_only=True
    )
    
    class Meta:
        model = DeliveryAttempt
        fields = [
            'id', 'attempt_number', 'attempted_at',
            'fail_reason', 'fail_reason_display',
            'notes', 'rescheduled_to'
        ]


class ShipmentSerializer(serializers.ModelSerializer):
    """Full shipment output DTO."""
    order_number = serializers.CharField(
        source='order.order_number',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    provider_display = serializers.CharField(
        source='get_provider_display',
        read_only=True
    )
    events = ShipmentEventSerializer(many=True, read_only=True)
    attempt_logs = DeliveryAttemptSerializer(many=True, read_only=True)
    
    # Computed
    is_delivered = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    is_final = serializers.ReadOnlyField()
    can_cancel = serializers.ReadOnlyField()
    days_in_transit = serializers.ReadOnlyField()
    tracking_url = serializers.ReadOnlyField()
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'order', 'order_number',
            'provider', 'provider_display',
            'tracking_code', 'provider_order_id',
            'status', 'status_display', 'provider_status',
            'weight', 'dimensions',
            'shipping_fee', 'insurance_fee', 'cod_fee', 'total_fee',
            'cod_amount', 'cod_collected', 'cod_transferred',
            'service_type', 'expected_delivery',
            'delivery_attempts', 'max_delivery_attempts',
            'note', 'fail_reason', 'cancel_reason',
            'picked_up_at', 'delivered_at', 'returned_at',
            'last_location', 'last_status_update',
            'is_delivered', 'is_active', 'is_final', 'can_cancel',
            'days_in_transit', 'tracking_url',
            'events', 'attempt_logs',
            'created_at', 'updated_at'
        ]


class ShipmentListSerializer(serializers.ModelSerializer):
    """Simplified shipment for listing."""
    order_number = serializers.CharField(
        source='order.order_number',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    provider_display = serializers.CharField(
        source='get_provider_display',
        read_only=True
    )
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'order_number', 'tracking_code',
            'provider', 'provider_display',
            'status', 'status_display',
            'cod_amount', 'cod_collected',
            'expected_delivery', 'delivered_at',
            'created_at'
        ]


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    """Public tracking info (limited fields)."""
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    provider_display = serializers.CharField(
        source='get_provider_display',
        read_only=True
    )
    events = ShipmentEventSerializer(many=True, read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'tracking_code', 'provider_display',
            'status', 'status_display',
            'expected_delivery', 'delivered_at',
            'last_location', 'events'
        ]


# --- Input Serializers ---

class ShippingFeeRequestSerializer(serializers.Serializer):
    """Shipping fee calculation input."""
    district_id = serializers.IntegerField(required=True, min_value=1)
    ward_code = serializers.CharField(required=True, max_length=20)
    weight = serializers.IntegerField(default=500, min_value=1, max_value=50000)
    insurance_value = serializers.IntegerField(default=0, min_value=0)
    cod_amount = serializers.IntegerField(default=0, min_value=0)


class ShippingFeeResponseSerializer(serializers.Serializer):
    """Shipping fee calculation output."""
    success = serializers.BooleanField()
    total = serializers.IntegerField(required=False)
    service_fee = serializers.IntegerField(required=False)
    insurance_fee = serializers.IntegerField(required=False)
    cod_fee = serializers.IntegerField(required=False)
    service_id = serializers.IntegerField(required=False)
    expected_delivery_time = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class CreateShipmentSerializer(serializers.Serializer):
    """Create shipment input."""
    order_id = serializers.UUIDField(required=True)
    weight = serializers.IntegerField(required=False, min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    auto_create_ghn = serializers.BooleanField(default=True)


class CancelShipmentSerializer(serializers.Serializer):
    """Cancel shipment input."""
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


# --- Location Serializers ---

class ProvinceSerializer(serializers.Serializer):
    """Province DTO from GHN."""
    ProvinceID = serializers.IntegerField()
    ProvinceName = serializers.CharField()
    Code = serializers.CharField(required=False)
    NameExtension = serializers.ListField(required=False)


class DistrictSerializer(serializers.Serializer):
    """District DTO from GHN."""
    DistrictID = serializers.IntegerField()
    DistrictName = serializers.CharField()
    ProvinceID = serializers.IntegerField()
    Code = serializers.CharField(required=False)


class WardSerializer(serializers.Serializer):
    """Ward DTO from GHN."""
    WardCode = serializers.CharField()
    WardName = serializers.CharField()
    DistrictID = serializers.IntegerField()


# --- Webhook Serializers ---

class GHNWebhookSerializer(serializers.Serializer):
    """GHN webhook payload DTO."""
    OrderCode = serializers.CharField()
    Status = serializers.CharField()
    Description = serializers.CharField(required=False, allow_blank=True)
    Reason = serializers.CharField(required=False, allow_blank=True)
    ReasonCode = serializers.CharField(required=False, allow_blank=True)
    Warehouse = serializers.CharField(required=False, allow_blank=True)
    Weight = serializers.IntegerField(required=False, allow_null=True)
    Fee = serializers.IntegerField(required=False, allow_null=True)
    CODAmount = serializers.IntegerField(required=False, allow_null=True)
    CODTransferDate = serializers.CharField(required=False, allow_null=True)
    Time = serializers.DateTimeField(required=False, allow_null=True)


# --- COD Serializers ---

class CODReconciliationSerializer(serializers.ModelSerializer):
    """COD reconciliation DTO."""
    provider_display = serializers.CharField(
        source='get_provider_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    class Meta:
        model = CODReconciliation
        fields = [
            'id', 'provider', 'provider_display',
            'reconciliation_date', 'status', 'status_display',
            'total_orders', 'total_cod', 'total_shipping_fee', 'net_amount',
            'transferred_at', 'transfer_reference', 'notes',
            'created_at'
        ]


# --- Statistics Serializers ---

class ShippingStatisticsSerializer(serializers.Serializer):
    """Shipping statistics output."""
    period_days = serializers.IntegerField()
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    in_transit = serializers.IntegerField()
    out_for_delivery = serializers.IntegerField()
    delivered = serializers.IntegerField()
    failed = serializers.IntegerField()
    returned = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    delivery_rate = serializers.FloatField()
    total_cod_collected = serializers.IntegerField()
    total_shipping_fee = serializers.IntegerField()
