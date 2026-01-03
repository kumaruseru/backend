"""
Commerce Orders - Production-Ready API Views.

Comprehensive endpoints with:
- Order CRUD
- Status tracking
- Reorder
- Admin management
- Statistics
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.common.core.exceptions import DomainException
from .models import Order
from .serializers import (
    OrderSerializer, OrderListSerializer, OrderTrackingSerializer,
    OrderFromCartSerializer, OrderCreateSerializer,
    OrderCancelSerializer, OrderNoteCreateSerializer, OrderNoteSerializer,
    AdminOrderUpdateSerializer, OrderStatisticsSerializer
)
from .services import OrderService


# ==================== USER ENDPOINTS ====================

class OrderListView(APIView):
    """List and create orders."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'orders'
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: OrderListSerializer(many=True)},
        tags=['Orders']
    )
    def get(self, request):
        """Get user's orders."""
        status_filter = request.query_params.get('status')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        result = OrderService.get_user_orders(
            request.user, status_filter, page, min(page_size, 50)
        )
        
        return Response({
            'results': OrderListSerializer(result['orders'], many=True).data,
            'count': result['total'],
            'page': result['page'],
            'pages': result['pages']
        })


class OrderFromCartView(APIView):
    """Create order from cart."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'order_create'
    
    @extend_schema(
        request=OrderFromCartSerializer,
        responses={201: OrderSerializer},
        tags=['Orders']
    )
    def post(self, request):
        """Create order from user's cart."""
        serializer = OrderFromCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            order = OrderService.create_order_from_cart(
                user=request.user,
                shipping_info=data,
                payment_method=data.get('payment_method', 'cod'),
                coupon_code=data.get('coupon_code', ''),
                customer_note=data.get('customer_note', ''),
                source=data.get('source', 'web'),
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class OrderFromItemsView(APIView):
    """Create order directly from items (quick buy)."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'order_create'
    
    @extend_schema(
        request=OrderCreateSerializer,
        responses={201: OrderSerializer},
        tags=['Orders']
    )
    def post(self, request):
        """Create order from items."""
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            order = OrderService.create_order_from_items(
                user=request.user,
                items=data['items'],
                shipping_info=data,
                payment_method=data.get('payment_method', 'cod'),
                coupon_code=data.get('coupon_code', ''),
                customer_note=data.get('customer_note', ''),
                source=data.get('source', 'web')
            )
            
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class OrderDetailView(APIView):
    """Get order details."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: OrderSerializer},
        tags=['Orders']
    )
    def get(self, request, order_id):
        """Get order by ID."""
        try:
            order = OrderService.get_order(order_id, request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class OrderByNumberView(APIView):
    """Get order by order number."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: OrderSerializer},
        tags=['Orders']
    )
    def get(self, request, order_number):
        """Get order by order number."""
        try:
            order = OrderService.get_by_order_number(order_number, request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class OrderCancelView(APIView):
    """Cancel an order."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=OrderCancelSerializer,
        responses={200: OrderSerializer},
        tags=['Orders']
    )
    def post(self, request, order_id):
        """Cancel order."""
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = OrderService.get_order(order_id, request.user)
            updated = OrderService.cancel_order(
                order,
                serializer.validated_data.get('reason', ''),
                request.user
            )
            return Response(OrderSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class OrderReorderView(APIView):
    """Reorder from previous order."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'order_create'
    
    @extend_schema(
        responses={201: OrderSerializer},
        tags=['Orders']
    )
    def post(self, request, order_id):
        """Create new order from previous order."""
        try:
            original = OrderService.get_order(order_id, request.user)
            new_order = OrderService.reorder(original, request.user)
            return Response(
                OrderSerializer(new_order).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class OrderTrackView(APIView):
    """Public order tracking."""
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'tracking'
    
    @extend_schema(
        responses={200: OrderTrackingSerializer},
        tags=['Orders']
    )
    def get(self, request, order_number):
        """Track order by order number."""
        try:
            order = Order.objects.prefetch_related('status_history').get(
                order_number=order_number
            )
            return Response(OrderTrackingSerializer(order).data)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class UserOrderStatisticsView(APIView):
    """User's order statistics."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: OrderStatisticsSerializer},
        tags=['Orders']
    )
    def get(self, request):
        """Get user's order statistics."""
        days = int(request.query_params.get('days', 365))
        stats = OrderService.get_statistics(min(days, 365), request.user)
        return Response(stats)


# ==================== ADMIN ENDPOINTS ====================

