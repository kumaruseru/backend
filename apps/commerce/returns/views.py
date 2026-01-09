"""Commerce Returns - API Views."""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from apps.commerce.orders.models import Order
from .models import ReturnRequest
from .serializers import (
    ReturnRequestSerializer, ReturnRequestListSerializer,
    ReturnItemSerializer, ReturnImageSerializer,
    ReturnCreateSerializer, ReturnApproveSerializer, ReturnRejectSerializer, ReturnReceiveSerializer,
    ReturnStatisticsSerializer
)
from .services import ReturnService, ReturnStatisticsService


class UserReturnListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReturnRequestListSerializer

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        return ReturnService.get_user_returns(self.request.user, status_filter)

    @extend_schema(parameters=[OpenApiParameter('status', str)], tags=['Returns'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserReturnDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ReturnRequestSerializer}, tags=['Returns'])
    def get(self, request, return_id):
        try:
            return_request = ReturnService.get_return(return_id, request.user)
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class UserReturnCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ReturnCreateSerializer, responses={201: ReturnRequestSerializer}, tags=['Returns'])
    def post(self, request):
        serializer = ReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            order = Order.objects.get(id=data['order_id'], user=request.user)
            bank_info = {'bank_name': data.get('bank_name', ''), 'account_number': data.get('bank_account_number', ''), 'account_name': data.get('bank_account_name', '')}
            return_request = ReturnService.create_return(user=request.user, order=order, reason=data['reason'], description=data['description'], items=data['items'], refund_method=data.get('refund_method', 'original'), bank_info=bank_info if data.get('refund_method') == 'bank_transfer' else None)
            return Response(ReturnRequestSerializer(return_request).data, status=status.HTTP_201_CREATED)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class UserReturnCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Returns'])
    def post(self, request, return_id):
        reason = request.data.get('reason', '')
        try:
            return_request = ReturnService.get_return(return_id, request.user)
            return_request = ReturnService.cancel_return(return_request, request.user, reason)
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminReturnListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ReturnRequestListSerializer

    def get_queryset(self):
        queryset = ReturnRequest.objects.select_related('order', 'user').prefetch_related('items')
        status_filter = self.request.query_params.get('status')
        reason = self.request.query_params.get('reason')
        search = self.request.query_params.get('search')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if reason:
            queryset = queryset.filter(reason=reason)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(Q(request_number__icontains=search) | Q(order__order_number__icontains=search))
        return queryset.order_by('-created_at')

    @extend_schema(parameters=[OpenApiParameter('status', str), OpenApiParameter('reason', str), OpenApiParameter('search', str)], tags=['Returns - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminReturnDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: ReturnRequestSerializer}, tags=['Returns - Admin'])
    def get(self, request, return_id):
        try:
            return_request = ReturnService.get_return(return_id)
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminReturnApproveView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ReturnApproveSerializer, responses={200: ReturnRequestSerializer}, tags=['Returns - Admin'])
    def post(self, request, return_id):
        serializer = ReturnApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            return_request = ReturnService.get_return(return_id)
            return_request = ReturnService.approve_return(return_request, request.user, data['approved_refund'], data.get('notes', ''))
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminReturnRejectView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ReturnRejectSerializer, responses={200: ReturnRequestSerializer}, tags=['Returns - Admin'])
    def post(self, request, return_id):
        serializer = ReturnRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            return_request = ReturnService.get_return(return_id)
            return_request = ReturnService.reject_return(return_request, request.user, data['reason'])
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminReturnReceiveView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ReturnReceiveSerializer, responses={200: ReturnRequestSerializer}, tags=['Returns - Admin'])
    def post(self, request, return_id):
        serializer = ReturnReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            return_request = ReturnService.get_return(return_id)
            return_request = ReturnService.receive_items(return_request, request.user, data['quality_passed'], data.get('notes', ''))
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminReturnCompleteView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: ReturnRequestSerializer}, tags=['Returns - Admin'])
    def post(self, request, return_id):
        try:
            return_request = ReturnService.get_return(return_id)
            return_request = ReturnService.complete_return(return_request, request.user)
            return Response(ReturnRequestSerializer(return_request).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminStatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(parameters=[OpenApiParameter('days', int)], responses={200: ReturnStatisticsSerializer}, tags=['Returns - Admin'])
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        stats = ReturnStatisticsService.get_statistics(days)
        return Response(stats)
