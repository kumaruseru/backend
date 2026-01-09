"""Users Security - Services."""
import pyotp
import logging
from typing import List
from django.utils import timezone
from apps.common.core.exceptions import InvalidTwoFactorCode, ValidationError
from apps.common.utils.security import TokenGenerator
from .models import TwoFactorConfig, LoginAttempt

logger = logging.getLogger('apps.security')


class TwoFactorService:
    ISSUER_NAME = 'OWLS Store'

    @staticmethod
    def setup_totp(user) -> dict:
        secret = pyotp.random_base32()
        config, created = TwoFactorConfig.objects.get_or_create(
            user=user,
            defaults={'secret': secret, 'method': 'totp'}
        )
        if not created:
            config.secret = secret
            config.is_enabled = False
            config.save(update_fields=['secret', 'is_enabled', 'updated_at'])

        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user.email, issuer_name=TwoFactorService.ISSUER_NAME)
        logger.info(f"2FA TOTP setup initiated for user {user.id}")
        return {'secret': secret, 'qr_uri': uri, 'method': 'totp'}

    @staticmethod
    def verify_totp(user, code: str) -> bool:
        try:
            config = user.two_factor
        except TwoFactorConfig.DoesNotExist:
            return False
        if not config.secret:
            return False
        totp = pyotp.TOTP(config.secret)
        is_valid = totp.verify(code, valid_window=1)
        if is_valid:
            config.last_used_at = timezone.now()
            config.save(update_fields=['last_used_at', 'updated_at'])
        return is_valid

    @staticmethod
    def enable_2fa(user, code: str) -> List[str]:
        if not TwoFactorService.verify_totp(user, code):
            raise InvalidTwoFactorCode()
        config = user.two_factor
        backup_codes = TokenGenerator.generate_backup_codes(count=10)
        hashed_codes = [TokenGenerator.hash_token(c.replace('-', '')) for c in backup_codes]
        config.is_enabled = True
        config.backup_codes = hashed_codes
        config.backup_codes_count = len(hashed_codes)
        config.setup_completed_at = timezone.now()
        config.save(update_fields=['is_enabled', 'backup_codes', 'backup_codes_count', 'setup_completed_at', 'updated_at'])
        logger.info(f"2FA enabled for user {user.id}")
        return backup_codes

    @staticmethod
    def disable_2fa(user, password: str) -> None:
        if not user.check_password(password):
            raise ValidationError(message='Password incorrect', details={'field': 'password'})
        try:
            config = user.two_factor
            config.is_enabled = False
            config.secret = ''
            config.backup_codes = []
            config.backup_codes_count = 0
            config.save(update_fields=['is_enabled', 'secret', 'backup_codes', 'backup_codes_count', 'updated_at'])
            logger.info(f"2FA disabled for user {user.id}")
        except TwoFactorConfig.DoesNotExist:
            pass

    @staticmethod
    def verify_backup_code(user, code: str) -> bool:
        try:
            config = user.two_factor
        except TwoFactorConfig.DoesNotExist:
            return False
        code = code.replace('-', '')
        code_hash = TokenGenerator.hash_token(code)
        if code_hash in config.backup_codes:
            config.backup_codes.remove(code_hash)
            config.backup_codes_count = len(config.backup_codes)
            config.last_used_at = timezone.now()
            config.save(update_fields=['backup_codes', 'backup_codes_count', 'last_used_at', 'updated_at'])
            logger.info(f"Backup code used for user {user.id}")
            return True
        return False

    @staticmethod
    def regenerate_backup_codes(user, password: str) -> List[str]:
        if not user.check_password(password):
            raise ValidationError(message='Password incorrect', details={'field': 'password'})
        try:
            config = user.two_factor
        except TwoFactorConfig.DoesNotExist:
            raise ValidationError(message='2FA not configured')
        if not config.is_enabled:
            raise ValidationError(message='2FA not enabled')
        backup_codes = TokenGenerator.generate_backup_codes(count=10)
        hashed_codes = [TokenGenerator.hash_token(c.replace('-', '')) for c in backup_codes]
        config.backup_codes = hashed_codes
        config.backup_codes_count = len(hashed_codes)
        config.save(update_fields=['backup_codes', 'backup_codes_count', 'updated_at'])
        logger.info(f"Backup codes regenerated for user {user.id}")
        return backup_codes

    @staticmethod
    def is_2fa_enabled(user) -> bool:
        try:
            return user.two_factor.is_enabled
        except TwoFactorConfig.DoesNotExist:
            return False

    @staticmethod
    def get_remaining_backup_codes(user) -> int:
        try:
            return len(user.two_factor.backup_codes)
        except TwoFactorConfig.DoesNotExist:
            return 0


class LoginAuditService:
    @staticmethod
    def record_attempt(email: str, ip_address: str, user_agent: str, success: bool, user=None, failure_reason: str = '') -> LoginAttempt:
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
        since = timezone.now() - timezone.timedelta(hours=hours)
        return list(LoginAttempt.objects.filter(email=email, created_at__gte=since).order_by('-created_at'))

    @staticmethod
    def get_failed_attempts_count(email: str, minutes: int = 30) -> int:
        since = timezone.now() - timezone.timedelta(minutes=minutes)
        return LoginAttempt.objects.filter(email=email, success=False, created_at__gte=since).count()
