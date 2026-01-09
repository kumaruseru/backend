"""Commerce Shipping - API Views."""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from apps.commerce.orders.models import Order
from .models import Shipment, CODReconciliation
from .serializers import (
    ShipmentSerializer, ShipmentListSerializer, ShipmentTrackingSerializer,
    ShipmentEventSerializer, DeliveryAttemptSerializer,
    ShipmentCreateSerializer, ShipmentStatusUpdateSerializer, DeliveryAttemptCreateSerializer,
    CalculateFeeSerializer, FeeResponseSerializer,
    CODReconciliationSerializer, ShippingStatisticsSerializer
)
from .services import ShipmentService, ShippingCalculatorService, CODService, ShippingStatisticsService


class ShipmentTrackingView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: ShipmentTrackingSerializer}, tags=['Shipping'])
    def get(self, request, tracking_code):
        try:
            shipment = ShipmentService.get_by_tracking(tracking_code)
            return Response(ShipmentTrackingSerializer(shipment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class CalculateFeeView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=CalculateFeeSerializer, responses={200: FeeResponseSerializer}, tags=['Shipping'])
    def post(self, request):
        serializer = CalculateFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = ShippingCalculatorService.calculate_fee(provider=data['provider'], district_id=data['district_id'], ward_code=data['ward_code'], weight=data['weight'], cod_amount=data.get('cod_amount', 0))
        return Response(result)


class AdminShipmentListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ShipmentListSerializer

    def get_queryset(self):
        queryset = Shipment.objects.select_related('order')
        status_filter = self.request.query_params.get('status')
        provider = self.request.query_params.get('provider')
        search = self.request.query_params.get('search')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if provider:
            queryset = queryset.filter(provider=provider)
        if search:
            queryset = queryset.filter(tracking_code__icontains=search)
        return queryset.order_by('-created_at')

    @extend_schema(parameters=[OpenApiParameter('status', str), OpenApiParameter('provider', str), OpenApiParameter('search', str)], tags=['Shipping - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminShipmentDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: ShipmentSerializer}, tags=['Shipping - Admin'])
    def get(self, request, shipment_id):
        try:
            shipment = ShipmentService.get_shipment(shipment_id)
            return Response(ShipmentSerializer(shipment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminShipmentCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ShipmentCreateSerializer, responses={201: ShipmentSerializer}, tags=['Shipping - Admin'])
    def post(self, request):
        serializer = ShipmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            order = Order.objects.get(id=data['order_id'])
            shipment = ShipmentService.create_shipment(order=order, provider=data['provider'], tracking_code=data.get('tracking_code', ''), cod_amount=data.get('cod_amount', 0), weight=data.get('weight', 500), note=data.get('note', ''))
            return Response(ShipmentSerializer(shipment).data, status=status.HTTP_201_CREATED)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminShipmentUpdateStatusView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ShipmentStatusUpdateSerializer, responses={200: ShipmentSerializer}, tags=['Shipping - Admin'])
    def post(self, request, shipment_id):
        serializer = ShipmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            shipment = ShipmentService.get_shipment(shipment_id)
            ShipmentService.update_status(shipment=shipment, new_status=data['status'], provider_status=data.get('provider_status', ''), location=data.get('location', ''), description=data.get('description', ''))
            shipment.refresh_from_db()
            return Response(ShipmentSerializer(shipment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminShipmentCancelView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(tags=['Shipping - Admin'])
    def post(self, request, shipment_id):
        reason = request.data.get('reason', '')
        try:
            shipment = ShipmentService.get_shipment(shipment_id)
            ShipmentService.cancel_shipment(shipment, reason)
            return Response(ShipmentSerializer(shipment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminDeliveryAttemptView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=DeliveryAttemptCreateSerializer, responses={201: DeliveryAttemptSerializer}, tags=['Shipping - Admin'])
    def post(self, request, shipment_id):
        serializer = DeliveryAttemptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            shipment = ShipmentService.get_shipment(shipment_id)
            attempt = ShipmentService.record_delivery_attempt(shipment=shipment, fail_reason=data['fail_reason'], notes=data.get('notes', ''), rescheduled_to=data.get('rescheduled_to'))
            return Response(DeliveryAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminActiveShipmentsView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ShipmentListSerializer

    def get_queryset(self):
        provider = self.request.query_params.get('provider')
        return ShipmentService.get_active_shipments(provider)

    @extend_schema(parameters=[OpenApiParameter('provider', str)], tags=['Shipping - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminFailedShipmentsView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ShipmentListSerializer

    def get_queryset(self):
        return ShipmentService.get_failed_shipments()

    @extend_schema(tags=['Shipping - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminPendingCODView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ShipmentListSerializer

    def get_queryset(self):
        return ShipmentService.get_pending_cod()

    @extend_schema(tags=['Shipping - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminStatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(parameters=[OpenApiParameter('days', int)], responses={200: ShippingStatisticsSerializer}, tags=['Shipping - Admin'])
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        stats = ShippingStatisticsService.get_statistics(days)
        return Response(stats)