class AdminOrderListView(APIView):
    """Admin: List all orders."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', str),
            OpenApiParameter('payment_status', str),
            OpenApiParameter('payment_method', str),
            OpenApiParameter('search', str, description='Search by order number, phone, email'),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: OrderListSerializer(many=True)},
        tags=['Orders - Admin']
    )
    def get(self, request):
        """Get all orders with filters."""
        queryset = Order.objects.select_related('user').prefetch_related('items')
        
        # Filters
        status_filter = request.query_params.get('status')
        payment_status = request.query_params.get('payment_status')
        payment_method = request.query_params.get('payment_method')
        search = request.query_params.get('search')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(recipient_name__icontains=search)
            )
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        offset = (page - 1) * page_size
        
        total = queryset.count()
        orders = list(queryset[offset:offset + page_size])
        
        return Response({
            'results': OrderListSerializer(orders, many=True).data,
            'count': total,
            'page': page,
            'pages': (total + page_size - 1) // page_size
        })


class AdminOrderDetailView(APIView):
    """Admin: Order details."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: OrderSerializer},
        tags=['Orders - Admin']
    )
    def get(self, request, order_id):
        """Get order details."""
        try:
            order = OrderService.get_order(order_id)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        request=AdminOrderUpdateSerializer,
        responses={200: OrderSerializer},
        tags=['Orders - Admin']
    )
    def patch(self, request, order_id):
        """Update order admin fields."""
        serializer = AdminOrderUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = OrderService.get_order(order_id)
            
            for field, value in serializer.validated_data.items():
                setattr(order, field, value)
            
            order.save()
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminOrderConfirmView(APIView):
    """Admin: Confirm order."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: OrderSerializer},
        tags=['Orders - Admin']
    )
    def post(self, request, order_id):
        """Confirm a pending order."""
        try:
            order = OrderService.get_order(order_id)
            updated = OrderService.confirm_order(order, request.user)
            return Response(OrderSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminOrderProcessView(APIView):
    """Admin: Mark order as processing."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: OrderSerializer},
        tags=['Orders - Admin']
    )
    def post(self, request, order_id):
        """Mark order as processing."""
        try:
            order = OrderService.get_order(order_id)
            order.mark_processing(request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminOrderShipView(APIView):
    """Admin: Mark order as shipped."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request={'type': 'object', 'properties': {
            'tracking_code': {'type': 'string'},
            'provider': {'type': 'string'}
        }},
        responses={200: OrderSerializer},
        tags=['Orders - Admin']
    )
    def post(self, request, order_id):
        """Mark order as shipped."""
        try:
            order = OrderService.get_order(order_id)
            tracking_code = request.data.get('tracking_code', '')
            provider = request.data.get('provider', 'ghn')
            
            order.ship(tracking_code, provider, request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminOrderDeliverView(APIView):
    """Admin: Mark order as delivered."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: OrderSerializer},
        tags=['Orders - Admin']
    )
    def post(self, request, order_id):
        """Mark order as delivered."""
        try:
            order = OrderService.get_order(order_id)
            order.deliver(request.user)
            return Response(OrderSerializer(order).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminOrderCancelView(APIView):
    """Admin: Cancel order."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=OrderCancelSerializer,
        responses={200: OrderSerializer},
        tags=['Orders - Admin']
    )
    def post(self, request, order_id):
        """Cancel order."""
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = OrderService.get_order(order_id)
            updated = OrderService.cancel_order(
                order,
                serializer.validated_data.get('reason', ''),
                request.user
            )
            return Response(OrderSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminOrderNoteView(APIView):
    """Admin: Add order notes."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=OrderNoteCreateSerializer,
        responses={201: OrderNoteSerializer},
        tags=['Orders - Admin']
    )
    def post(self, request, order_id):
        """Add note to order."""
        serializer = OrderNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = OrderService.get_order(order_id)
            note = OrderService.add_note(
                order,
                serializer.validated_data['content'],
                serializer.validated_data.get('note_type', 'general'),
                request.user,
                serializer.validated_data.get('is_private', True)
            )
            return Response(
                OrderNoteSerializer(note).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminOrderStatisticsView(APIView):
    """Admin: Order statistics."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('days', int, description='Period in days (default: 30)'),
        ],
        responses={200: OrderStatisticsSerializer},
        tags=['Orders - Admin']
    )
    def get(self, request):
        """Get order statistics."""
        days = int(request.query_params.get('days', 30))
        stats = OrderService.get_statistics(min(days, 365))
        return Response(stats)
