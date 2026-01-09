"""Common Utils - Security Utilities."""
import logging
import hashlib
import secrets
import httpx
from typing import Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('apps.security')


def verify_turnstile(token: str, ip_address: Optional[str] = None) -> dict:
    """Verify Cloudflare Turnstile token."""
    if not token:
        return {'success': False, 'error': 'missing-input-response'}
    try:
        response = httpx.post(
            settings.CLOUDFLARE_TURNSTILE_VERIFY_URL,
            data={
                'secret': settings.CLOUDFLARE_TURNSTILE_SECRET_KEY,
                'response': token,
                'remoteip': ip_address,
            },
            timeout=10.0
        )
        result = response.json()
        return {
            'success': result.get('success', False),
            'challenge_ts': result.get('challenge_ts'),
            'hostname': result.get('hostname'),
            'error_codes': result.get('error-codes', []),
        }
    except Exception as e:
        logger.error(f"Turnstile verification failed: {e}")
        return {'success': False, 'error': str(e)}


def block_ip(ip: str, duration_seconds: int = 3600, reason: str = ''):
    """Block an IP address."""
    cache.set(f'blocked_ip:{ip}', True, timeout=duration_seconds)
    logger.warning(f"IP blocked: {ip}, duration: {duration_seconds}s, reason: {reason}")


def unblock_ip(ip: str):
    """Unblock an IP address."""
    cache.delete(f'blocked_ip:{ip}')
    logger.info(f"IP unblocked: {ip}")


def is_ip_blocked(ip: str) -> bool:
    """Check if an IP is blocked."""
    return cache.get(f'blocked_ip:{ip}', False)


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP."""
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


class TokenGenerator:
    @staticmethod
    def generate_backup_codes(count: int = 10) -> list:
        """Generate backup codes for 2FA recovery."""
        return [f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}" for _ in range(count)]

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def get_client_ip(request) -> str:
    """Extract client IP from request, handling proxies."""
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def mask_email(email: str) -> str:
    """Mask email for display (e.g., t***@example.com)."""
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '***'
    else:
        masked_local = local[0] + '***' + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    """Mask phone for display (e.g., ***1234)."""
    if not phone or len(phone) < 4:
        return phone
    return '***' + phone[-4:]
