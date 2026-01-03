"""
Commerce Billing - Payment Gateway Interface.

Abstract interface for payment gateway implementations.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass
class PaymentResult:
    """Result from payment verification."""
    success: bool
    transaction_id: Optional[str] = None
    amount: Optional[Decimal] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class RefundResult:
    """Result from refund request."""
    success: bool
    refund_id: Optional[str] = None
    amount: Optional[Decimal] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class PaymentGateway(ABC):
    """
    Abstract payment gateway interface.
    
    All payment providers must implement this interface.
    """
    
    @abstractmethod
    def create_payment_url(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: str,
        **kwargs
    ) -> str:
        """
        Create a payment URL for redirect.
        
        Args:
            order_id: Unique order identifier
            amount: Payment amount
            description: Payment description
            return_url: URL to return after payment
            
        Returns:
            Payment URL for redirect
        """
        pass
    
    @abstractmethod
    def verify_callback(self, data: Dict[str, Any]) -> PaymentResult:
        """
        Verify payment callback/return data.
        
        Args:
            data: Callback data from payment provider
            
        Returns:
            PaymentResult with success status and details
        """
        pass
    
    @abstractmethod
    def verify_webhook(self, data: Dict[str, Any], signature: str = None) -> PaymentResult:
        """
        Verify webhook notification.
        
        Args:
            data: Webhook payload
            signature: Signature header for verification
            
        Returns:
            PaymentResult with success status and details
        """
        pass
    
    @abstractmethod
    def refund(
        self,
        transaction_id: str,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """
        Process a refund.
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount
            reason: Refund reason
            
        Returns:
            RefundResult with success status and details
        """
        pass
    
    @abstractmethod
    def check_payment_status(self, transaction_id: str) -> PaymentResult:
        """
        Check payment status.
        
        Args:
            transaction_id: Transaction ID to check
            
        Returns:
            PaymentResult with current status
        """
        pass
