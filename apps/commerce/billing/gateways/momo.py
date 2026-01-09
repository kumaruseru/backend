"""MoMo Payment Gateway.

Integration with MoMo Vietnamese e-wallet using HMAC signature.
"""
import hashlib
import hmac
import json
import uuid
import logging
import requests
from decimal import Decimal
from typing import Dict, Any

from django.conf import settings

from .base import BasePaymentGateway, PaymentResult, RefundResult

logger = logging.getLogger('apps.billing.momo')


class MoMoGateway(BasePaymentGateway):
    """MoMo e-wallet payment gateway.
    
    Uses MoMo Payment Gateway API v2 with HMAC-SHA256 signatures.
    """
    
    gateway_code = 'momo'
    gateway_name = 'MoMo'
    supports_refund = True
    supports_webhook = True
    
    def __init__(self):
        self.partner_code = getattr(settings, 'MOMO_PARTNER_CODE', '')
        self.access_key = getattr(settings, 'MOMO_ACCESS_KEY', '')
        self.secret_key = getattr(settings, 'MOMO_SECRET_KEY', '')
        self.endpoint = getattr(
            settings, 'MOMO_ENDPOINT',
            'https://test-payment.momo.vn/v2/gateway/api'
        )
    
    def _generate_signature(self, raw_data: str) -> str:
        """Generate HMAC-SHA256 signature."""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            raw_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def create_payment(
        self,
        order,
        amount: Decimal,
        currency: str = 'VND',
        return_url: str = '',
        cancel_url: str = '',
        **kwargs
    ) -> PaymentResult:
        """Create MoMo payment request."""
        try:
            request_id = str(uuid.uuid4())
            order_id = f"MOMO{order.order_number}"
            amount_int = int(amount)
            
            notify_url = kwargs.get('notify_url', return_url.replace('/return/', '/notify/'))
            extra_data = kwargs.get('extra_data', '')
            
            # Build raw signature string
            raw_signature = '&'.join([
                f"accessKey={self.access_key}",
                f"amount={amount_int}",
                f"extraData={extra_data}",
                f"ipnUrl={notify_url}",
                f"orderId={order_id}",
                f"orderInfo=Payment for order {order.order_number}",
                f"partnerCode={self.partner_code}",
                f"redirectUrl={return_url}",
                f"requestId={request_id}",
                f"requestType=captureWallet",
            ])
            
            signature = self._generate_signature(raw_signature)
            
            payload = {
                'partnerCode': self.partner_code,
                'accessKey': self.access_key,
                'requestId': request_id,
                'amount': amount_int,
                'orderId': order_id,
                'orderInfo': f'Payment for order {order.order_number}',
                'redirectUrl': return_url,
                'ipnUrl': notify_url,
                'extraData': extra_data,
                'requestType': 'captureWallet',
                'signature': signature,
                'lang': 'vi',
            }
            
            response = requests.post(
                f"{self.endpoint}/create",
                json=payload,
                timeout=30
            )
            data = response.json()
            
            if data.get('resultCode') == 0:
                return PaymentResult(
                    success=True,
                    transaction_id=request_id,
                    gateway_transaction_id=order_id,
                    payment_url=data.get('payUrl', ''),
                    raw_response=data
                )
            else:
                return PaymentResult(
                    success=False,
                    transaction_id=request_id,
                    error_code=str(data.get('resultCode', 'UNKNOWN')),
                    error_message=data.get('message', 'MoMo payment creation failed'),
                    raw_response=data
                )
                
        except requests.RequestException as e:
            logger.exception(f"MoMo API error: {e}")
            return PaymentResult(
                success=False,
                error_code='CONNECTION_ERROR',
                error_message=str(e)
            )
    
    def verify_payment(
        self,
        transaction_id: str,
        gateway_data: Dict[str, Any]
    ) -> PaymentResult:
        """Verify payment from MoMo redirect callback."""
        try:
            result_code = gateway_data.get('resultCode')
            
            # Verify signature
            received_signature = gateway_data.get('signature', '')
            raw_signature = '&'.join([
                f"accessKey={self.access_key}",
                f"amount={gateway_data.get('amount', '')}",
                f"extraData={gateway_data.get('extraData', '')}",
                f"message={gateway_data.get('message', '')}",
                f"orderId={gateway_data.get('orderId', '')}",
                f"orderInfo={gateway_data.get('orderInfo', '')}",
                f"orderType={gateway_data.get('orderType', '')}",
                f"partnerCode={self.partner_code}",
                f"payType={gateway_data.get('payType', '')}",
                f"requestId={gateway_data.get('requestId', '')}",
                f"responseTime={gateway_data.get('responseTime', '')}",
                f"resultCode={result_code}",
                f"transId={gateway_data.get('transId', '')}",
            ])
            
            expected_signature = self._generate_signature(raw_signature)
            
            if not hmac.compare_digest(received_signature, expected_signature):
                return PaymentResult(
                    success=False,
                    error_code='INVALID_SIGNATURE',
                    error_message='Signature verification failed',
                    raw_response=gateway_data
                )
            
            if result_code == 0:
                return PaymentResult(
                    success=True,
                    transaction_id=transaction_id,
                    gateway_transaction_id=str(gateway_data.get('transId', '')),
                    raw_response=gateway_data
                )
            else:
                return PaymentResult(
                    success=False,
                    transaction_id=transaction_id,
                    error_code=str(result_code),
                    error_message=gateway_data.get('message', 'Payment failed'),
                    raw_response=gateway_data
                )
                
        except Exception as e:
            logger.exception(f"MoMo verification error: {e}")
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
        """Process MoMo IPN webhook."""
        return self.verify_payment(
            transaction_id=payload.get('requestId', ''),
            gateway_data=payload
        )
    
    def _process_refund(
        self,
        transaction,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """Process MoMo refund."""
        try:
            request_id = str(uuid.uuid4())
            amount_int = int(amount)
            
            raw_signature = '&'.join([
                f"accessKey={self.access_key}",
                f"amount={amount_int}",
                f"description={reason}",
                f"orderId={transaction.gateway_transaction_id}",
                f"partnerCode={self.partner_code}",
                f"requestId={request_id}",
                f"transId={transaction.gateway_transaction_id}",
            ])
            
            signature = self._generate_signature(raw_signature)
            
            payload = {
                'partnerCode': self.partner_code,
                'accessKey': self.access_key,
                'requestId': request_id,
                'orderId': transaction.gateway_transaction_id,
                'transId': transaction.gateway_transaction_id,
                'amount': amount_int,
                'description': reason,
                'signature': signature,
                'lang': 'vi',
            }
            
            response = requests.post(
                f"{self.endpoint}/refund",
                json=payload,
                timeout=30
            )
            data = response.json()
            
            if data.get('resultCode') == 0:
                return RefundResult(
                    success=True,
                    refund_id=request_id,
                    gateway_refund_id=str(data.get('transId', '')),
                    raw_response=data
                )
            else:
                return RefundResult(
                    success=False,
                    error_code=str(data.get('resultCode', 'UNKNOWN')),
                    error_message=data.get('message', 'Refund failed'),
                    raw_response=data
                )
                
        except Exception as e:
            logger.exception(f"MoMo refund error: {e}")
            return RefundResult(
                success=False,
                error_code='REFUND_ERROR',
                error_message=str(e)
            )
