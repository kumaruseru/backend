"""Commerce Orders - API Views."""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Order, OrderNote
from .serializers import (
    OrderSerializer, OrderListSerializer, OrderTrackingSerializer,
    OrderItemSerializer, OrderStatusHistorySerializer, OrderNoteSerializer,
    OrderCreateSerializer, OrderCancelSerializer, OrderNoteCreateSerializer,
    AdminOrderUpdateSerializer, AdminBulkStatusUpdateSerializer, OrderStatisticsSerializer
)
from .services import OrderService


class OrderListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        queryset = Order.objects.filter(user=self.request.user).prefetch_related('items')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by('-created_at')

    @extend_schema(parameters=[OpenApiParameter('status', str)], tags=['Orders'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OrderSerializer}, tags=['Orders'])
    def get(self, request, order_id):
        try:
            order = OrderService.get_order(order_id, request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class OrderByNumberView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OrderSerializer}, tags=['Orders'])
    def get(self, request, order_number):
        try:
            order = OrderService.get_by_order_number(order_number, request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class OrderCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=OrderCreateSerializer, responses={201: OrderSerializer}, tags=['Orders'])
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        shipping_info = {
            'recipient_name': data['recipient_name'],
            'phone': data['phone'],
            'email': data.get('email', ''),
            'address': data['address'],
            'ward': data['ward'],
            'district': data['district'],
            'city': data['city'],
            'district_id': data.get('district_id'),
            'ward_code': data.get('ward_code', ''),
            'is_gift': data.get('is_gift', False),
            'gift_message': data.get('gift_message', '')
        }

        try:
            order = OrderService.create_order_from_items(
                user=request.user,
                items=data['items'],
                shipping_info=shipping_info,
                payment_method=data.get('payment_method', Order.PaymentMethod.COD),
                coupon_code=data.get('coupon_code', ''),
                customer_note=data.get('customer_note', ''),
                source=data.get('source', Order.Source.WEB)
            )
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=OrderCancelSerializer, responses={200: OrderSerializer}, tags=['Orders'])
    def post(self, request, order_id):
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.get_order(order_id, request.user)
            order = OrderService.cancel_order(order, serializer.validated_data.get('reason', ''), request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class OrderTrackingView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OrderTrackingSerializer}, tags=['Orders'])
    def get(self, request, order_number):
        try:
            order = OrderService.get_by_order_number(order_number)
            return Response(OrderTrackingSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class OrderNoteCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=OrderNoteCreateSerializer, responses={201: OrderNoteSerializer}, tags=['Orders'])
    def post(self, request, order_id):
        serializer = OrderNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.get_order(order_id, request.user)
            note = OrderService.add_note(
                order=order,
                content=serializer.validated_data['content'],
                note_type=serializer.validated_data.get('note_type', 'general'),
                created_by=request.user,
                is_private=serializer.validated_data.get('is_private', True)
            )
            return Response(OrderNoteSerializer(note).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        queryset = Order.objects.select_related('user').prefetch_related('items')
        status_filter = self.request.query_params.get('status')
        payment_status = self.request.query_params.get('payment_status')
        search = self.request.query_params.get('search')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(Q(order_number__icontains=search) | Q(phone__icontains=search) | Q(recipient_name__icontains=search))
        return queryset.order_by('-created_at')

    @extend_schema(parameters=[OpenApiParameter('status', str), OpenApiParameter('payment_status', str), OpenApiParameter('search', str)], tags=['Orders - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminOrderDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: OrderSerializer}, tags=['Orders - Admin'])
    def get(self, request, order_id):
        try:
            order = OrderService.get_order(order_id)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminOrderConfirmView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: OrderSerializer}, tags=['Orders - Admin'])
    def post(self, request, order_id):
        try:
            order = OrderService.get_order(order_id)
            order = OrderService.confirm_order(order, request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminOrderCancelView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=OrderCancelSerializer, responses={200: OrderSerializer}, tags=['Orders - Admin'])
    def post(self, request, order_id):
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.get_order(order_id)
            order = OrderService.cancel_order(order, serializer.validated_data.get('reason', ''), request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminOrderShipView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(tags=['Orders - Admin'])
    def post(self, request, order_id):
        tracking_code = request.data.get('tracking_code', '')
        provider = request.data.get('provider', 'ghn')
        if not tracking_code:
            return Response({'error': 'Tracking code is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = OrderService.get_order(order_id)
            order.ship(tracking_code, provider, request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminOrderDeliverView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: OrderSerializer}, tags=['Orders - Admin'])
    def post(self, request, order_id):
        try:
            order = OrderService.get_order(order_id)
            order.deliver(request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminStatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(parameters=[OpenApiParameter('days', int)], responses={200: OrderStatisticsSerializer}, tags=['Orders - Admin'])
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        stats = OrderService.get_statistics(days)
        return Response(stats)
