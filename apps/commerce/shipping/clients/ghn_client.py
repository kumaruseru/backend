"""
GHN HTTP Client - Pure HTTP Communication Layer.

This client is ONLY responsible for:
- Making HTTP requests to GHN API
- Retry logic and timeout handling
- Returning raw JSON responses

No business logic or data transformation here.
"""
import logging
import requests
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger('apps.shipping.ghn')


class GHNClientError(Exception):
    """GHN API error."""
    def __init__(self, message: str, code: str = None, response: dict = None):
        self.message = message
        self.code = code
        self.response = response
        super().__init__(message)


class GHNClient:
    """
    Pure HTTP client for GHN API.
    
    All methods return raw JSON responses.
    Data transformation is done by GHNAdapter.
    """
    
    # API Endpoints
    BASE_URL = 'https://online-gateway.ghn.vn/shiip/public-api'
    SANDBOX_URL = 'https://dev-online-gateway.ghn.vn/shiip/public-api'
    
    # Timeouts
    DEFAULT_TIMEOUT = 10
    
    def __init__(self):
        self.token = getattr(settings, 'GHN_TOKEN', '')
        self.shop_id = getattr(settings, 'GHN_SHOP_ID', '')
        self.is_sandbox = getattr(settings, 'GHN_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if self.is_sandbox else self.BASE_URL
    
    @property
    def _headers(self) -> dict:
        """Default headers for GHN API."""
        return {
            'Content-Type': 'application/json',
            'Token': self.token,
            'ShopId': str(self.shop_id)
        }
    
    def request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        timeout: int = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to GHN API.
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint (e.g., '/v2/shipping-order/create')
            data: Request body
            timeout: Request timeout
            
        Returns:
            Raw JSON response
            
        Raises:
            GHNClientError: On API error
        """
        url = f"{self.base_url}{endpoint}"
        timeout = timeout or self.DEFAULT_TIMEOUT
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers,
                json=data,
                timeout=timeout
            )
            
            result = response.json()
            
            # GHN returns code 200 for success
            if result.get('code') != 200:
                raise GHNClientError(
                    message=result.get('message', 'Unknown error'),
                    code=str(result.get('code')),
                    response=result
                )
            
            return result
            
        except requests.Timeout:
            logger.error(f"GHN API timeout: {endpoint}")
            raise GHNClientError(message='API timeout', code='TIMEOUT')
        except requests.RequestException as e:
            logger.error(f"GHN API request failed: {e}")
            raise GHNClientError(message=str(e), code='REQUEST_ERROR')
    
    # ==================== Location APIs ====================
    
    def get_provinces(self) -> Dict:
        """Get all provinces."""
        return self.request('GET', '/master-data/province')
    
    def get_districts(self, province_id: int) -> Dict:
        """Get districts of a province."""
        return self.request('POST', '/master-data/district', {
            'province_id': province_id
        })
    
    def get_wards(self, district_id: int) -> Dict:
        """Get wards of a district."""
        return self.request('POST', '/master-data/ward', {
            'district_id': district_id
        })
    
    # ==================== Service APIs ====================
    
    def get_available_services(self, to_district_id: int) -> Dict:
        """Get available shipping services."""
        from_district = getattr(settings, 'GHN_FROM_DISTRICT_ID', 1454)
        return self.request('POST', '/v2/shipping-order/available-services', {
            'shop_id': int(self.shop_id),
            'from_district': from_district,
            'to_district': to_district_id
        })
    
    def calculate_fee(
        self,
        to_district_id: int,
        to_ward_code: str,
        weight: int = 500,
        insurance_value: int = 0,
        cod_amount: int = 0,
        service_id: int = None
    ) -> Dict:
        """Calculate shipping fee."""
        from_district = getattr(settings, 'GHN_FROM_DISTRICT_ID', 1454)
        from_ward = getattr(settings, 'GHN_FROM_WARD_CODE', '21211')
        
        data = {
            'from_district_id': from_district,
            'from_ward_code': from_ward,
            'to_district_id': to_district_id,
            'to_ward_code': str(to_ward_code),
            'weight': weight,
            'insurance_value': insurance_value,
            'cod_value': cod_amount,
            'service_type_id': 2  # E-commerce
        }
        
        if service_id:
            data['service_id'] = service_id
        
        return self.request('POST', '/v2/shipping-order/fee', data)
    
    # ==================== Order APIs ====================
    
    def create_order(self, order_data: Dict) -> Dict:
        """Create shipping order."""
        return self.request('POST', '/v2/shipping-order/create', order_data)
    
    def get_order_detail(self, order_code: str) -> Dict:
        """Get order details."""
        return self.request('POST', '/v2/shipping-order/detail', {
            'order_code': order_code
        })
    
    def cancel_order(self, order_codes: list) -> Dict:
        """Cancel shipping orders."""
        return self.request('POST', '/v2/switch-status/cancel', {
            'order_codes': order_codes
        })
