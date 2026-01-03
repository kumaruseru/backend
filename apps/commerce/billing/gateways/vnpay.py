"""
Commerce Billing - VNPay Gateway.

VNPay payment integration.
"""
import hashlib
import hmac
import urllib.parse
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from django.conf import settings
import logging

from .base import PaymentGateway, PaymentResult, RefundResult

logger = logging.getLogger('apps.billing')


class VNPayGateway(PaymentGateway):
    """VNPay payment gateway implementation."""
    
    def __init__(self):
        self.tmn_code = getattr(settings, 'VNPAY_TMN_CODE', '')
        self.hash_secret = getattr(settings, 'VNPAY_HASH_SECRET', '')
        self.payment_url = getattr(settings, 'VNPAY_PAYMENT_URL', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
        self.api_url = getattr(settings, 'VNPAY_API_URL', 'https://sandbox.vnpayment.vn/merchant_webapi/api/transaction')
    
    def create_payment_url(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: str,
        **kwargs
    ) -> str:
        """Create VNPay payment URL."""
        ip_address = kwargs.get('ip_address', '127.0.0.1')
        bank_code = kwargs.get('bank_code', '')
        
        # VNPay parameters
        params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': self.tmn_code,
            'vnp_Amount': int(amount) * 100,  # VNPay requires amount in đồng x 100
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': order_id,
            'vnp_OrderInfo': description[:255],
            'vnp_OrderType': 'other',
            'vnp_Locale': 'vn',
            'vnp_ReturnUrl': return_url,
            'vnp_IpAddr': ip_address,
            'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
        }
        
        if bank_code:
            params['vnp_BankCode'] = bank_code
        
        # Sort parameters and build query string
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Create signature
        signature = self._create_signature(query_string)
        
        # Build final URL
        payment_url = f"{self.payment_url}?{query_string}&vnp_SecureHash={signature}"
        
        logger.info(f"VNPay payment URL created for order {order_id}")
        return payment_url
    
    def verify_callback(self, data: Dict[str, Any]) -> PaymentResult:
        """Verify VNPay return callback."""
        # Extract signature
        received_signature = data.get('vnp_SecureHash', '')
        
        # Build query string without signature
        params = {k: v for k, v in data.items() if k.startswith('vnp_') and k != 'vnp_SecureHash' and k != 'vnp_SecureHashType'}
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Verify signature
        expected_signature = self._create_signature(query_string)
        
        if received_signature != expected_signature:
            logger.warning(f"VNPay signature mismatch for order {data.get('vnp_TxnRef')}")
            return PaymentResult(
                success=False,
                error_code='INVALID_SIGNATURE',
                error_message='Chữ ký không hợp lệ'
            )
        
        # Check response code
        response_code = data.get('vnp_ResponseCode')
        
        if response_code == '00':
            return PaymentResult(
                success=True,
                transaction_id=data.get('vnp_TransactionNo'),
                amount=Decimal(int(data.get('vnp_Amount', 0)) / 100),
                raw_data=data
            )
        else:
            return PaymentResult(
                success=False,
                error_code=response_code,
                error_message=self._get_error_message(response_code),
                raw_data=data
            )
    
    def verify_webhook(self, data: Dict[str, Any], signature: str = None) -> PaymentResult:
        """VNPay IPN verification."""
        return self.verify_callback(data)
    
    def refund(
        self,
        transaction_id: str,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """VNPay doesn't support direct refund via API."""
        return RefundResult(
            success=False,
            error_code='NOT_SUPPORTED',
            error_message='VNPay không hỗ trợ hoàn tiền tự động. Vui lòng xử lý thủ công.'
        )
    
    def check_payment_status(self, transaction_id: str) -> PaymentResult:
        """Query payment status from VNPay."""
        # VNPay query API implementation
        return PaymentResult(
            success=False,
            error_code='NOT_IMPLEMENTED',
            error_message='Chức năng đang phát triển'
        )
    
    def _create_signature(self, query_string: str) -> str:
        """Create HMAC-SHA512 signature."""
        signature = hmac.new(
            self.hash_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        return signature
    
    def _get_error_message(self, code: str) -> str:
        """Get human-readable error message."""
        messages = {
            '07': 'Giao dịch bị nghi ngờ gian lận',
            '09': 'Thẻ/Tài khoản chưa đăng ký Internet Banking',
            '10': 'Xác thực thất bại quá 3 lần',
            '11': 'Đã hết hạn giao dịch',
            '12': 'Thẻ/Tài khoản bị khóa',
            '13': 'Sai mật khẩu OTP',
            '24': 'Giao dịch bị hủy',
            '51': 'Tài khoản không đủ số dư',
            '65': 'Vượt hạn mức giao dịch trong ngày',
            '75': 'Ngân hàng đang bảo trì',
            '79': 'Sai mật khẩu thanh toán quá số lần quy định',
            '99': 'Lỗi không xác định',
        }
        return messages.get(code, 'Giao dịch thất bại')
