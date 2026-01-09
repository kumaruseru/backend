"""Users Identity - Services."""
from typing import Dict, Any, Optional
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from apps.common.core.exceptions import InvalidCredentials, AuthenticationError, NotFoundError
from apps.common.utils.security import verify_turnstile, get_client_ip
from .models import User, UserAddress, LoginHistory


class AuthService:
    """Authentication domain service."""

    @staticmethod
    def register(email: str, password: str, first_name: str = '', last_name: str = '') -> User:
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        return user

    @staticmethod
    def login(email: str, password: str, captcha_token: str = None, ip_address: str = None) -> Dict[str, Any]:
        user = authenticate(email=email, password=password)
        if not user:
            LoginHistory.objects.create(
                email=email,
                status=LoginHistory.Status.FAILED,
                fail_reason='invalid_password',
                ip_address=ip_address
            )
            raise InvalidCredentials()

        if not user.is_active:
            raise AuthenticationError(message='Tài khoản đã bị vô hiệu hóa', code='ACCOUNT_DISABLED')

        refresh = RefreshToken.for_user(user)
        LoginHistory.objects.create(
            user=user,
            email=email,
            status=LoginHistory.Status.SUCCESS,
            ip_address=ip_address
        )

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': user,
            'requires_2fa': False
        }

    @staticmethod
    def logout(refresh_token: str) -> None:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass

    @staticmethod
    def refresh_token(refresh_token: str) -> Dict[str, str]:
        try:
            token = RefreshToken(refresh_token)
            return {
                'access': str(token.access_token),
                'refresh': str(token)
            }
        except Exception:
            raise AuthenticationError(message='Token không hợp lệ hoặc đã hết hạn', code='INVALID_TOKEN')


class ProfileService:
    """Profile management domain service."""

    @staticmethod
    def update_profile(user: User, **kwargs) -> User:
        allowed_fields = ['first_name', 'last_name', 'phone', 'address', 'ward', 'district', 'city',
                          'province_id', 'district_id', 'ward_code']
        update_fields = ['updated_at']
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(user, field, value)
                update_fields.append(field)
        if len(update_fields) > 1:
            user.save(update_fields=update_fields)
        return user

    @staticmethod
    def change_password(user: User, current_password: str, new_password: str) -> None:
        if not user.check_password(current_password):
            raise InvalidCredentials(message='Mật khẩu hiện tại không đúng')
        user.set_password(new_password)
        user.save(update_fields=['password'])


class AddressService:
    """Address management domain service."""

    @staticmethod
    def list_addresses(user: User):
        return UserAddress.objects.filter(user=user).order_by('-is_default', '-created_at')

    @staticmethod
    def get_address(user: User, address_id: int) -> UserAddress:
        try:
            return UserAddress.objects.get(id=address_id, user=user)
        except UserAddress.DoesNotExist:
            raise NotFoundError(message='Địa chỉ không tồn tại', code='ADDRESS_NOT_FOUND')

    @staticmethod
    def create_address(user: User, **kwargs) -> UserAddress:
        return UserAddress.objects.create(user=user, **kwargs)

    @staticmethod
    def update_address(user: User, address_id: int, **kwargs) -> UserAddress:
        address = AddressService.get_address(user, address_id)
        for field, value in kwargs.items():
            setattr(address, field, value)
        address.save()
        return address

    @staticmethod
    def delete_address(user: User, address_id: int) -> None:
        address = AddressService.get_address(user, address_id)
        address.delete()

    @staticmethod
    def set_default_address(user: User, address_id: int) -> UserAddress:
        address = AddressService.get_address(user, address_id)
        address.is_default = True
        address.save()
        return address
