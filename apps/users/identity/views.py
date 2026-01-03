"""
Users Identity - API Views.

REST API endpoints for authentication and profile management.
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.common.core.exceptions import DomainException
from apps.common.utils.security import IPValidator
from .models import User, UserAddress
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    UserProfileUpdateSerializer, UserAddressSerializer, UserAddressCreateSerializer,
    PasswordChangeSerializer, TokenPairSerializer
)
from .services import AuthService, ProfileService, AddressService


class RegisterView(APIView):
    """User registration endpoint."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=UserRegistrationSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description='Validation error')
        },
        tags=['Authentication']
    )
    def post(self, request):
        """Register a new user account."""
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            user = AuthService.register(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                first_name=serializer.validated_data.get('first_name', ''),
                last_name=serializer.validated_data.get('last_name', '')
            )
            
            # Send verification email asynchronously
            from .tasks import send_verification_email
            send_verification_email.delay(user.id)
            
            return Response(
                UserSerializer(user).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """User login endpoint."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: TokenPairSerializer,
            401: OpenApiResponse(description='Invalid credentials')
        },
        tags=['Authentication']
    )
    def post(self, request):
        """Authenticate user and return JWT tokens."""
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = AuthService.login(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                captcha_token=serializer.validated_data.get('captcha_token'),
                ip_address=IPValidator.get_client_ip(request)
            )
            
            return Response({
                'access': result['access'],
                'refresh': result['refresh'],
                'user': UserSerializer(result['user']).data,
                'requires_2fa': result['requires_2fa']
            })
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """User logout endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: OpenApiResponse(description='Logged out successfully')},
        tags=['Authentication']
    )
    def post(self, request):
        """Logout user and blacklist refresh token."""
        refresh_token = request.data.get('refresh')
        if refresh_token:
            AuthService.logout(refresh_token)
        
        return Response({'message': 'Đăng xuất thành công'})


