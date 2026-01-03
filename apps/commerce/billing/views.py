"""
Commerce Billing - Production-Ready API Views.

Comprehensive endpoints with:
- Payment creation
- Callback/webhook handling
- Refound management
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
from .models import Payment, PaymentMethod
from .serializers import (
    PaymentSerializer, PaymentListSerializer, RefundSerializer,
    PaymentMethodSerializer,
    CreatePaymentSerializer, PaymentCallbackSerializer,
    RefundRequestSerializer, SavePaymentMethodSerializer,
    PaymentUrlResponseSerializer, PaymentResultSerializer,
    PaymentStatisticsSerializer
)
from .services import PaymentService


# ==================== USER ENDPOINTS ====================

class PaymentCreateView(APIView):
    """Create payment for order."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'payment_create'
    
    @extend_schema(
        request=CreatePaymentSerializer,
        responses={201: PaymentUrlResponseSerializer},
        tags=['Billing']
    )
    def post(self, request):
        """Create payment and get payment URL."""
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            order = Order.objects.get(
                id=data['order_id'],
                user=request.user
            )
            
            result = PaymentService.create_payment(
                order=order,
                method=data['method'],
                return_url=data.get('return_url', ''),
                cancel_url=data.get('cancel_url', ''),
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class PaymentDetailView(APIView):
    """Get payment details."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: PaymentSerializer},
        tags=['Billing']
    )
    def get(self, request, payment_id):
        """Get payment by ID."""
        try:
            payment = PaymentService.get_payment(payment_id, request.user)
            return Response(PaymentSerializer(payment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class PaymentListView(APIView):
    """List user's payments."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', str),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: PaymentListSerializer(many=True)},
        tags=['Billing']
    )
    def get(self, request):
        """Get user's payments."""
        queryset = Payment.objects.filter(user=request.user).select_related('order')
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 50)
        offset = (page - 1) * page_size
        
        total = queryset.count()
        payments = list(queryset[offset:offset + page_size])
        
        return Response({
            'results': PaymentListSerializer(payments, many=True).data,
            'count': total,
            'page': page,
            'pages': (total + page_size - 1) // page_size
        })


