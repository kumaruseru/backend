"""Payment Gateway - Base Abstract Class."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal


@dataclass
class PaymentResult:
    """Result of a payment operation."""
    success: bool
    transaction_id: str = ''
    gateway_transaction_id: str = ''
    payment_url: str = ''
    error_code: str = ''
    error_message: str = ''
    raw_response: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.raw_response is None:
            self.raw_response = {}


@dataclass
class RefundResult:
    """Result of a refund operation."""
    success: bool
    refund_id: str = ''
    gateway_refund_id: str = ''
    error_code: str = ''
    error_message: str = ''
    raw_response: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.raw_response is None:
            self.raw_response = {}


class BasePaymentGateway(ABC):
    """Abstract base class for payment gateways.
    
    All payment gateways must implement these methods to ensure
    consistent behavior across different payment providers.
    """
    
    gateway_code: str = ''
    gateway_name: str = ''
    supports_refund: bool = True
    supports_webhook: bool = True
    
    @abstractmethod
    def create_payment(
        self,
        order,
        amount: Decimal,
        currency: str = 'VND',
        return_url: str = '',
        cancel_url: str = '',
        **kwargs
    ) -> PaymentResult:
        """Create a payment request.
        
        Args:
            order: Order instance
            amount: Payment amount
            currency: Currency code (default VND)
            return_url: URL to redirect after payment
            cancel_url: URL for cancellation
            **kwargs: Additional gateway-specific parameters
            
        Returns:
            PaymentResult with payment URL or error
        """
        pass
    
    @abstractmethod
    def verify_payment(
        self,
        transaction_id: str,
        gateway_data: Dict[str, Any]
    ) -> PaymentResult:
        """Verify payment completion from gateway callback.
        
        Args:
            transaction_id: Our internal transaction ID
            gateway_data: Data from gateway callback
            
        Returns:
            PaymentResult indicating success/failure
        """
        pass
    
    @abstractmethod
    def process_webhook(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> PaymentResult:
        """Process webhook notification from gateway.
        
        Args:
            payload: Webhook payload
            headers: HTTP headers for signature verification
            
        Returns:
            PaymentResult with transaction status
        """
        pass
    
    def create_refund(
        self,
        transaction,
        amount: Decimal,
        reason: str = ''
    ) -> RefundResult:
        """Create a refund request.
        
        Args:
            transaction: PaymentTransaction instance
            amount: Refund amount
            reason: Reason for refund
            
        Returns:
            RefundResult indicating success/failure
        """
        if not self.supports_refund:
            return RefundResult(
                success=False,
                error_code='NOT_SUPPORTED',
                error_message=f'{self.gateway_name} does not support refunds'
            )
        return self._process_refund(transaction, amount, reason)
    
    def _process_refund(
        self,
        transaction,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """Override in subclass if refunds are supported."""
        raise NotImplementedError
    
    @staticmethod
    def generate_signature(*args, secret_key: str) -> str:
        """Generate HMAC signature for request validation."""
        import hmac
        import hashlib
        
        data = ''.join(str(arg) for arg in args)
        return hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def verify_signature(data: str, signature: str, secret_key: str) -> bool:
        """Verify HMAC signature."""
        import hmac
        import hashlib
        
        expected = hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
