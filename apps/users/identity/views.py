"""Users Identity - API Views."""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.utils import timezone

from apps.common.core.exceptions import DomainException
from apps.common.utils.security import get_client_ip
from .models import User, UserAddress, UserSession, LoginHistory, UserPreferences
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    UserProfileUpdateSerializer, UserAddressSerializer, UserAddressCreateSerializer,
    PasswordChangeSerializer, TokenPairSerializer, UserSessionSerializer,
    LoginHistorySerializer, UserPreferencesSerializer, UserPreferencesUpdateSerializer
)
from .services import AuthService, ProfileService, AddressService


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=UserRegistrationSerializer, responses={201: UserSerializer}, tags=['Authentication'])
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = AuthService.register(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                first_name=serializer.validated_data.get('first_name', ''),
                last_name=serializer.validated_data.get('last_name', '')
            )
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=UserLoginSerializer, responses={200: TokenPairSerializer}, tags=['Authentication'])
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = AuthService.login(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                captcha_token=serializer.validated_data.get('captcha_token'),
                ip_address=get_client_ip(request)
            )
            return Response({
                'access': result['access'],
                'refresh': result['refresh'],
                'user': UserSerializer(result['user']).data
            })
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description='Logged out')}, tags=['Authentication'])
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            AuthService.logout(refresh_token)
        return Response({'message': 'Đăng xuất thành công'})


class RefreshTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: TokenPairSerializer}, tags=['Authentication'])
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tokens = AuthService.refresh_token(refresh_token)
            return Response(tokens)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_401_UNAUTHORIZED)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Authentication'])
    def post(self, request):
        uid = request.data.get('uid')
        token = request.data.get('token')
        if not uid or not token:
            return Response({'error': 'UID và token là bắt buộc'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except Exception:
            return Response({'error': 'Link xác thực không hợp lệ'}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_email_verified:
            return Response({'message': 'Email đã được xác thực trước đó'})
        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Link xác thực đã hết hạn'}, status=status.HTTP_400_BAD_REQUEST)
        user.verify_email()
        return Response({'message': 'Email đã được xác thực thành công'})


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Authentication'])
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email là bắt buộc'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Nếu email tồn tại, bạn sẽ nhận được email xác thực'})


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserSerializer}, tags=['Profile'])
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=UserProfileUpdateSerializer, responses={200: UserSerializer}, tags=['Profile'])
    def patch(self, request):
        serializer = UserProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = ProfileService.update_profile(request.user, **serializer.validated_data)
        return Response(UserSerializer(user).data)


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, tags=['Profile'])
    def post(self, request):
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
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserAddressSerializer(many=True)}, tags=['Addresses'])
    def get(self, request):
        addresses = AddressService.list_addresses(request.user)
        return Response(UserAddressSerializer(addresses, many=True).data)

    @extend_schema(request=UserAddressCreateSerializer, responses={201: UserAddressSerializer}, tags=['Addresses'])
    def post(self, request):
        serializer = UserAddressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = AddressService.create_address(request.user, **serializer.validated_data)
        return Response(UserAddressSerializer(address).data, status=status.HTTP_201_CREATED)


class AddressDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserAddressSerializer}, tags=['Addresses'])
    def get(self, request, address_id: int):
        try:
            address = AddressService.get_address(request.user, address_id)
            return Response(UserAddressSerializer(address).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)

    @extend_schema(request=UserAddressCreateSerializer, responses={200: UserAddressSerializer}, tags=['Addresses'])
    def patch(self, request, address_id: int):
        serializer = UserAddressCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            address = AddressService.update_address(request.user, address_id, **serializer.validated_data)
            return Response(UserAddressSerializer(address).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)

    @extend_schema(responses={204: None}, tags=['Addresses'])
    def delete(self, request, address_id: int):
        try:
            AddressService.delete_address(request.user, address_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class AddressSetDefaultView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserAddressSerializer}, tags=['Addresses'])
    def post(self, request, address_id: int):
        try:
            address = AddressService.set_default_address(request.user, address_id)
            return Response(UserAddressSerializer(address).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class SessionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Security'])
    def get(self, request):
        sessions = UserSession.objects.filter(user=request.user, is_active=True).order_by('-last_activity')
        return Response(UserSessionSerializer(sessions, many=True).data)


class SessionTerminateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Security'])
    def post(self, request, session_id):
        try:
            session = UserSession.objects.get(id=session_id, user=request.user)
            session.terminate()
            return Response({'message': 'Phiên đã kết thúc'})
        except UserSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)


class SessionTerminateAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Security'])
    def post(self, request):
        count = UserSession.objects.filter(user=request.user, is_active=True).update(is_active=False)
        return Response({'terminated': count})


class LoginHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Security'])
    def get(self, request):
        history = LoginHistory.objects.filter(user=request.user).order_by('-created_at')[:50]
        return Response(LoginHistorySerializer(history, many=True).data)


class PreferencesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Preferences'])
    def get(self, request):
        prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
        return Response(UserPreferencesSerializer(prefs).data)

    @extend_schema(tags=['Preferences'])
    def patch(self, request):
        prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
        serializer = UserPreferencesUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for key, value in serializer.validated_data.items():
            setattr(prefs, key, value)
        prefs.save()
        return Response(UserPreferencesSerializer(prefs).data)