class PaymentRetryView(APIView):
    """Retry failed payment."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'payment_create'
    
    @extend_schema(
        responses={200: PaymentUrlResponseSerializer},
        tags=['Billing']
    )
    def post(self, request, payment_id):
        """Retry a failed payment."""
        try:
            payment = PaymentService.get_payment(payment_id, request.user)
            result = PaymentService.retry_payment(payment)
            
            if result.get('success'):
                return Response(result)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class PaymentCancelView(APIView):
    """Cancel pending payment."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: PaymentSerializer},
        tags=['Billing']
    )
    def post(self, request, payment_id):
        """Cancel payment."""
        try:
            payment = PaymentService.get_payment(payment_id, request.user)
            updated = PaymentService.cancel_payment(
                payment,
                request.data.get('reason', '')
            )
            return Response(PaymentSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


# ==================== SAVED PAYMENT METHODS ====================

class PaymentMethodListView(APIView):
    """List saved payment methods."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: PaymentMethodSerializer(many=True)},
        tags=['Billing - Methods']
    )
    def get(self, request):
        """Get user's saved payment methods."""
        methods = PaymentMethod.objects.filter(
            user=request.user,
            is_active=True
        )
        return Response(PaymentMethodSerializer(methods, many=True).data)
    
    @extend_schema(
        request=SavePaymentMethodSerializer,
        responses={201: PaymentMethodSerializer},
        tags=['Billing - Methods']
    )
    def post(self, request):
        """Save a new payment method."""
        serializer = SavePaymentMethodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        method = PaymentMethod.objects.create(
            user=request.user,
            **data
        )
        
        return Response(
            PaymentMethodSerializer(method).data,
            status=status.HTTP_201_CREATED
        )


class PaymentMethodDetailView(APIView):
    """Manage saved payment method."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={204: None},
        tags=['Billing - Methods']
    )
    def delete(self, request, method_id):
        """Delete saved payment method."""
        PaymentMethod.objects.filter(
            id=method_id,
            user=request.user
        ).update(is_active=False)
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentMethodSetDefaultView(APIView):
    """Set default payment method."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: PaymentMethodSerializer},
        tags=['Billing - Methods']
    )
    def post(self, request, method_id):
        """Set payment method as default."""
        try:
            method = PaymentMethod.objects.get(
                id=method_id,
                user=request.user,
                is_active=True
            )
            method.is_default = True
            method.save()
            
            return Response(PaymentMethodSerializer(method).data)
        except PaymentMethod.DoesNotExist:
            return Response(
                {'error': 'Payment method not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ==================== WEBHOOKS ====================

@method_decorator(csrf_exempt, name='dispatch')
class VNPayCallbackView(APIView):
    """VNPay payment callback."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=PaymentCallbackSerializer,
        responses={200: OpenApiResponse(description='Callback processed')},
        tags=['Billing - Webhooks']
    )
    def get(self, request):
        """Process VNPay return URL callback."""
        result = PaymentService.process_callback('vnpay', request.GET.dict())
        
        # Redirect to frontend
        from django.conf import settings
        from django.shortcuts import redirect
        
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        
        if result.get('success'):
            return redirect(f"{base_url}/checkout/success?order={result.get('order_number', '')}")
        else:
            return redirect(f"{base_url}/checkout/failed?error={result.get('error', '')}")
    
    def post(self, request):
        """Process VNPay IPN webhook."""
        result = PaymentService.process_callback('vnpay', request.data)
        
        if result.get('success'):
            return Response({'RspCode': '00', 'Message': 'success'})
        else:
            return Response({'RspCode': '99', 'Message': result.get('error', 'failed')})


@method_decorator(csrf_exempt, name='dispatch')
class MoMoCallbackView(APIView):
    """MoMo payment callback."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=PaymentCallbackSerializer,
        responses={200: OpenApiResponse(description='Callback processed')},
        tags=['Billing - Webhooks']
    )
    def post(self, request):
        """Process MoMo callback."""
        result = PaymentService.process_callback('momo', request.data)
        
        return Response({'success': result.get('success', False)})


# ==================== ADMIN ENDPOINTS ====================

class AdminPaymentListView(APIView):
    """Admin: List all payments."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', str),
            OpenApiParameter('method', str),
            OpenApiParameter('search', str),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: PaymentListSerializer(many=True)},
        tags=['Billing - Admin']
    )
    def get(self, request):
        """Get all payments."""
        queryset = Payment.objects.select_related('order', 'user')
        
        # Filters
        status_filter = request.query_params.get('status')
        method = request.query_params.get('method')
        search = request.query_params.get('search')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if method:
            queryset = queryset.filter(method=method)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(order__order_number__icontains=search) |
                Q(transaction_id__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        offset = (page - 1) * page_size
        
        total = queryset.count()
        payments = list(queryset[offset:offset + page_size])
        
        return Response({
            'results': PaymentListSerializer(payments, many=True).data,
            'count': total,
            'page': page,
            'pages': (total + page_size - 1) // page_size
        })


class AdminPaymentDetailView(APIView):
    """Admin: Payment details."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: PaymentSerializer},
        tags=['Billing - Admin']
    )
    def get(self, request, payment_id):
        """Get payment details."""
        try:
            payment = PaymentService.get_payment(payment_id)
            return Response(PaymentSerializer(payment).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class AdminRefundView(APIView):
    """Admin: Create refund."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        request=RefundRequestSerializer,
        responses={201: RefundSerializer},
        tags=['Billing - Admin']
    )
    def post(self, request):
        """Create refund for payment."""
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            payment = PaymentService.get_payment(data['payment_id'])
            
            refund = PaymentService.create_refund(
                payment=payment,
                amount=data.get('amount'),
                reason=data.get('reason', 'customer_request'),
                reason_detail=data.get('reason_detail', ''),
                processed_by=request.user
            )
            
            return Response(
                RefundSerializer(refund).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AdminPaymentStatisticsView(APIView):
    """Admin: Payment statistics."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        parameters=[
            OpenApiParameter('days', int, description='Period in days (default: 30)'),
        ],
        responses={200: PaymentStatisticsSerializer},
        tags=['Billing - Admin']
    )
    def get(self, request):
        """Get payment statistics."""
        days = int(request.query_params.get('days', 30))
        stats = PaymentService.get_statistics(min(days, 365))
        return Response(stats)
