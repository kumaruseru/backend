"""
Common Utils - Security Utilities.

Provides security-related utilities:
- IPValidator: Secure client IP extraction
- TokenGenerator: Secure token generation
- CAPTCHA verification
- Password utilities
- SensitiveDataFilter: Logging filter
"""
import hashlib
import hmac
import secrets
import string
import logging
import re
from typing import Optional
from django.conf import settings
from django.http import HttpRequest
import requests

logger = logging.getLogger('apps.security')


# ==================== Logging Filter ====================

class SensitiveDataFilter(logging.Filter):
    """
    Logging filter to mask sensitive data in log messages.
    
    Masks:
    - Passwords
    - API keys
    - Tokens
    - Credit card numbers
    - Email addresses (partial)
    """
    
    # Patterns to mask
    PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\']+["\']?', 'password="***"'),
        (r'token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+["\']?', 'token="***"'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+["\']?', 'api_key="***"'),
        (r'secret["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+["\']?', 'secret="***"'),
        (r'authorization["\']?\s*[:=]\s*["\']?bearer\s+[a-zA-Z0-9_.-]+["\']?', 'authorization="Bearer ***"'),
        (r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '****-****-****-****'),  # Card numbers
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask sensitive data in log record."""
        if record.msg:
            message = str(record.msg)
            for pattern, replacement in self.PATTERNS:
                message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
            record.msg = message
        
        # Also filter args if present
        if record.args:
            args = list(record.args)
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    for pattern, replacement in self.PATTERNS:
                        arg = re.sub(pattern, replacement, arg, flags=re.IGNORECASE)
                    args[i] = arg
            record.args = tuple(args)
        
        return True


class IPValidator:
    """
    Secure client IP extraction from HTTP requests.
    
    Handles various proxy scenarios:
    - Cloudflare (CF-Connecting-IP)
    - Standard proxies (X-Forwarded-For)
    - Direct connections (REMOTE_ADDR)
    
    SECURITY: Always validate and sanitize IP addresses.
    """
    
    # Trusted proxy networks (Cloudflare, internal)
    TRUSTED_PROXIES = ['127.0.0.1', '::1']
    
    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """
        Extract the real client IP address from request.
        
        Priority:
        1. CF-Connecting-IP (Cloudflare)
        2. X-Forwarded-For (first non-private IP)
        3. REMOTE_ADDR (fallback)
        """
        # Cloudflare - most trusted
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip and IPValidator._is_valid_ip(cf_ip):
            return cf_ip
        
        # X-Forwarded-For - take first public IP
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            for ip in x_forwarded.split(','):
                ip = ip.strip()
                if IPValidator._is_valid_ip(ip) and not IPValidator._is_private_ip(ip):
                    return ip
        
        # Fallback to REMOTE_ADDR
        remote_addr = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return remote_addr if IPValidator._is_valid_ip(remote_addr) else '127.0.0.1'
    
    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """Validate IP address format."""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """Check if IP is private/internal."""
        import ipaddress
        try:
            return ipaddress.ip_address(ip).is_private
        except ValueError:
            return False


class TokenGenerator:
    """
    Secure token generation for various purposes.
    
    Token types:
    - URL-safe tokens for email verification
    - Numeric OTP for SMS/2FA
    - API keys with prefixes
    """
    
    @staticmethod
    def generate_url_safe_token(length: int = 32) -> str:
        """Generate a URL-safe random token."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_hex_token(length: int = 32) -> str:
        """Generate a hex random token."""
        return secrets.token_hex(length // 2)
    
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate a numeric OTP."""
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    @staticmethod
    def generate_api_key(prefix: str = 'owls') -> str:
        """Generate an API key with prefix."""
        key = secrets.token_urlsafe(32)
        return f"{prefix}_{key}"
    
    @staticmethod
    def generate_backup_codes(count: int = 10, length: int = 8) -> list[str]:
        """Generate backup codes for 2FA."""
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice(string.digits) for _ in range(length))
            # Format as XXXX-XXXX for readability
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def verify_token_hash(token: str, token_hash: str) -> bool:
        """Verify a token against its hash."""
        return hmac.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(),
            token_hash
        )


class CaptchaVerifier:
    """
    Cloudflare Turnstile CAPTCHA verification.
    
    Verifies CAPTCHA tokens from frontend to prevent bot abuse.
    """
    
    VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    
    @staticmethod
    def verify(token: str, ip: Optional[str] = None) -> bool:
        """
        Verify a Turnstile CAPTCHA token.
        
        Args:
            token: The CAPTCHA response token from frontend
            ip: Optional client IP for additional verification
            
        Returns:
            True if token is valid, False otherwise
        """
        secret_key = getattr(settings, 'CLOUDFLARE_TURNSTILE_SECRET_KEY', None)
        
        if not secret_key:
            logger.warning("Turnstile secret key not configured, skipping verification")
            return True  # Skip verification in development
        
        try:
            payload = {
                'secret': secret_key,
                'response': token,
            }
            if ip:
                payload['remoteip'] = ip
            
            response = requests.post(
                CaptchaVerifier.VERIFY_URL,
                data=payload,
                timeout=10
            )
            result = response.json()
            
            if result.get('success'):
                return True
            
            logger.warning(f"Turnstile verification failed: {result.get('error-codes')}")
            return False
            
        except requests.RequestException as e:
            logger.error(f"Turnstile API error: {e}")
            return False  # Fail closed - deny on error


class PasswordPolicy:
    """
    Password strength validation.
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase
    - At least one lowercase
    - At least one number
    - At least one special character
    """
    
    MIN_LENGTH = 8
    SPECIAL_CHARS = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    @staticmethod
    def validate(password: str) -> tuple[bool, list[str]]:
        """
        Validate password against policy.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if len(password) < PasswordPolicy.MIN_LENGTH:
            errors.append(f'Mật khẩu phải có ít nhất {PasswordPolicy.MIN_LENGTH} ký tự')
        
        if not any(c.isupper() for c in password):
            errors.append('Mật khẩu phải có ít nhất 1 chữ in hoa')
        
        if not any(c.islower() for c in password):
            errors.append('Mật khẩu phải có ít nhất 1 chữ thường')
        
        if not any(c.isdigit() for c in password):
            errors.append('Mật khẩu phải có ít nhất 1 chữ số')
        
        if not any(c in PasswordPolicy.SPECIAL_CHARS for c in password):
            errors.append('Mật khẩu phải có ít nhất 1 ký tự đặc biệt')
        
        return len(errors) == 0, errors
    
    @staticmethod
    def check_common_password(password: str) -> bool:
        """Check if password is in common passwords list."""
        # Django's built-in common password validator handles this
        from django.contrib.auth.password_validation import CommonPasswordValidator
        validator = CommonPasswordValidator()
        try:
            validator.validate(password)
            return False  # Not common
        except Exception:
            return True  # Is common
