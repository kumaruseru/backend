"""
Common Utils - Security Utilities.
Refactored & Optimized for Production.

Provides security-related utilities:
- IPValidator: Robust client IP extraction with Proxy Trust support
- TokenGenerator: Cryptographically secure token generation
- CaptchaVerifier: Cloudflare Turnstile verification with optimized networking
- PasswordPolicy: Password strength validation
- SensitiveDataFilter: High-performance logging sanitizer
"""
import hashlib
import hmac
import secrets
import string
import logging
import re
import ipaddress
from typing import Optional, Tuple, List, Any
from django.conf import settings
from django.http import HttpRequest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger('apps.security')


# ==================== Logging Filter (High Performance) ====================

class SensitiveDataFilter(logging.Filter):
    """
    Logging filter to mask sensitive data in log messages.
    Optimized: Pre-compiles regex patterns for performance.
    """
    
    # Pre-compile patterns once at class level
    PATTERNS = [
        (re.compile(r'(password|passwd|pwd)["\']?\s*[:=]\s*["\']?[^"\']+["\']?', re.IGNORECASE), r'\1="***"'),
        (re.compile(r'(token|access_token|refresh_token)["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_\-\.]+(?:\.[a-zA-Z0-9_\-\.]+){2,}["\']?', re.IGNORECASE), r'\1="***.***.***"'), # JWT format
        (re.compile(r'(api[_-]?key|secret|client_secret)["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_\-]+["\']?', re.IGNORECASE), r'\1="***"'),
        (re.compile(r'authorization["\']?\s*[:=]\s*["\']?(bearer|basic)\s+[a-zA-Z0-9._\-]+["\']?', re.IGNORECASE), r'authorization="\1 ***"'),
        (re.compile(r'\b(?:\d{4}[- ]?){3}\d{4}\b'), '****-****-****-****'),  # Credit Card
        # Mask email but keep domain
        (re.compile(r'\b([a-zA-Z0-9._%+-]{3})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'), r'\1***@\2'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask sensitive data in log record."""
        if isinstance(record.msg, str):
            record.msg = self._mask_message(record.msg)
        
        if record.args:
            record.args = tuple(
                self._mask_message(str(arg)) if isinstance(arg, str) else arg 
                for arg in record.args
            )
        
        return True

    def _mask_message(self, message: str) -> str:
        """Apply all masking patterns to a string."""
        for pattern, replacement in self.PATTERNS:
            message = pattern.sub(replacement, message)
        return message


# ==================== IP Validator (Robust) ====================

class IPValidator:
    """
    Secure client IP extraction with trusted proxy support.
    Prevents IP Spoofing via X-Forwarded-For headers.
    """
    
    # Configurable via settings, default to localhost
    TRUSTED_PROXIES = getattr(settings, 'TRUSTED_PROXIES', ['127.0.0.1', '::1'])

    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """
        Extract the real client IP address.
        Logic:
        1. Cloudflare (CF-Connecting-IP) - If trusted
        2. X-Forwarded-For - Parse chain from right to left (stripping trusted proxies)
        3. X-Real-IP - Nginx standard
        4. REMOTE_ADDR - Direct connection
        """
        meta = request.META
        
        # 1. Cloudflare (High Trust if behind CF)
        if 'HTTP_CF_CONNECTING_IP' in meta:
            return meta['HTTP_CF_CONNECTING_IP']

        # 2. X-Forwarded-For (Standard Proxy Chain)
        x_forwarded_for = meta.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Split IPs and process from right (nearest proxy) to left (client)
            ips = [ip.strip() for ip in x_forwarded_for.split(',')]
            
            # Walk backwards, ignoring trusted proxies to find the first real client IP
            for ip in reversed(ips):
                if not IPValidator._is_valid_ip(ip):
                    continue
                if IPValidator._is_private_ip(ip):
                    continue
                # Found the first public, valid IP
                return ip

        # 3. Nginx / Standard Reverse Proxy
        if 'HTTP_X_REAL_IP' in meta:
            ip = meta['HTTP_X_REAL_IP']
            if IPValidator._is_valid_ip(ip):
                return ip

        # 4. Fallback
        return meta.get('REMOTE_ADDR', '127.0.0.1')

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """Check if IP is private (LAN, Docker, Localhost)."""
        try:
            return ipaddress.ip_address(ip).is_private
        except ValueError:
            return False


# ==================== Token Generator (Cryptographic) ====================

class TokenGenerator:
    """
    Secure token generation utilities.
    """
    
    @staticmethod
    def generate_url_safe_token(length: int = 32) -> str:
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_hex_token(length: int = 32) -> str:
        return secrets.token_hex(length // 2)
    
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate numeric OTP using CSPRNG."""
        # secrets.choice is cryptographically secure
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    @staticmethod
    def generate_api_key(prefix: str = 'sk') -> str:
        """
        Generate API key with format: prefix_randomstring
        Example: sk_live_51Ha...
        """
        # 24 bytes = ~32 chars base64
        key = secrets.token_urlsafe(24)
        return f"{prefix}_{key}"
    
    @staticmethod
    def generate_strong_password(length: int = 16) -> str:
        """Generate a random strong password compliant with policies."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))
            is_valid, _ = PasswordPolicy.validate(password)
            if is_valid:
                return password

    @staticmethod
    def verify_token_match(provided_token: str, stored_token: str) -> bool:
        """
        Constant-time comparison to prevent timing attacks.
        Both inputs must be strings.
        """
        return hmac.compare_digest(provided_token, stored_token)


# ==================== Captcha Verifier (Resilient) ====================

class CaptchaVerifier:
    """
    Cloudflare Turnstile CAPTCHA verification with connection pooling.
    """
    VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    
    # Reuse session for Keep-Alive connections
    _session = requests.Session()
    _adapter = HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.5))
    _session.mount('https://', _adapter)

    @classmethod
    def verify(cls, token: str, ip: Optional[str] = None) -> bool:
        secret_key = getattr(settings, 'CLOUDFLARE_TURNSTILE_SECRET_KEY', None)
        
        # Dev bypass
        if not secret_key:
            if settings.DEBUG:
                logger.debug("Turnstile Skipped (No Secret Key)")
                return True
            logger.critical("Turnstile Secret Key Missing in Production!")
            return False

        try:
            payload = {
                'secret': secret_key,
                'response': token,
            }
            if ip:
                payload['remoteip'] = ip

            response = cls._session.post(
                cls.VERIFY_URL, 
                data=payload, 
                timeout=5  # Fast timeout
            )
            response.raise_for_status()
            result = response.json()

            if result.get('success'):
                return True

            logger.warning(f"Turnstile Failed: {result.get('error-codes', [])} | IP: {ip}")
            return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Turnstile Connection Error: {str(e)}")
            # Fail closed for security, or open if availability is priority?
            # Usually fail closed for security features.
            return False


# ==================== Password Policy ====================

class PasswordPolicy:
    """Password strength validation rules."""
    
    MIN_LENGTH = 8
    SPECIAL_CHARS = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    @classmethod
    def validate(cls, password: str) -> Tuple[bool, List[str]]:
        errors = []
        
        if len(password) < cls.MIN_LENGTH:
            errors.append(f'Mật khẩu phải có ít nhất {cls.MIN_LENGTH} ký tự.')
        
        if not re.search(r'[A-Z]', password):
            errors.append('Mật khẩu cần ít nhất 1 chữ in hoa.')
            
        if not re.search(r'[a-z]', password):
            errors.append('Mật khẩu cần ít nhất 1 chữ thường.')
            
        if not re.search(r'\d', password):
            errors.append('Mật khẩu cần ít nhất 1 số.')
            
        if not any(c in cls.SPECIAL_CHARS for c in password):
            errors.append('Mật khẩu cần ít nhất 1 ký tự đặc biệt.')

        return len(errors) == 0, errors

    @staticmethod
    def is_common_password(password: str) -> bool:
        """Wrapper for Django's CommonPasswordValidator."""
        from django.contrib.auth.password_validation import CommonPasswordValidator, ValidationError
        validator = CommonPasswordValidator()
        try:
            validator.validate(password)
            return False
        except ValidationError:
            return True