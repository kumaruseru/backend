"""
Commerce Billing - Gateway Factory.

Factory for creating payment gateway instances.
Supports: VNPay, MoMo (COD is handled directly in service)
"""
from typing import Dict, Type
from .base import PaymentGateway
from .vnpay import VNPayGateway
from .momo import MoMoGateway


class PaymentGatewayFactory:
    """
    Factory for creating payment gateway instances.
    
    Usage:
        factory = PaymentGatewayFactory()
        gateway = factory.get_gateway('vnpay')
        payment_url = gateway.create_payment_url(...)
    """
    
    _gateways: Dict[str, Type[PaymentGateway]] = {
        'vnpay': VNPayGateway,
        'momo': MoMoGateway,
    }
    
    _instances: Dict[str, PaymentGateway] = {}
    
    @classmethod
    def get_gateway(cls, method: str) -> PaymentGateway:
        """
        Get payment gateway instance.
        
        Args:
            method: Payment method code (vnpay, momo)
            
        Returns:
            PaymentGateway instance
            
        Raises:
            ValueError: If method is not supported
        """
        if method not in cls._gateways:
            raise ValueError(f"Unsupported payment method: {method}")
        
        # Use singleton pattern for gateway instances
        if method not in cls._instances:
            cls._instances[method] = cls._gateways[method]()
        
        return cls._instances[method]
    
    @classmethod
    def supported_methods(cls) -> list[str]:
        """Get list of supported payment methods."""
        return list(cls._gateways.keys())
    
    @classmethod
    def register_gateway(cls, method: str, gateway_class: Type[PaymentGateway]) -> None:
        """Register a new payment gateway."""
        cls._gateways[method] = gateway_class


def get_gateway(method: str) -> PaymentGateway:
    """Convenience function to get gateway."""
    return PaymentGatewayFactory.get_gateway(method)
