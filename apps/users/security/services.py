"""
Users Security - 2FA Services.

Business logic for two-factor authentication.
"""
import pyotp
import logging
from typing import Optional, Tuple, List
from django.utils import timezone
from django.conf import settings

from apps.common.core.exceptions import (
    InvalidTwoFactorCode, ValidationError, AuthenticationError
)
from apps.common.utils.security import TokenGenerator
from .models import TwoFactorConfig, LoginAttempt

logger = logging.getLogger('apps.security')


class TwoFactorService:
    """
    Two-Factor Authentication management.
    
    Supports TOTP (Time-based One-Time Password) and Email OTP.
    """
    
    ISSUER_NAME = 'OWLS Store'
    
    @staticmethod
    def setup_totp(user) -> dict:
        """
        Initialize TOTP setup for a user.
        
        Returns:
            Dict with secret, QR code URI, and backup codes
        """
        # Generate new secret
        secret = pyotp.random_base32()
        
        # Get or create 2FA config
        config, created = TwoFactorConfig.objects.get_or_create(
            user=user,
            defaults={'secret': secret, 'method': 'totp'}
        )
        
        if not created:
            # Update existing config with new secret
            config.secret = secret
            config.is_enabled = False  # Require re-verification
            config.save(update_fields=['secret', 'is_enabled', 'updated_at'])
        
        # Generate provisioning URI for QR code
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=TwoFactorService.ISSUER_NAME
        )
        
        logger.info(f"2FA TOTP setup initiated for user {user.id}")
        
        return {
            'secret': secret,
            'qr_uri': uri,
            'method': 'totp'
        }
    
    @staticmethod
    def verify_totp(user, code: str) -> bool:
        """
        Verify a TOTP code.
        
        Args:
            user: User instance
            code: 6-digit TOTP code
            
        Returns:
            True if code is valid
        """
        try:
            config = user.two_factor
        except TwoFactorConfig.DoesNotExist:
            return False
        
        if not config.secret:
            return False
        
        totp = pyotp.TOTP(config.secret)
        
        # Allow 1 window tolerance (30 seconds before/after)
        is_valid = totp.verify(code, valid_window=1)
        
        if is_valid:
            config.last_used_at = timezone.now()
            config.save(update_fields=['last_used_at', 'updated_at'])
        
        return is_valid
    
    @staticmethod
    def enable_2fa(user, code: str) -> List[str]:
        """
        Enable 2FA after verifying initial code.
        
        Args:
            user: User instance
            code: Verification code to confirm setup
            
        Returns:
            List of backup codes
            
        Raises:
            InvalidTwoFactorCode: If code is invalid
        """
        if not TwoFactorService.verify_totp(user, code):
            raise InvalidTwoFactorCode()
        
        config = user.two_factor
        
        # Generate backup codes
        backup_codes = TokenGenerator.generate_backup_codes(count=10)
        
        # Hash backup codes for storage
        hashed_codes = [
            TokenGenerator.hash_token(code.replace('-', ''))
            for code in backup_codes
        ]
        
        config.is_enabled = True
        config.backup_codes = hashed_codes
        config.save(update_fields=['is_enabled', 'backup_codes', 'updated_at'])
        
        logger.info(f"2FA enabled for user {user.id}")
        
        return backup_codes
    
    @staticmethod
    def disable_2fa(user, password: str) -> None:
        """
        Disable 2FA after password verification.
        
        Args:
            user: User instance
            password: User's current password
            
        Raises:
            ValidationError: If password is wrong
        """
        if not user.check_password(password):
            raise ValidationError(
                message='Mật khẩu không đúng',
                details={'field': 'password'}
            )
        
        try:
            config = user.two_factor
            config.is_enabled = False
            config.secret = ''
            config.backup_codes = []
            config.save(update_fields=['is_enabled', 'secret', 'backup_codes', 'updated_at'])
            
            logger.info(f"2FA disabled for user {user.id}")
        except TwoFactorConfig.DoesNotExist:
            pass  # Already disabled
    
    @staticmethod
    def verify_backup_code(user, code: str) -> bool:
        """
        Verify and consume a backup code.
        
        Args:
            user: User instance
            code: Backup code (with or without dash)
            
        Returns:
            True if code is valid and consumed
        """
        try:
            config = user.two_factor
        except TwoFactorConfig.DoesNotExist:
            return False
        
        # Normalize code (remove dashes)
        code = code.replace('-', '')
        code_hash = TokenGenerator.hash_token(code)
        
        if code_hash in config.backup_codes:
            # Remove used code
            config.backup_codes.remove(code_hash)
            config.last_used_at = timezone.now()
            config.save(update_fields=['backup_codes', 'last_used_at', 'updated_at'])
            
            logger.info(f"Backup code used for user {user.id}")
            return True
        
        return False
    
    @staticmethod
    def regenerate_backup_codes(user, password: str) -> List[str]:
        """
        Regenerate backup codes after password verification.
        
        Args:
            user: User instance
            password: User's password
            
        Returns:
            New list of backup codes
        """
        if not user.check_password(password):
            raise ValidationError(
                message='Mật khẩu không đúng',
                details={'field': 'password'}
            )
        
        try:
            config = user.two_factor
        except TwoFactorConfig.DoesNotExist:
            raise ValidationError(message='2FA chưa được thiết lập')
        
        if not config.is_enabled:
            raise ValidationError(message='2FA chưa được kích hoạt')
        
        # Generate new backup codes
        backup_codes = TokenGenerator.generate_backup_codes(count=10)
        hashed_codes = [
            TokenGenerator.hash_token(code.replace('-', ''))
            for code in backup_codes
        ]
        
        config.backup_codes = hashed_codes
        config.save(update_fields=['backup_codes', 'updated_at'])
        
        logger.info(f"Backup codes regenerated for user {user.id}")
        
        return backup_codes
    
    @staticmethod
    def is_2fa_enabled(user) -> bool:
        """Check if user has 2FA enabled."""
        try:
            return user.two_factor.is_enabled
        except TwoFactorConfig.DoesNotExist:
            return False
    
    @staticmethod
    def get_remaining_backup_codes(user) -> int:
        """Get count of remaining backup codes."""
        try:
            return len(user.two_factor.backup_codes)
        except TwoFactorConfig.DoesNotExist:
            return 0


class LoginAuditService:
    """
    Login attempt auditing and analysis.
    """
    
    @staticmethod
    def record_attempt(
        email: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        user=None,
        failure_reason: str = ''
    ) -> LoginAttempt:
        """Record a login attempt."""
        attempt = LoginAttempt.objects.create(
            user=user,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason
        )
        
        if not success:
            logger.warning(f"Failed login attempt for {email} from {ip_address}: {failure_reason}")
        
        return attempt
    
    @staticmethod
    def get_recent_attempts(email: str, hours: int = 24) -> list:
        """Get recent login attempts for an email."""
        since = timezone.now() - timezone.timedelta(hours=hours)
        return list(LoginAttempt.objects.filter(
            email=email,
            created_at__gte=since
        ).order_by('-created_at'))
    
    @staticmethod
    def get_failed_attempts_count(email: str, minutes: int = 30) -> int:
        """Get count of failed attempts in recent period."""
        since = timezone.now() - timezone.timedelta(minutes=minutes)
        return LoginAttempt.objects.filter(
            email=email,
            success=False,
            created_at__gte=since
        ).count()
