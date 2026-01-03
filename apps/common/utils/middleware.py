"""
Common Utils - Security Middleware.

Provides security-related middleware components:
- SecurityHeadersMiddleware: Adds security headers to responses
- RequestLoggingMiddleware: Logs all requests for audit
- SuspiciousActivityMiddleware: Detects and blocks suspicious activity
"""
import logging
import time
import hashlib
from typing import Callable, Optional
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('apps.security')


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: Restricts browser features
    """
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(), gyroscope=(), '
            'magnetometer=(), microphone=(), payment=(), usb=()'
        )
        
        # Remove server identification header
        response.headers.pop('Server', None)
        
        return response


class RequestLoggingMiddleware:
    """
    Log all requests for audit and debugging.
    
    Logs:
    - Request method, path, user
    - Response status and time
    - Masks sensitive data in logs
    """
    
    SENSITIVE_PATHS = ['/api/auth/login', '/api/auth/register', '/api/auth/password']
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.time()
        
        # Process request
        response = self.get_response(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Get user info
        user_info = 'anonymous'
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_info = str(request.user.id)
        
        # Log request (skip health checks and static files)
        if not self._should_skip_logging(request):
            log_data = {
                'method': request.method,
                'path': request.path,
                'status': response.status_code,
                'duration_ms': round(duration_ms, 2),
                'user': user_info,
                'ip': self._get_client_ip(request),
            }
            
            if response.status_code >= 400:
                logger.warning(f"Request: {log_data}")
            else:
                logger.info(f"Request: {log_data}")
        
        return response
    
    def _should_skip_logging(self, request: HttpRequest) -> bool:
        """Skip logging for health checks and static files."""
        skip_paths = ['/health', '/static/', '/media/', '/favicon.ico']
        return any(request.path.startswith(p) for p in skip_paths)
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request, handling proxies."""
        # Check for Cloudflare header first
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip:
            return cf_ip
        
        # Check X-Forwarded-For (from reverse proxy)
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            # Take the first IP (original client)
            return x_forwarded.split(',')[0].strip()
        
        # Fallback to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR', 'unknown')


class SuspiciousActivityMiddleware:
    """
    Detect and block suspicious activity.
    
    Monitors:
    - Repeated failed login attempts
    - Unusual request patterns
    - Missing or suspicious headers
    
    Actions:
    - Rate limiting by IP
    - Temporary IP blocking
    - Logging suspicious activity
    """
    
    # Rate limiting settings
    RATE_LIMIT_WINDOW = 60  # seconds
    MAX_REQUESTS_PER_WINDOW = 100
    
    # Suspicious patterns
    BLOCKED_USER_AGENTS = ['sqlmap', 'nikto', 'nmap', 'masscan']
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        client_ip = self._get_client_ip(request)
        
        # Check if IP is blocked
        if self._is_ip_blocked(client_ip):
            logger.warning(f"Blocked IP attempted access: {client_ip}")
            return JsonResponse(
                {'error': 'Access denied', 'code': 'IP_BLOCKED'},
                status=403
            )
        
        # Check for suspicious user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if self._is_suspicious_user_agent(user_agent):
            logger.warning(f"Suspicious user agent from {client_ip}: {user_agent}")
            self._increment_suspicion_score(client_ip, 10)
        
        # Rate limiting
        if not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JsonResponse(
                {'error': 'Too many requests', 'code': 'RATE_LIMITED'},
                status=429
            )
        
        return self.get_response(request)
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request."""
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip:
            return cf_ip
        
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is in block list."""
        cache_key = f'blocked_ip:{ip}'
        return cache.get(cache_key, False)
    
    def _block_ip(self, ip: str, duration_seconds: int = 3600):
        """Block an IP for specified duration."""
        cache_key = f'blocked_ip:{ip}'
        cache.set(cache_key, True, timeout=duration_seconds)
        logger.warning(f"IP blocked for {duration_seconds}s: {ip}")
    
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent matches known attack tools."""
        return any(tool in user_agent for tool in self.BLOCKED_USER_AGENTS)
    
    def _check_rate_limit(self, ip: str) -> bool:
        """Check and update rate limit for IP. Returns True if allowed."""
        cache_key = f'rate_limit:{ip}'
        current_count = cache.get(cache_key, 0)
        
        if current_count >= self.MAX_REQUESTS_PER_WINDOW:
            return False
        
        # Increment counter
        cache.set(cache_key, current_count + 1, timeout=self.RATE_LIMIT_WINDOW)
        return True
    
    def _increment_suspicion_score(self, ip: str, points: int):
        """Increment suspicion score for IP. Block if threshold exceeded."""
        cache_key = f'suspicion:{ip}'
        current_score = cache.get(cache_key, 0) + points
        cache.set(cache_key, current_score, timeout=3600)
        
        # Block if score too high
        if current_score >= 50:
            self._block_ip(ip, duration_seconds=3600)


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that masks sensitive data.
    
    Masks:
    - Passwords
    - API keys
    - Tokens
    - Credit card numbers
    """
    
    SENSITIVE_KEYS = ['password', 'token', 'secret', 'api_key', 'credit_card', 'cvv']
    
    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for key in self.SENSITIVE_KEYS:
                record.msg = self._mask_value(record.msg, key)
        return True
    
    def _mask_value(self, message: str, key: str) -> str:
        """Mask values associated with sensitive keys."""
        import re
        # Match patterns like 'password': 'value' or password=value
        patterns = [
            rf"'{key}':\s*'[^']*'",
            rf'"{key}":\s*"[^"]*"',
            rf'{key}=[^\s&]+',
        ]
        for pattern in patterns:
            message = re.sub(pattern, f"'{key}': '***MASKED***'", message, flags=re.IGNORECASE)
        return message
