"""
Commerce Shipping - Production-Ready API Views.

Comprehensive endpoints with:
- Location APIs
- Fee calculation
- Shipment management
- Tracking
- Webhooks
- Statistics
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.common.core.exceptions import DomainException
from apps.commerce.orders.models import Order
from .models import Shipment
from .serializers import (
    ShipmentSerializer, ShipmentListSerializer, ShipmentTrackingSerializer,
    ShippingFeeRequestSerializer, ShippingFeeResponseSerializer,
    CreateShipmentSerializer, CancelShipmentSerializer,
    ProvinceSerializer, DistrictSerializer, WardSerializer,
    GHNWebhookSerializer, ShippingStatisticsSerializer
)
from .services import GHNService, ShippingService


# ==================== PUBLIC ENDPOINTS ====================

class ProvincesView(APIView):
    """Get list of provinces."""
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'location'
    
    @extend_schema(
        responses={200: ProvinceSerializer(many=True)},
        tags=['Shipping - Location']
    )
    def get(self, request):
        """Get all provinces."""
        ghn = GHNService()
        provinces = ghn.get_provinces()
        return Response(provinces)


class DistrictsView(APIView):
    """Get districts of a province."""
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'location'
    
    @extend_schema(
        responses={200: DistrictSerializer(many=True)},
        tags=['Shipping - Location']
    )
    def get(self, request, province_id: int):
        """Get districts for a province."""
        ghn = GHNService()
        districts = ghn.get_districts(province_id)
        return Response(districts)


class WardsView(APIView):
    """Get wards of a district."""
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'location'
    
    @extend_schema(
        responses={200: WardSerializer(many=True)},
        tags=['Shipping - Location']
    )
    def get(self, request, district_id: int):
        """Get wards for a district."""
        ghn = GHNService()
        wards = ghn.get_wards(district_id)
        return Response(wards)


class CalculateFeeView(APIView):
    """Calculate shipping fee."""
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'shipping_calculate'
    
    @extend_schema(
        request=ShippingFeeRequestSerializer,
        responses={200: ShippingFeeResponseSerializer},
        tags=['Shipping']
    )
    def post(self, request):
        """Calculate shipping fee for destination."""
        serializer = ShippingFeeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        ghn = GHNService()
        result = ghn.calculate_fee(
            to_district_id=serializer.validated_data['district_id'],
            to_ward_code=serializer.validated_data['ward_code'],
            weight=serializer.validated_data.get('weight', 500),
            insurance_value=serializer.validated_data.get('insurance_value', 0),
            cod_amount=serializer.validated_data.get('cod_amount', 0)
        )
        
        if result.get('success'):
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class TrackingView(APIView):
    """Public tracking endpoint."""
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'tracking'
    
    @extend_schema(
        responses={200: ShipmentTrackingSerializer},
        tags=['Shipping - Tracking']
    )
    def get(self, request, tracking_code: str):
        """Get tracking info by tracking code."""
        try:
            shipment = ShippingService.get_by_tracking_code(tracking_code)
            return Response(ShipmentTrackingSerializer(shipment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


# ==================== USER ENDPOINTS ====================

class UserShipmentListView(APIView):
    """User's shipments."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: ShipmentListSerializer(many=True)},
        tags=['Shipping - User']
    )
    def get(self, request):
        """Get shipments for user's orders."""
        shipments = Shipment.objects.filter(
            order__user=request.user
        ).select_related('order').order_by('-created_at')[:20]
        
        return Response(ShipmentListSerializer(shipments, many=True).data)


class UserShipmentDetailView(APIView):
    """User's shipment detail."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: ShipmentSerializer},
        tags=['Shipping - User']
    )
    def get(self, request, shipment_id):
        """Get shipment details."""
        try:
            shipment = Shipment.objects.select_related('order').prefetch_related(
                'events', 'attempt_logs'
            ).get(id=shipment_id, order__user=request.user)
            
            return Response(ShipmentSerializer(shipment).data)
        except Shipment.DoesNotExist:
            return Response(
                {'error': 'Shipment not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ==================== ADMIN ENDPOINTS ====================

class AdminShipmentListView(APIView):
    """Admin: List all shipments."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('provider', str, description='Filter by provider'),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: ShipmentListSerializer(many=True)},
        tags=['Shipping - Admin']
    )
    def get(self, request):
        """Get all shipments."""
        queryset = Shipment.objects.select_related('order').order_by('-created_at')
        
        # Filters
        status_filter = request.query_params.get('status')
        provider = request.query_params.get('provider')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if provider:
            queryset = queryset.filter(provider=provider)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        offset = (page - 1) * page_size
        
        total = queryset.count()
        shipments = list(queryset[offset:offset + page_size])
        
        return Response({
            'results': ShipmentListSerializer(shipments, many=True).data,
            'count': total,
            'page': page,
            'pages': (total + page_size - 1) // page_size
        })


