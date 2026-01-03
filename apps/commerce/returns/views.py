"""
Commerce Returns - Production-Ready API Views.

Comprehensive endpoints with:
- Rate limiting
- Pagination
- Image upload
- Admin workflow
- Statistics
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import ReturnRequest
from .serializers import (
    ReturnRequestSerializer, ReturnRequestListSerializer,
    ReturnRequestCreateSerializer, ReturnImageSerializer,
    ReturnImageUploadSerializer, ReturnTrackingUpdateSerializer,
    ReturnApproveSerializer, ReturnRejectSerializer,
    ReturnReceiveSerializer, ReturnProcessRefundSerializer
)
from .services import ReturnService


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


# ==================== USER ENDPOINTS ====================

class ReturnRequestListView(APIView):
    """List and create return requests."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'returns'
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('page', int, description='Page number'),
            OpenApiParameter('page_size', int, description='Items per page'),
        ],
        responses={200: ReturnRequestListSerializer(many=True)},
        tags=['Returns']
    )
    def get(self, request):
        """Get user's return requests."""
        status_filter = request.query_params.get('status')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        result = ReturnService.get_user_returns(
            request.user, status_filter, page, min(page_size, 50)
        )
        
        return Response({
            'results': ReturnRequestListSerializer(result['returns'], many=True).data,
            'count': result['total'],
            'page': result['page'],
            'pages': result['pages']
        })
    
    @extend_schema(
        request=ReturnRequestCreateSerializer,
        responses={201: ReturnRequestSerializer},
        tags=['Returns']
    )
    def post(self, request):
        """Create a new return request."""
        serializer = ReturnRequestCreateSerializer(
            data=request.data,
            context={'user': request.user}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            bank_info = {
                'bank_name': data.get('bank_name', ''),
                'bank_account_number': data.get('bank_account_number', ''),
                'bank_account_name': data.get('bank_account_name', '')
            }
            
            return_request = ReturnService.create_return_request(
                user=request.user,
                order_id=data['order_id'],
                reason=data['reason'],
                description=data['description'],
                items=data['items'],
                refund_method=data.get('refund_method', 'original'),
                bank_info=bank_info
            )
            
            return Response(
                ReturnRequestSerializer(return_request).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class ReturnRequestDetailView(APIView):
    """Get return request details."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: ReturnRequestSerializer},
        tags=['Returns']
    )
    def get(self, request, request_id):
        """Get return request by ID."""
        try:
            return_request = ReturnService.get_return_request(request_id, request.user)
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class ReturnByNumberView(APIView):
    """Get return by request number."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: ReturnRequestSerializer},
        tags=['Returns']
    )
    def get(self, request, request_number):
        """Get return by request number."""
        try:
            return_request = ReturnService.get_by_request_number(request_number, request.user)
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class ReturnCancelView(APIView):
    """Cancel a pending return request."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'returns_modify'
    
    @extend_schema(
        request={'type': 'object', 'properties': {'reason': {'type': 'string'}}},
        responses={200: ReturnRequestSerializer},
        tags=['Returns']
    )
    def post(self, request, request_id):
        """Cancel return request."""
        try:
            return_request = ReturnService.get_return_request(request_id, request.user)
            reason = request.data.get('reason', '')
            
            updated = ReturnService.cancel_return(return_request, request.user, reason)
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class ReturnImageUploadView(APIView):
    """Upload evidence images."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = 'returns_upload'
    
    @extend_schema(
        request=ReturnImageUploadSerializer,
        responses={201: ReturnImageSerializer},
        tags=['Returns']
    )
    def post(self, request, request_id):
        """Upload image for return request."""
        serializer = ReturnImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            return_request = ReturnService.get_return_request(request_id, request.user)
            
            return_image = ReturnService.upload_image(
                return_request,
                request.user,
                serializer.validated_data['image'],
                serializer.validated_data.get('caption', '')
            )
            
            return Response(
                ReturnImageSerializer(return_image).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class ReturnTrackingView(APIView):
    """Update return shipment tracking."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=ReturnTrackingUpdateSerializer,
        responses={200: ReturnRequestSerializer},
        tags=['Returns']
    )
    def post(self, request, request_id):
        """Update return tracking info."""
        serializer = ReturnTrackingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            return_request = ReturnService.get_return_request(request_id, request.user)
            
            updated = ReturnService.update_tracking(
                return_request,
                request.user,
                serializer.validated_data['tracking_code'],
                serializer.validated_data.get('carrier', 'GHN')
            )
            
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


# ==================== ADMIN ENDPOINTS ====================

class AdminReturnListView(APIView):
    """Admin: List all return requests."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: ReturnRequestSerializer(many=True)},
        tags=['Returns Admin']
    )
    def get(self, request):
        """Get all return requests."""
        status_filter = request.query_params.get('status')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        result = ReturnService.get_pending_returns(status_filter, page, min(page_size, 100))
        
        return Response({
            'results': ReturnRequestSerializer(result['returns'], many=True).data,
            'count': result['total'],
            'page': result['page'],
            'pages': result['pages']
        })


class AdminReturnDetailView(APIView):
    """Admin: Get return details."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: ReturnRequestSerializer},
        tags=['Returns Admin']
    )
    def get(self, request, request_id):
        """Get return request details."""
        try:
            return_request = ReturnService.get_return_request(request_id)
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class AdminStartReviewView(APIView):
    """Admin: Start reviewing a return request."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: ReturnRequestSerializer},
        tags=['Returns Admin']
    )
    def post(self, request, request_id):
        """Start review process."""
        try:
            return_request = ReturnService.get_return_request(request_id)
            updated = ReturnService.start_review(return_request, request.user)
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminApproveView(APIView):
    """Admin: Approve return request."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=ReturnApproveSerializer,
        responses={200: ReturnRequestSerializer},
        tags=['Returns Admin']
    )
    def post(self, request, request_id):
        """Approve return request."""
        try:
            return_request = ReturnService.get_return_request(request_id)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReturnApproveSerializer(
            data=request.data,
            context={'return_request': return_request}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            updated = ReturnService.approve_return(
                return_request,
                request.user,
                serializer.validated_data['approved_refund'],
                serializer.validated_data.get('notes', '')
            )
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminRejectView(APIView):
    """Admin: Reject return request."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=ReturnRejectSerializer,
        responses={200: ReturnRequestSerializer},
        tags=['Returns Admin']
    )
    def post(self, request, request_id):
        """Reject return request."""
        serializer = ReturnRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            return_request = ReturnService.get_return_request(request_id)
            updated = ReturnService.reject_return(
                return_request,
                request.user,
                serializer.validated_data['reason']
            )
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminReceiveView(APIView):
    """Admin: Mark items as received."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=ReturnReceiveSerializer,
        responses={200: ReturnRequestSerializer},
        tags=['Returns Admin']
    )
    def post(self, request, request_id):
        """Mark returned items as received."""
        serializer = ReturnReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            return_request = ReturnService.get_return_request(request_id)
            updated = ReturnService.receive_items(
                return_request,
                request.user,
                serializer.validated_data['quality_passed'],
                serializer.validated_data.get('notes', ''),
                serializer.validated_data.get('items')
            )
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminProcessRefundView(APIView):
    """Admin: Process refund."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=ReturnProcessRefundSerializer,
        responses={200: ReturnRequestSerializer},
        tags=['Returns Admin']
    )
    def post(self, request, request_id):
        """Process refund for return."""
        serializer = ReturnProcessRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            return_request = ReturnService.get_return_request(request_id)
            updated = ReturnService.process_refund(return_request, request.user)
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminCompleteView(APIView):
    """Admin: Complete return process."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: ReturnRequestSerializer},
        tags=['Returns Admin']
    )
    def post(self, request, request_id):
        """Mark return as completed."""
        try:
            return_request = ReturnService.get_return_request(request_id)
            updated = ReturnService.complete_return(return_request, request.user)
            return Response(ReturnRequestSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminStatisticsView(APIView):
    """Admin: Get return statistics."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('days', int, description='Period in days (default: 30)'),
        ],
        responses={200: {'type': 'object'}},
        tags=['Returns Admin']
    )
    def get(self, request):
        """Get return statistics."""
        days = int(request.query_params.get('days', 30))
        stats = ReturnService.get_statistics(min(days, 365))
        return Response(stats)
