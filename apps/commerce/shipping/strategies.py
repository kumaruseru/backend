"""
Shipping calculation strategies.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional
from django.conf import settings
from apps.common.core.exceptions import BusinessRuleViolation
import logging

logger = logging.getLogger('apps.shipping')

class ShippingCalculatorStrategy(ABC):
    """Abstract base class for shipping calculation."""
    
    @abstractmethod
    def calculate(
        self,
        subtotal: Decimal,
        district_id: Optional[int] = None,
        ward_code: Optional[str] = None,
        weight: int = 500
    ) -> Decimal:
        """Calculate shipping fee."""
        pass

class FixedPriceShippingStrategy(ShippingCalculatorStrategy):
    """
    Fixed price strategy with weight-based surcharge.
    
    - Free if subtotal > threshold
    - Base fee + Surcharge for heavy items if subtotal < threshold
    """
    
    def calculate(
        self,
        subtotal: Decimal,
        district_id: Optional[int] = None,
        ward_code: Optional[str] = None,
        weight: int = 500
    ) -> Decimal:
        free_shipping_threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', 500000)
        
        # Business Rule: High value orders get free shipping regardless of weight (can be adjusted)
        if subtotal >= free_shipping_threshold:
            return Decimal('0')

        base_fee = Decimal(getattr(settings, 'DEFAULT_SHIPPING_FEE', 30000))
        
        # Advanced: Add weight surcharge
        # Example: +5,000 VND for every 500g over 2kg
        THRESHOLD_WEIGHT = 2000  # 2kg
        SURCHARGE_STEP = 500     # 500g
        SURCHARGE_AMOUNT = Decimal('5000')
        
        if weight > THRESHOLD_WEIGHT:
            extra_weight = weight - THRESHOLD_WEIGHT
            steps = (extra_weight + SURCHARGE_STEP - 1) // SURCHARGE_STEP
            surcharge = steps * SURCHARGE_AMOUNT
            return base_fee + surcharge
            
        return base_fee

class GHNShippingStrategy(ShippingCalculatorStrategy):
    """
    GHN API strategy with Circuit Breaker pattern.
    
    - Validates location strictly.
    - Falls back to FixedPriceStrategy (Smart Calculation) on API failure.
    """
    
    def calculate(
        self,
        subtotal: Decimal,
        district_id: Optional[int] = None,
        ward_code: Optional[str] = None,
        weight: int = 500
    ) -> Decimal:
        # 1. Business Rule: Free shipping check first
        free_shipping_threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', 500000)
        if subtotal >= free_shipping_threshold:
            return Decimal('0')
            
        # 2. Strict Validation (Advanced)
        # We block checkout if address is incomplete to prevent delivery issues.
        if not district_id or not ward_code:
             logger.warning("Shipping calculation failed: Missing location info.")
             raise BusinessRuleViolation(
                 message="Vui lòng cập nhật đầy đủ thông tin Quận/Huyện và Phường/Xã để tính phí vận chuyển."
             )

        # 3. Call External API
        try:
            from apps.commerce.shipping.services import GHNService
            ghn = GHNService()
            result = ghn.calculate_fee(
                to_district_id=district_id,
                to_ward_code=ward_code,
                weight=weight
            )
            
            if result.get('success'):
                return Decimal(result.get('total', 30000))
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"GHN calculation failed: {error_msg}. Using fallback.")
                # API logic failed (e.g. out of service area), fallback to Smart Fixed Price
                return self._fallback_calculation(subtotal, weight)
                
        except Exception as e:
            logger.warning(f"GHN strategy system error: {e}. Using fallback.")
            # System error (Network/Timeout), fallback to Smart Fixed Price
            return self._fallback_calculation(subtotal, weight)

    def _fallback_calculation(self, subtotal: Decimal, weight: int) -> Decimal:
        """Delegate to FixedPriceStrategy for consistency."""
        fallback = FixedPriceShippingStrategy()
        return fallback.calculate(subtotal=subtotal, weight=weight)

class ShippingStrategyFactory:
    """Factory to get the appropriate strategy."""
    
    @staticmethod
    def get_strategy(provider: str = 'ghn') -> ShippingCalculatorStrategy:
        if provider == 'ghn':
            return GHNShippingStrategy()
        return FixedPriceShippingStrategy()
