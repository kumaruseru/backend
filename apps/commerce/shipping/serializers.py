"""Commerce Shipping - Serializers."""
from rest_framework import serializers
from .models import Shipment, ShipmentEvent, DeliveryAttempt, CODReconciliation


class ShipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = ['id', 'status', 'description', 'location', 'occurred_at']


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    fail_reason_display = serializers.CharField(source='get_fail_reason_display', read_only=True)

    class Meta:
        model = DeliveryAttempt
        fields = ['id', 'attempt_number', 'attempted_at', 'fail_reason', 'fail_reason_display', 'notes', 'rescheduled_to']


class ShipmentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    events = ShipmentEventSerializer(many=True, read_only=True)
    is_delivered = serializers.ReadOnlyField()
    is_failed = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    is_final = serializers.ReadOnlyField()
    can_cancel = serializers.ReadOnlyField()
    can_retry = serializers.ReadOnlyField()
    days_in_transit = serializers.ReadOnlyField()
    tracking_url = serializers.ReadOnlyField()

    class Meta:
        model = Shipment
        fields = ['id', 'order', 'order_number', 'provider', 'provider_display', 'tracking_code', 'status', 'status_display', 'provider_status', 'weight', 'shipping_fee', 'cod_amount', 'cod_collected', 'cod_transferred', 'expected_delivery', 'delivery_attempts', 'picked_up_at', 'delivered_at', 'returned_at', 'last_location', 'fail_reason', 'is_delivered', 'is_failed', 'is_active', 'is_final', 'can_cancel', 'can_retry', 'days_in_transit', 'tracking_url', 'events', 'created_at', 'updated_at']


class ShipmentListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Shipment
        fields = ['id', 'order_number', 'tracking_code', 'provider', 'provider_display', 'status', 'status_display', 'cod_amount', 'expected_delivery', 'created_at']


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    events = ShipmentEventSerializer(many=True, read_only=True)
    tracking_url = serializers.ReadOnlyField()

    class Meta:
        model = Shipment
        fields = ['tracking_code', 'provider', 'provider_display', 'status', 'status_display', 'expected_delivery', 'picked_up_at', 'delivered_at', 'last_location', 'tracking_url', 'events']


class ShipmentCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=Shipment.Provider.choices, default='ghn')
    tracking_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    cod_amount = serializers.DecimalField(max_digits=12, decimal_places=0, default=0)
    weight = serializers.IntegerField(min_value=1, default=500)
    note = serializers.CharField(required=False, allow_blank=True)


class ShipmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Shipment.Status.choices)
    provider_status = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class DeliveryAttemptCreateSerializer(serializers.Serializer):
    fail_reason = serializers.ChoiceField(choices=DeliveryAttempt.FailReason.choices)
    notes = serializers.CharField(required=False, allow_blank=True)
    rescheduled_to = serializers.DateTimeField(required=False, allow_null=True)


class CalculateFeeSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=Shipment.Provider.choices, default='ghn')
    district_id = serializers.IntegerField()
    ward_code = serializers.CharField()
    weight = serializers.IntegerField(min_value=1, default=500)
    cod_amount = serializers.DecimalField(max_digits=12, decimal_places=0, default=0)


class FeeResponseSerializer(serializers.Serializer):
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=0)
    cod_fee = serializers.DecimalField(max_digits=12, decimal_places=0)
    insurance_fee = serializers.DecimalField(max_digits=12, decimal_places=0)
    total_fee = serializers.DecimalField(max_digits=12, decimal_places=0)


class CODReconciliationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)

    class Meta:
        model = CODReconciliation
        fields = ['id', 'provider', 'provider_display', 'reconciliation_date', 'status', 'status_display', 'total_orders', 'total_cod', 'total_shipping_fee', 'net_amount', 'transferred_at', 'transfer_reference', 'created_at']


class ShippingStatisticsSerializer(serializers.Serializer):
    period_days = serializers.IntegerField()
    total_shipments = serializers.IntegerField()
    delivered = serializers.IntegerField()
    failed = serializers.IntegerField()
    returned = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    delivery_rate = serializers.FloatField()
    total_cod_collected = serializers.DecimalField(max_digits=15, decimal_places=0)
    pending_cod_transfer = serializers.DecimalField(max_digits=15, decimal_places=0)
