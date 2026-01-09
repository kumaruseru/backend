"""Commerce Billing - API Views and Webhooks."""
import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from apps.commerce.orders.models import Order

from .models import PaymentTransaction, PaymentRefund
from .services import PaymentService
from .serializers import (
    CreatePaymentSerializer, PaymentTransactionSerializer,
    PaymentTransactionDetailSerializer, CreateRefundSerializer,
    PaymentRefundSerializer, PaymentGatewaySerializer
)

logger = logging.getLogger('apps.billing.views')


class AvailableGatewaysView(APIView):
    """List available payment gateways."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        gateways = PaymentService.get_available_gateways()
        serializer = PaymentGatewaySerializer(gateways, many=True)
        return Response(serializer.data)


class CreatePaymentView(APIView):
    """Create a payment for an order."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_id = serializer.validated_data['order_id']
        gateway = serializer.validated_data.get('gateway')
        return_url = serializer.validated_data['return_url']
        cancel_url = serializer.validated_data.get('cancel_url', return_url)
        
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if order.payment_status == Order.PaymentStatus.PAID:
            return Response(
                {'error': 'Order already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            txn = PaymentService.create_payment(
                order=order,
                gateway_code=gateway,
                return_url=return_url,
                cancel_url=cancel_url,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            
            return Response({
                'transaction_id': txn.transaction_id,
                'payment_url': txn.payment_url,
                'status': txn.status,
                'gateway': txn.gateway,
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Payment creation error: {e}")
            return Response(
                {'error': 'Payment creation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_client_ip(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


class PaymentCallbackView(APIView):
    """Handle payment gateway callbacks (return URL)."""
    permission_classes = [AllowAny]
    
    def get(self, request, gateway):
        """Handle GET redirect from gateway."""
        return self._process_callback(gateway, request.query_params.dict())
    
    def post(self, request, gateway):
        """Handle POST callback from gateway."""
        return self._process_callback(gateway, request.data)
    
    def _process_callback(self, gateway, data):
        try:
            # Extract transaction ID based on gateway
            if gateway == 'vnpay':
                txn_id = data.get('vnp_TxnRef', '')
            elif gateway == 'momo':
                txn_id = data.get('requestId') or data.get('orderId', '')
            elif gateway == 'stripe':
                txn_id = data.get('session_id', '')
            else:
                txn_id = data.get('transaction_id', '')
            
            if not txn_id:
                return Response(
                    {'error': 'Transaction ID not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            txn = PaymentService.verify_payment(txn_id, data)
            
            response_data = {
                'transaction_id': txn.transaction_id,
                'status': txn.status,
                'success': txn.is_successful,
            }
            
            if txn.is_successful:
                response_data['message'] = 'Payment successful'
                response_data['order_number'] = txn.order.order_number
            else:
                response_data['message'] = txn.error_message or 'Payment failed'
                response_data['error_code'] = txn.error_code
            
            return Response(response_data)
            
        except PaymentTransaction.DoesNotExist:
            return Response(
                {'error': 'Transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Payment callback error: {e}")
            return Response(
                {'error': 'Callback processing failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(APIView):
    """Handle payment gateway webhooks (IPNs)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request, gateway):
        try:
            headers = {
                key: value
                for key, value in request.META.items()
                if key.startswith('HTTP_')
            }
            
            # For Stripe, get raw body (bytes) for signature verification
            if gateway == 'stripe':
                payload = request.body  # Keep as bytes for signature verification
                headers['Stripe-Signature'] = request.META.get('HTTP_STRIPE_SIGNATURE', '')
            else:
                payload = request.data
            
            txn = PaymentService.process_webhook(
                gateway_code=gateway,
                payload=payload if gateway == 'stripe' else dict(payload),
                headers=headers
            )
            
            if txn:
                return Response({'received': True, 'transaction_id': txn.transaction_id})
            else:
                return Response({'received': True, 'message': 'No matching transaction'})
                
        except Exception as e:
            logger.exception(f"Webhook error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TransactionListView(ListAPIView):
    """List user's payment transactions."""
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentTransactionSerializer
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return PaymentTransaction.objects.all().order_by('-created_at')
        return PaymentTransaction.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


class TransactionDetailView(APIView):
    """Get transaction details."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, transaction_id):
        try:
            if request.user.is_staff:
                txn = PaymentTransaction.objects.get(transaction_id=transaction_id)
            else:
                txn = PaymentTransaction.objects.get(
                    transaction_id=transaction_id,
                    user=request.user
                )
            
            serializer = PaymentTransactionDetailSerializer(txn)
            return Response(serializer.data)
            
        except PaymentTransaction.DoesNotExist:
            return Response(
                {'error': 'Transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class CreateRefundView(APIView):
    """Create a refund for an order."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        serializer = CreateRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_id = serializer.validated_data['order_id']
        amount = serializer.validated_data.get('amount')
        reason = serializer.validated_data.get('reason', 'customer_request')
        notes = serializer.validated_data.get('notes', '')
        
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            refund = PaymentService.create_refund(
                order=order,
                amount=amount,
                reason=notes or reason,
                processed_by=request.user
            )
            
            return Response({
                'refund_id': refund.refund_id,
                'status': refund.status,
                'amount': refund.amount,
                'success': refund.status == PaymentRefund.Status.COMPLETED,
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Refund creation error: {e}")
            return Response(
                {'error': 'Refund creation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefundListView(ListAPIView):
    """List refunds."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = PaymentRefundSerializer
    
    def get_queryset(self):
        return PaymentRefund.objects.all().order_by('-created_at')
