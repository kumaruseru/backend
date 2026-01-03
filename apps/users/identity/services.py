"""
Users Identity - Application Services.

Business logic for identity management use cases.
"""
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.core.exceptions import (
    InvalidCredentials, AccountLocked, UserNotFound,
    ValidationError, AuthenticationError
)
from apps.common.utils.security import TokenGenerator, CaptchaVerifier
from .models import User, UserAddress

logger = logging.getLogger('apps.identity')


class AuthService:
    """
    Authentication use cases.
    
    Handles user registration, login, logout, and token management.
    """
    
    # Account lockout settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = 30 * 60  # 30 minutes in seconds
    
    @staticmethod
    def register(
        email: str,
        password: str,
        first_name: str = '',
        last_name: str = ''
    ) -> User:
        """
        Register a new user.
        
        Args:
            email: User's email address
            password: User's password
            first_name: Optional first name
            last_name: Optional last name
            
        Returns:
            Created User instance
            
        Raises:
            ValidationError: If email is already taken
        """
        email = email.lower().strip()
        
        # Check if email exists
        if User.objects.filter(email=email).exists():
            raise ValidationError(
                message='Email này đã được sử dụng',
                details={'field': 'email'}
            )
        
        # Create user
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            logger.info(f"User registered: {user.id}")
        
        return user
    
    @staticmethod
    def login(
        email: str,
        password: str,
        captcha_token: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authenticate user and return tokens.
        
        Args:
            email: User's email
            password: User's password
            captcha_token: Optional CAPTCHA token
            ip_address: Client IP for security logging
            
        Returns:
            Dict with tokens and user data
            
        Raises:
            InvalidCredentials: If credentials are wrong
            AccountLocked: If account is locked
        """
        email = email.lower().strip()
        
        # Verify CAPTCHA if required
        if captcha_token and not CaptchaVerifier.verify(captcha_token, ip_address):
            raise ValidationError(message='Xác thực CAPTCHA thất bại')
        
        # Find user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Log failed attempt but don't reveal if email exists
            logger.warning(f"Login failed - email not found: {email}")
            raise InvalidCredentials()
        
        # Check if account is locked
        if AuthService._is_account_locked(user):
            raise AccountLocked(
                message='Tài khoản đã bị khóa do đăng nhập sai nhiều lần. Vui lòng thử lại sau.'
            )
        
        # Verify password
        if not user.check_password(password):
            AuthService._record_failed_login(user)
            logger.warning(f"Login failed - wrong password: {user.id}")
            raise InvalidCredentials()
        
        # Check if user is active
        if not user.is_active:
            raise AuthenticationError(message='Tài khoản đã bị vô hiệu hóa')
        
        # Reset failed login counter
        AuthService._reset_failed_logins(user)
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Update last login
        user.save(update_fields=['last_login'])
        
        logger.info(f"User logged in: {user.id}")
        
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': user,
            'requires_2fa': hasattr(user, 'two_factor') and user.two_factor.is_enabled
        }
    
    @staticmethod
    def logout(refresh_token: str) -> None:
        """
        Logout user by blacklisting refresh token.
        
        Args:
            refresh_token: The refresh token to blacklist
        """
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"User logged out, token blacklisted")
        except Exception as e:
            logger.warning(f"Logout failed: {e}")
            # Don't raise - user is considered logged out anyway
    
    @staticmethod
    def refresh_token(refresh_token: str) -> Dict[str, str]:
        """
        Refresh access token.
        
        Args:
            refresh_token: Current refresh token
            
        Returns:
            Dict with new access token
        """
        try:
            token = RefreshToken(refresh_token)
            return {
                'access': str(token.access_token),
                'refresh': str(token)
            }
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
            raise AuthenticationError(message='Token không hợp lệ hoặc đã hết hạn')
    
    @staticmethod
    def _is_account_locked(user: User) -> bool:
        """Check if account is locked due to failed logins."""
        cache_key = f"account_locked:{user.id}"
        return cache.get(cache_key, False)
    
    @staticmethod
    def _record_failed_login(user: User) -> None:
        """Record a failed login attempt."""
        cache_key = f"failed_logins:{user.id}"
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, timeout=AuthService.LOCKOUT_DURATION)
        
        if attempts >= AuthService.MAX_FAILED_ATTEMPTS:
            lock_key = f"account_locked:{user.id}"
            cache.set(lock_key, True, timeout=AuthService.LOCKOUT_DURATION)
            logger.warning(f"Account locked after {attempts} failed attempts: {user.id}")
    
    @staticmethod
    def _reset_failed_logins(user: User) -> None:
        """Reset failed login counter on successful login."""
        cache.delete(f"failed_logins:{user.id}")
        cache.delete(f"account_locked:{user.id}")


class ProfileService:
    """
    Profile management use cases.
    """
    
    @staticmethod
    def get_profile(user_id: UUID) -> User:
        """Get user profile by ID."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise UserNotFound()
    
    @staticmethod
    def update_profile(user: User, **kwargs) -> User:
        """
        Update user profile.
        
        Args:
            user: User instance to update
            **kwargs: Fields to update
            
        Returns:
            Updated User instance
        """
        user.update_profile(**kwargs)
        logger.info(f"Profile updated: {user.id}")
        return user
    
    @staticmethod
    def change_password(user: User, current_password: str, new_password: str) -> None:
        """
        Change user's password.
        
        Args:
            user: User instance
            current_password: Current password for verification
            new_password: New password to set
            
        Raises:
            ValidationError: If current password is wrong
        """
        if not user.check_password(current_password):
            raise ValidationError(
                message='Mật khẩu hiện tại không đúng',
                details={'field': 'current_password'}
            )
        
        user.set_password(new_password)
        user.save(update_fields=['password', 'updated_at'])
        
        # Invalidate all sessions
        # Note: This would blacklist all refresh tokens in a real implementation
        
        logger.info(f"Password changed: {user.id}")


class AddressService:
    """
    Address management use cases.
    """
    
    @staticmethod
    def list_addresses(user: User) -> list[UserAddress]:
        """Get all addresses for a user."""
        return list(user.addresses.all())
    
    @staticmethod
    def get_address(user: User, address_id: int) -> UserAddress:
        """Get a specific address."""
        try:
            return user.addresses.get(id=address_id)
        except UserAddress.DoesNotExist:
            raise UserNotFound(message='Không tìm thấy địa chỉ')
    
    @staticmethod
    def create_address(user: User, **kwargs) -> UserAddress:
        """Create a new address for user."""
        address = UserAddress.objects.create(user=user, **kwargs)
        logger.info(f"Address created: {address.id} for user {user.id}")
        return address
    
    @staticmethod
    def update_address(user: User, address_id: int, **kwargs) -> UserAddress:
        """Update an existing address."""
        address = AddressService.get_address(user, address_id)
        
        for field, value in kwargs.items():
            if hasattr(address, field):
                setattr(address, field, value)
        
        address.save()
        logger.info(f"Address updated: {address.id}")
        return address
    
    @staticmethod
    def delete_address(user: User, address_id: int) -> None:
        """Delete an address."""
        address = AddressService.get_address(user, address_id)
        address.delete()
        logger.info(f"Address deleted: {address_id}")
    
    @staticmethod
    def set_default_address(user: User, address_id: int) -> UserAddress:
        """Set an address as default."""
        address = AddressService.get_address(user, address_id)
        address.set_as_default()
        logger.info(f"Default address set: {address_id}")
        return address
    
    @staticmethod
    def get_default_address(user: User) -> Optional[UserAddress]:
        """Get user's default address."""
        return user.addresses.filter(is_default=True).first()
