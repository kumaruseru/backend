"""VNPay Payment Gateway.

Integration with VNPay Vietnamese payment gateway using hash verification.
"""
import hashlib
import hmac
import urllib.parse
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from django.conf import settings

from .base import BasePaymentGateway, PaymentResult, RefundResult

logger = logging.getLogger('apps.billing.vnpay')


class VNPayGateway(BasePaymentGateway):
    """VNPay payment gateway.
    
    Uses VNPay Payment API with HMAC-SHA512 hash verification.
    """
    
    gateway_code = 'vnpay'
    gateway_name = 'VNPay'
    supports_refund = True
    supports_webhook = True
    
    def __init__(self):
        self.tmn_code = getattr(settings, 'VNPAY_TMN_CODE', '')
        self.hash_secret = getattr(settings, 'VNPAY_HASH_SECRET', '')
        self.payment_url = getattr(
            settings, 'VNPAY_URL',
            'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html'
        )
        self.api_url = getattr(
            settings, 'VNPAY_API_URL',
            'https://sandbox.vnpayment.vn/merchant_webapi/api/transaction'
        )
    
    def _generate_hash(self, data: str) -> str:
        """Generate HMAC-SHA512 hash."""
        return hmac.new(
            self.hash_secret.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
    
    def _build_query_string(self, params: Dict) -> str:
        """Build sorted query string for signature."""
        sorted_params = sorted(params.items())
        return '&'.join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in sorted_params)
    
    def create_payment(
        self,
        order,
        amount: Decimal,
        currency: str = 'VND',
        return_url: str = '',
        cancel_url: str = '',
        **kwargs
    ) -> PaymentResult:
        """Create VNPay payment URL."""
        try:
            txn_ref = f"VNP{order.order_number}"
            amount_int = int(amount) * 100  # VNPay uses x100
            create_date = datetime.now().strftime('%Y%m%d%H%M%S')
            
            ip_address = kwargs.get('ip_address', '127.0.0.1')
            order_type = kwargs.get('order_type', 'other')
            bank_code = kwargs.get('bank_code', '')
            
            params = {
                'vnp_Version': '2.1.0',
                'vnp_Command': 'pay',
                'vnp_TmnCode': self.tmn_code,
                'vnp_Amount': amount_int,
                'vnp_CurrCode': 'VND',
                'vnp_TxnRef': txn_ref,
                'vnp_OrderInfo': f'Thanh toan don hang {order.order_number}',
                'vnp_OrderType': order_type,
                'vnp_Locale': 'vn',
                'vnp_ReturnUrl': return_url,
                'vnp_IpAddr': ip_address,
                'vnp_CreateDate': create_date,
            }
            
            if bank_code:
                params['vnp_BankCode'] = bank_code
            
            # Build hash data
            hash_data = self._build_query_string(params)
            secure_hash = self._generate_hash(hash_data)
            
            params['vnp_SecureHash'] = secure_hash
            
            # Build payment URL
            query_string = self._build_query_string(params)
            payment_url = f"{self.payment_url}?{query_string}"
            
            return PaymentResult(
                success=True,
                transaction_id=txn_ref,
                gateway_transaction_id=txn_ref,
                payment_url=payment_url,
                raw_response=params
            )
            
        except Exception as e:
            logger.exception(f"VNPay payment creation error: {e}")
            return PaymentResult(
                success=False,
                error_code='CREATION_ERROR',
                error_message=str(e)
            )
    
    def verify_payment(
        self,
        transaction_id: str,
        gateway_data: Dict[str, Any]
    ) -> PaymentResult:
        """Verify payment from VNPay return URL."""
        try:
            # Extract secure hash
            received_hash = gateway_data.pop('vnp_SecureHash', '')
            gateway_data.pop('vnp_SecureHashType', None)
            
            # Rebuild hash for verification
            hash_data = self._build_query_string(gateway_data)
            expected_hash = self._generate_hash(hash_data)
            
            if not hmac.compare_digest(received_hash.lower(), expected_hash.lower()):
                return PaymentResult(
                    success=False,
                    error_code='INVALID_SIGNATURE',
                    error_message='Hash verification failed',
                    raw_response=gateway_data
                )
            
            response_code = gateway_data.get('vnp_ResponseCode', '')
            transaction_status = gateway_data.get('vnp_TransactionStatus', '')
            
            if response_code == '00' and transaction_status == '00':
                return PaymentResult(
                    success=True,
                    transaction_id=transaction_id,
                    gateway_transaction_id=gateway_data.get('vnp_TransactionNo', ''),
                    raw_response=gateway_data
                )
            else:
                error_messages = {
                    '07': 'Deduction successful, suspected fraud',
                    '09': 'Card not registered for Internet Banking',
                    '10': 'Invalid card verification (3+ times)',
                    '11': 'Payment timeout',
                    '12': 'Card locked',
                    '13': 'Invalid OTP',
                    '24': 'Transaction cancelled',
                    '51': 'Insufficient balance',
                    '65': 'Transaction limit exceeded',
                    '75': 'Bank under maintenance',
                    '79': 'Too many payment attempts',
                    '99': 'Unknown error',
                }
                
                return PaymentResult(
                    success=False,
                    transaction_id=transaction_id,
                    error_code=response_code,
                    error_message=error_messages.get(response_code, 'Payment failed'),
                    raw_response=gateway_data
                )
                
        except Exception as e:
            logger.exception(f"VNPay verification error: {e}")
            return PaymentResult(
                success=False,
                error_code='VERIFICATION_ERROR',
                error_message=str(e),
                raw_response=gateway_data
            )
    
    def process_webhook(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> PaymentResult:
        """Process VNPay IPN callback."""
        txn_ref = payload.get('vnp_TxnRef', '')
        return self.verify_payment(transaction_id=txn_ref, gateway_data=payload.copy())
    
    def _process_refund(
        self,
        transaction,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """Process VNPay refund via API."""
        try:
            import requests
            
            request_id = datetime.now().strftime('%Y%m%d%H%M%S')
            amount_int = int(amount) * 100
            
            params = {
                'vnp_RequestId': request_id,
                'vnp_Version': '2.1.0',
                'vnp_Command': 'refund',
                'vnp_TmnCode': self.tmn_code,
                'vnp_TransactionType': '02' if amount < transaction.amount else '03',
                'vnp_TxnRef': transaction.gateway_transaction_id,
                'vnp_Amount': amount_int,
                'vnp_OrderInfo': reason or 'Refund',
                'vnp_TransactionNo': transaction.gateway_response.get('vnp_TransactionNo', ''),
                'vnp_TransactionDate': transaction.gateway_response.get('vnp_PayDate', ''),
                'vnp_CreateBy': 'admin',
                'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
                'vnp_IpAddr': '127.0.0.1',
            }
            
            hash_data = self._build_query_string(params)
            params['vnp_SecureHash'] = self._generate_hash(hash_data)
            
            response = requests.post(self.api_url, json=params, timeout=30)
            data = response.json()
            
            if data.get('vnp_ResponseCode') == '00':
                return RefundResult(
                    success=True,
                    refund_id=request_id,
                    gateway_refund_id=data.get('vnp_TransactionNo', ''),
                    raw_response=data
                )
            else:
                return RefundResult(
                    success=False,
                    error_code=data.get('vnp_ResponseCode', 'UNKNOWN'),
                    error_message=data.get('vnp_Message', 'Refund failed'),
                    raw_response=data
                )
                
        except Exception as e:
            logger.exception(f"VNPay refund error: {e}")
            return RefundResult(
                success=False,
                error_code='REFUND_ERROR',
                error_message=str(e)
            )
