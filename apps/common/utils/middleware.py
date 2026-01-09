"""Common Utils - Security Middleware."""
import logging
import time
from typing import Callable
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.core.cache import cache

logger = logging.getLogger('apps.security')


class SecurityHeadersMiddleware:
    """Add security headers to all responses."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()'
        response.headers.pop('Server', None)
        return response


class RequestLoggingMiddleware:
    """Log all requests for audit and debugging."""
    SKIP_PATHS = ['/health', '/static/', '/media/', '/favicon.ico']

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.time()
        response = self.get_response(request)
        duration_ms = (time.time() - start_time) * 1000
        user_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else None
        if not any(request.path.startswith(p) for p in self.SKIP_PATHS):
            log_data = {
                'method': request.method,
                'path': request.path,
                'status': response.status_code,
                'duration_ms': round(duration_ms, 2),
                'user_id': user_id,
                'client_ip': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100],
            }
            if response.status_code >= 400:
                logger.warning('Request completed', extra=log_data)
            else:
                logger.info('Request completed', extra=log_data)
        return response

    def _get_client_ip(self, request: HttpRequest) -> str:
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip:
            return cf_ip
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class SuspiciousActivityMiddleware:
    """Detect and block suspicious activity."""
    RATE_LIMIT_WINDOW = 60
    MAX_REQUESTS_PER_WINDOW = 100
    BLOCKED_USER_AGENTS = ['sqlmap', 'nikto', 'nmap', 'masscan', 'dirbuster']

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        client_ip = self._get_client_ip(request)
        if self._is_ip_blocked(client_ip):
            logger.warning(f"Blocked IP attempted access: {client_ip}")
            return JsonResponse({'error': 'Access denied', 'code': 'IP_BLOCKED'}, status=403)
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if self._is_suspicious_user_agent(user_agent):
            logger.warning(f"Suspicious user agent from {client_ip}: {user_agent}")
            self._increment_suspicion_score(client_ip, 10)
        if not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JsonResponse({'error': 'Too many requests', 'code': 'RATE_LIMITED'}, status=429)
        return self.get_response(request)

    def _get_client_ip(self, request: HttpRequest) -> str:
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip:
            return cf_ip
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')

    def _is_ip_blocked(self, ip: str) -> bool:
        return cache.get(f'blocked_ip:{ip}', False)

    def _block_ip(self, ip: str, duration_seconds: int = 3600):
        cache.set(f'blocked_ip:{ip}', True, timeout=duration_seconds)
        logger.warning(f"IP blocked for {duration_seconds}s: {ip}")

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        return any(tool in user_agent for tool in self.BLOCKED_USER_AGENTS)

    def _check_rate_limit(self, ip: str) -> bool:
        cache_key = f'rate_limit:{ip}'
        current_count = cache.get(cache_key, 0)
        if current_count >= self.MAX_REQUESTS_PER_WINDOW:
            return False
        cache.set(cache_key, current_count + 1, timeout=self.RATE_LIMIT_WINDOW)
        return True

    def _increment_suspicion_score(self, ip: str, points: int):
        cache_key = f'suspicion:{ip}'
        current_score = cache.get(cache_key, 0) + points
        cache.set(cache_key, current_score, timeout=3600)
        if current_score >= 50:
            self._block_ip(ip, duration_seconds=3600)


class SensitiveDataFilter(logging.Filter):
    """Log filter that masks sensitive data."""
    SENSITIVE_KEYS = ['password', 'token', 'secret', 'api_key', 'credit_card', 'cvv']

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            import re
            for key in self.SENSITIVE_KEYS:
                patterns = [rf"'{key}':\s*'[^']*'", rf'"{key}":\s*"[^"]*"', rf'{key}=[^\s&]+']
                for pattern in patterns:
                    record.msg = re.sub(pattern, f"'{key}': '***MASKED***'", record.msg, flags=re.IGNORECASE)
        return True


class Admin2FAEnforcementMiddleware:
    """Redirect admin users to 2FA setup if not configured."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith('/admin-login/') and not request.path.startswith('/account/'):
            if hasattr(request, 'user') and request.user.is_authenticated:
                if request.user.is_staff and not self._has_2fa(request.user):
                    from django.shortcuts import redirect
                    return redirect('two_factor:setup')
        return self.get_response(request)

    def _has_2fa(self, user) -> bool:
        from django_otp import user_has_device
        return user_has_device(user)
