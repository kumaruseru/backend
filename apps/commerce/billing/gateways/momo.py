"""
Commerce Billing - MoMo Gateway.

MoMo payment integration.
"""
import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from typing import Dict, Any
from django.conf import settings
import requests
import logging

from .base import PaymentGateway, PaymentResult, RefundResult

logger = logging.getLogger('apps.billing')


class MoMoGateway(PaymentGateway):
    """MoMo payment gateway implementation."""
    
    def __init__(self):
        self.partner_code = getattr(settings, 'MOMO_PARTNER_CODE', '')
        self.access_key = getattr(settings, 'MOMO_ACCESS_KEY', '')
        self.secret_key = getattr(settings, 'MOMO_SECRET_KEY', '')
        self.endpoint = getattr(settings, 'MOMO_ENDPOINT', 'https://test-payment.momo.vn')
    
    def create_payment_url(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: str,
        **kwargs
    ) -> str:
        """Create MoMo payment URL."""
        notify_url = kwargs.get('notify_url', return_url)
        request_id = str(uuid.uuid4())
        
        # Build raw signature string
        raw_signature = (
            f"accessKey={self.access_key}"
            f"&amount={int(amount)}"
            f"&extraData="
            f"&ipnUrl={notify_url}"
            f"&orderId={order_id}"
            f"&orderInfo={description}"
            f"&partnerCode={self.partner_code}"
            f"&redirectUrl={return_url}"
            f"&requestId={request_id}"
            f"&requestType=payWithMethod"
        )
        
        # Create HMAC-SHA256 signature
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Request body
        payload = {
            'partnerCode': self.partner_code,
            'partnerName': 'OWLS Store',
            'storeId': self.partner_code,
            'requestId': request_id,
            'amount': int(amount),
            'orderId': order_id,
            'orderInfo': description,
            'redirectUrl': return_url,
            'ipnUrl': notify_url,
            'lang': 'vi',
            'requestType': 'payWithMethod',
            'autoCapture': True,
            'extraData': '',
            'signature': signature
        }
        
        try:
            response = requests.post(
                f"{self.endpoint}/v2/gateway/api/create",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            result = response.json()
            
            if result.get('resultCode') == 0:
                logger.info(f"MoMo payment URL created for order {order_id}")
                return result.get('payUrl', '')
            else:
                logger.error(f"MoMo create payment failed: {result}")
                return ''
                
        except requests.RequestException as e:
            logger.error(f"MoMo API error: {e}")
            return ''
    
    def verify_callback(self, data: Dict[str, Any]) -> PaymentResult:
        """Verify MoMo return callback."""
        # Build raw signature for verification
        raw_signature = (
            f"accessKey={self.access_key}"
            f"&amount={data.get('amount')}"
            f"&extraData={data.get('extraData', '')}"
            f"&message={data.get('message')}"
            f"&orderId={data.get('orderId')}"
            f"&orderInfo={data.get('orderInfo')}"
            f"&orderType={data.get('orderType')}"
            f"&partnerCode={data.get('partnerCode')}"
            f"&payType={data.get('payType')}"
            f"&requestId={data.get('requestId')}"
            f"&responseTime={data.get('responseTime')}"
            f"&resultCode={data.get('resultCode')}"
            f"&transId={data.get('transId')}"
        )
        
        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if data.get('signature') != expected_signature:
            logger.warning(f"MoMo signature mismatch for order {data.get('orderId')}")
            return PaymentResult(
                success=False,
                error_code='INVALID_SIGNATURE',
                error_message='Chữ ký không hợp lệ'
            )
        
        result_code = int(data.get('resultCode', -1))
        
        if result_code == 0:
            return PaymentResult(
                success=True,
                transaction_id=str(data.get('transId')),
                amount=Decimal(data.get('amount', 0)),
                raw_data=data
            )
        else:
            return PaymentResult(
                success=False,
                error_code=str(result_code),
                error_message=data.get('message', 'Giao dịch thất bại'),
                raw_data=data
            )
    
    def verify_webhook(self, data: Dict[str, Any], signature: str = None) -> PaymentResult:
        """MoMo IPN verification."""
        return self.verify_callback(data)
    
    def refund(
        self,
        transaction_id: str,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """Process MoMo refund."""
        request_id = str(uuid.uuid4())
        
        raw_signature = (
            f"accessKey={self.access_key}"
            f"&amount={int(amount)}"
            f"&description={reason}"
            f"&orderId={request_id}"
            f"&partnerCode={self.partner_code}"
            f"&requestId={request_id}"
            f"&transId={transaction_id}"
        )
        
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        payload = {
            'partnerCode': self.partner_code,
            'orderId': request_id,
            'requestId': request_id,
            'amount': int(amount),
            'transId': transaction_id,
            'lang': 'vi',
            'description': reason,
            'signature': signature
        }
        
        try:
            response = requests.post(
                f"{self.endpoint}/v2/gateway/api/refund",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            result = response.json()
            
            if result.get('resultCode') == 0:
                return RefundResult(
                    success=True,
                    refund_id=str(result.get('transId')),
                    amount=Decimal(amount),
                    raw_data=result
                )
            else:
                return RefundResult(
                    success=False,
                    error_code=str(result.get('resultCode')),
                    error_message=result.get('message'),
                    raw_data=result
                )
                
        except requests.RequestException as e:
            logger.error(f"MoMo refund error: {e}")
            return RefundResult(
                success=False,
                error_code='REQUEST_ERROR',
                error_message=str(e)
            )
    
    def check_payment_status(self, transaction_id: str) -> PaymentResult:
        """Query payment status from MoMo."""
        return PaymentResult(
            success=False,
            error_code='NOT_IMPLEMENTED',
            error_message='Chức năng đang phát triển'
        )