class AdminShipmentDetailView(APIView):
    """Admin: Shipment details."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: ShipmentSerializer},
        tags=['Shipping - Admin']
    )
    def get(self, request, shipment_id):
        """Get shipment details."""
        try:
            shipment = ShippingService.get_shipment(shipment_id)
            return Response(ShipmentSerializer(shipment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class AdminCreateShipmentView(APIView):
    """Admin: Create shipment for order."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=CreateShipmentSerializer,
        responses={201: ShipmentSerializer},
        tags=['Shipping - Admin']
    )
    def post(self, request):
        """Create shipment for an order."""
        serializer = CreateShipmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = Order.objects.get(id=serializer.validated_data['order_id'])
            
            shipment = ShippingService.create_shipment(
                order=order,
                weight=serializer.validated_data.get('weight'),
                note=serializer.validated_data.get('note', ''),
                auto_create_ghn=serializer.validated_data.get('auto_create_ghn', True)
            )
            
            return Response(
                ShipmentSerializer(shipment).data,
                status=status.HTTP_201_CREATED
            )
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminCancelShipmentView(APIView):
    """Admin: Cancel shipment."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=CancelShipmentSerializer,
        responses={200: ShipmentSerializer},
        tags=['Shipping - Admin']
    )
    def post(self, request, shipment_id):
        """Cancel a shipment."""
        serializer = CancelShipmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            shipment = ShippingService.get_shipment(shipment_id)
            updated = ShippingService.cancel_shipment(
                shipment,
                serializer.validated_data.get('reason', '')
            )
            return Response(ShipmentSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminSyncTrackingView(APIView):
    """Admin: Sync tracking from provider."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: ShipmentSerializer},
        tags=['Shipping - Admin']
    )
    def post(self, request, shipment_id):
        """Sync tracking info from provider."""
        try:
            shipment = ShippingService.get_shipment(shipment_id)
            updated = ShippingService.sync_tracking(shipment)
            return Response(ShipmentSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminShippingStatisticsView(APIView):
    """Admin: Get shipping statistics."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('days', int, description='Period in days (default: 30)'),
            OpenApiParameter('provider', str, description='Filter by provider'),
        ],
        responses={200: ShippingStatisticsSerializer},
        tags=['Shipping - Admin']
    )
    def get(self, request):
        """Get shipping statistics."""
        days = int(request.query_params.get('days', 30))
        provider = request.query_params.get('provider')
        
        stats = ShippingService.get_statistics(min(days, 365), provider)
        return Response(stats)


# ==================== WEBHOOKS ====================

@method_decorator(csrf_exempt, name='dispatch')
class GHNWebhookView(APIView):
    """
    GHN Webhook endpoint.
    
    Receives shipping status updates from GHN.
    Configure this URL in GHN dashboard.
    """
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=GHNWebhookSerializer,
        responses={200: OpenApiResponse(description='Webhook processed')},
        tags=['Shipping - Webhooks']
    )
    def post(self, request):
        """Process GHN webhook."""
        import logging
        logger = logging.getLogger('apps.shipping')
        
        try:
            payload = request.data
            logger.info(
                f"GHN webhook received: {payload.get('OrderCode')}",
                extra={'payload': payload}
            )
            
            result = ShippingService.process_webhook('ghn', payload)
            
            return Response({'success': result.get('success', False)})
            
        except Exception as e:
            logger.error(f"GHN webhook error: {e}", exc_info=True)
            # Return 200 to prevent webhook retry
            return Response({'success': False, 'error': str(e)})


@method_decorator(csrf_exempt, name='dispatch')
class GHTKWebhookView(APIView):
    """GHTK Webhook placeholder."""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Process GHTK webhook."""
        # TODO: Implement GHTK webhook processing
        return Response({'success': True})


@method_decorator(csrf_exempt, name='dispatch')
class VTPWebhookView(APIView):
    """Viettel Post Webhook placeholder."""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Process Viettel Post webhook."""
        # TODO: Implement VTP webhook processing
        return Response({'success': True})