class RefreshTokenView(APIView):
    """Token refresh endpoint."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request={'type': 'object', 'properties': {'refresh': {'type': 'string'}}},
        responses={200: TokenPairSerializer},
        tags=['Authentication']
    )
    def post(self, request):
        """Refresh access token using refresh token."""
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tokens = AuthService.refresh_token(refresh_token)
            return Response(tokens)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_401_UNAUTHORIZED)


class VerifyEmailView(APIView):
    """Email verification endpoint."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request={'type': 'object', 'properties': {'uid': {'type': 'string'}, 'token': {'type': 'string'}}},
        responses={200: OpenApiResponse(description='Email verified successfully')},
        tags=['Authentication']
    )
    def post(self, request):
        """Verify user email with token."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str
        from django.utils import timezone
        
        uid = request.data.get('uid')
        token = request.data.get('token')
        
        if not uid or not token:
            return Response(
                {'error': 'UID và token là bắt buộc'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, User.DoesNotExist):
            return Response(
                {'error': 'Link xác thực không hợp lệ'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.is_email_verified:
            return Response({'message': 'Email đã được xác thực trước đó'})
        
        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': 'Link xác thực đã hết hạn hoặc không hợp lệ'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark as verified
        user.is_email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=['is_email_verified', 'email_verified_at'])
        
        # Send welcome email
        from .tasks import send_welcome_email
        send_welcome_email.delay(str(user.id))
        
        return Response({'message': 'Email đã được xác thực thành công'})


class ResendVerificationView(APIView):
    """Resend verification email endpoint."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request={'type': 'object', 'properties': {'email': {'type': 'string'}}},
        responses={200: OpenApiResponse(description='Verification email sent')},
        tags=['Authentication']
    )
    def post(self, request):
        """Resend verification email."""
        email = request.data.get('email')
        
        if not email:
            return Response(
                {'error': 'Email là bắt buộc'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists
            return Response({'message': 'Nếu email tồn tại, bạn sẽ nhận được email xác thực'})
        
        if user.is_email_verified:
            return Response({'message': 'Email đã được xác thực'})
        
        from .tasks import send_verification_email
        send_verification_email.delay(str(user.id))
        
        return Response({'message': 'Email xác thực đã được gửi'})


class ProfileView(APIView):
    """User profile endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: UserSerializer},
        tags=['Profile']
    )
    def get(self, request):
        """Get current user's profile."""
        return Response(UserSerializer(request.user).data)
    
    @extend_schema(
        request=UserProfileUpdateSerializer,
        responses={200: UserSerializer},
        tags=['Profile']
    )
    def patch(self, request):
        """Update current user's profile."""
        serializer = UserProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = ProfileService.update_profile(
            request.user,
            **serializer.validated_data
        )
        
        return Response(UserSerializer(user).data)


class PasswordChangeView(APIView):
    """Password change endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=PasswordChangeSerializer,
        responses={200: OpenApiResponse(description='Password changed successfully')},
        tags=['Profile']
    )
    def post(self, request):
        """Change user's password."""
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            ProfileService.change_password(
                request.user,
                serializer.validated_data['current_password'],
                serializer.validated_data['new_password']
            )
            return Response({'message': 'Mật khẩu đã được thay đổi'})
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class AddressListView(APIView):
    """User addresses list endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: UserAddressSerializer(many=True)},
        tags=['Addresses']
    )
    def get(self, request):
        """Get all addresses for current user."""
        addresses = AddressService.list_addresses(request.user)
        return Response(UserAddressSerializer(addresses, many=True).data)
    
    @extend_schema(
        request=UserAddressCreateSerializer,
        responses={201: UserAddressSerializer},
        tags=['Addresses']
    )
    def post(self, request):
        """Create a new address."""
        serializer = UserAddressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        address = AddressService.create_address(
            request.user,
            **serializer.validated_data
        )
        
        return Response(
            UserAddressSerializer(address).data,
            status=status.HTTP_201_CREATED
        )


class AddressDetailView(APIView):
    """Single address endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: UserAddressSerializer},
        tags=['Addresses']
    )
    def get(self, request, address_id: int):
        """Get a specific address."""
        try:
            address = AddressService.get_address(request.user, address_id)
            return Response(UserAddressSerializer(address).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        request=UserAddressCreateSerializer,
        responses={200: UserAddressSerializer},
        tags=['Addresses']
    )
    def patch(self, request, address_id: int):
        """Update an address."""
        serializer = UserAddressCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        try:
            address = AddressService.update_address(
                request.user,
                address_id,
                **serializer.validated_data
            )
            return Response(UserAddressSerializer(address).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        responses={204: None},
        tags=['Addresses']
    )
    def delete(self, request, address_id: int):
        """Delete an address."""
        try:
            AddressService.delete_address(request.user, address_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class AddressSetDefaultView(APIView):
    """Set default address endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: UserAddressSerializer},
        tags=['Addresses']
    )
    def post(self, request, address_id: int):
        """Set an address as default."""
        try:
            address = AddressService.set_default_address(request.user, address_id)
            return Response(UserAddressSerializer(address).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


# ==================== Session Management ====================

class SessionListView(APIView):
    """List active sessions."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Identity - Security'])
    def get(self, request):
        """Get all active sessions for current user."""
        from .models import UserSession
        from .serializers import UserSessionSerializer
        
        sessions = UserSession.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-last_activity')
        
        return Response(UserSessionSerializer(sessions, many=True).data)


class SessionTerminateView(APIView):
    """Terminate a session."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Identity - Security'])
    def post(self, request, session_id):
        """Terminate a specific session."""
        from .models import UserSession
        
        try:
            session = UserSession.objects.get(id=session_id, user=request.user)
            session.terminate()
            return Response({'message': 'Phiên đã kết thúc'})
        except UserSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)


class SessionTerminateAllView(APIView):
    """Terminate all other sessions."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Identity - Security'])
    def post(self, request):
        """Terminate all sessions except current."""
        from .models import UserSession
        
        current_session_key = request.data.get('current_session_key')
        count = UserSession.terminate_all_for_user(request.user, current_session_key)
        return Response({'terminated': count})


# ==================== Login History ====================

class LoginHistoryView(APIView):
    """View login history."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Identity - Security'])
    def get(self, request):
        """Get login history for current user."""
        from .models import LoginHistory
        from .serializers import LoginHistorySerializer
        
        history = LoginHistory.objects.filter(user=request.user).order_by('-created_at')[:50]
        return Response(LoginHistorySerializer(history, many=True).data)


# ==================== Preferences ====================

class PreferencesView(APIView):
    """User preferences endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Identity - Preferences'])
    def get(self, request):
        """Get user preferences."""
        from .models import UserPreferences
        from .serializers import UserPreferencesSerializer
        
        prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
        return Response(UserPreferencesSerializer(prefs).data)
    
    @extend_schema(tags=['Identity - Preferences'])
    def patch(self, request):
        """Update user preferences."""
        from .models import UserPreferences
        from .serializers import UserPreferencesSerializer, UserPreferencesUpdateSerializer
        
        prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
        serializer = UserPreferencesUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        for key, value in serializer.validated_data.items():
            setattr(prefs, key, value)
        prefs.save()
        
        return Response(UserPreferencesSerializer(prefs).data)


# ==================== Account Deletion ====================

class AccountDeletionView(APIView):
    """Account deletion request endpoint."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Identity - Account'])
    def get(self, request):
        """Check pending deletion request."""
        from .models import AccountDeletionRequest
        from .serializers import AccountDeletionStatusSerializer
        
        pending = AccountDeletionRequest.objects.filter(user=request.user, status='pending').first()
        if pending:
            return Response(AccountDeletionStatusSerializer(pending).data)
        return Response({'has_pending_request': False})
    
    @extend_schema(tags=['Identity - Account'])
    def post(self, request):
        """Request account deletion."""
        from .models import AccountDeletionRequest
        from .serializers import AccountDeletionRequestSerializer, AccountDeletionStatusSerializer
        
        serializer = AccountDeletionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        existing = AccountDeletionRequest.objects.filter(user=request.user, status='pending').first()
        if existing:
            return Response({'error': 'Bạn đã có yêu cầu xóa tài khoản đang chờ'}, status=status.HTTP_400_BAD_REQUEST)
        
        deletion_request = AccountDeletionRequest.objects.create(
            user=request.user,
            reason=serializer.validated_data.get('reason', '')
        )
        return Response(AccountDeletionStatusSerializer(deletion_request).data, status=status.HTTP_201_CREATED)
    
    @extend_schema(tags=['Identity - Account'])
    def delete(self, request):
        """Cancel account deletion request."""
        from .models import AccountDeletionRequest
        
        pending = AccountDeletionRequest.objects.filter(user=request.user, status='pending').first()
        if pending:
            pending.cancel()
            return Response({'message': 'Đã hủy yêu cầu xóa tài khoản'})
        return Response({'error': 'Không có yêu cầu xóa tài khoản'}, status=status.HTTP_404_NOT_FOUND)
