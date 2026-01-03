"""
Users Security - API Views.

REST API endpoints for security features.
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.common.core.exceptions import DomainException
from apps.common.utils.security import IPValidator
from .services import TwoFactorService, LoginAuditService
from .serializers import (
    TwoFactorStatusSerializer, TwoFactorSetupSerializer, TwoFactorEnableSerializer,
    TwoFactorVerifySerializer, TwoFactorDisableSerializer,
    BackupCodesSerializer, RegenerateBackupCodesSerializer,
    APIKeySerializer, APIKeyCreateSerializer, APIKeyCreatedSerializer,
    TrustedDeviceSerializer, LoginAttemptSerializer, SecurityAuditLogSerializer
)


# ==================== 2FA Views ====================

class TwoFactorStatusView(APIView):
    """Get 2FA status."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(responses={200: TwoFactorStatusSerializer}, tags=['2FA'])
    def get(self, request):
        """Get current 2FA configuration."""
        from .models import TwoFactorConfig
        
        config, _ = TwoFactorConfig.objects.get_or_create(user=request.user)
        return Response(TwoFactorStatusSerializer(config).data)


class TwoFactorSetupView(APIView):
    """Setup 2FA."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(responses={200: TwoFactorSetupSerializer}, tags=['2FA'])
    def post(self, request):
        """Initialize 2FA setup (get QR code)."""
        result = TwoFactorService.setup_totp(request.user)
        return Response(TwoFactorSetupSerializer(result).data)


class TwoFactorEnableView(APIView):
    """Enable 2FA."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(request=TwoFactorEnableSerializer, tags=['2FA'])
    def post(self, request):
        """Enable 2FA by verifying first code."""
        serializer = TwoFactorEnableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            backup_codes = TwoFactorService.enable_2fa(
                request.user,
                serializer.validated_data['code']
            )
            return Response({
                'message': '2FA đã được kích hoạt',
                'backup_codes': backup_codes
            })
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class TwoFactorDisableView(APIView):
    """Disable 2FA."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(request=TwoFactorDisableSerializer, tags=['2FA'])
    def post(self, request):
        """Disable 2FA."""
        serializer = TwoFactorDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            TwoFactorService.disable_2fa(
                request.user,
                serializer.validated_data['password']
            )
            return Response({'message': '2FA đã được tắt'})
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class TwoFactorVerifyView(APIView):
    """Verify 2FA code (during login)."""
    permission_classes = [permissions.AllowAny]  # Called during login flow
    
    @extend_schema(request=TwoFactorVerifySerializer, tags=['2FA'])
    def post(self, request):
        """Verify 2FA code."""
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # This would be called after initial auth, using a temp token
        # Implementation depends on auth flow
        return Response({'message': 'Verification endpoint'})


class BackupCodesView(APIView):
    """View backup codes."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['2FA'])
    def get(self, request):
        """Get remaining backup codes count."""
        count = TwoFactorService.get_remaining_backup_codes(request.user)
        return Response({'remaining': count})
    
    @extend_schema(request=RegenerateBackupCodesSerializer, tags=['2FA'])
    def post(self, request):
        """Regenerate backup codes."""
        serializer = RegenerateBackupCodesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            codes = TwoFactorService.regenerate_backup_codes(
                request.user,
                serializer.validated_data['password']
            )
            return Response({'backup_codes': codes})
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


# ==================== API Key Views ====================

class APIKeyListView(APIView):
    """List and create API keys."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(responses={200: APIKeySerializer(many=True)}, tags=['API Keys'])
    def get(self, request):
        """Get all API keys."""
        from .models import APIKey
        keys = APIKey.objects.filter(user=request.user, is_active=True)
        return Response(APIKeySerializer(keys, many=True).data)
    
    @extend_schema(request=APIKeyCreateSerializer, responses={201: APIKeyCreatedSerializer}, tags=['API Keys'])
    def post(self, request):
        """Create a new API key."""
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from .models import APIKey
        data = serializer.validated_data
        
        api_key, plain_key = APIKey.generate(
            user=request.user,
            name=data['name'],
            permission=data['permission'],
            expires_days=data.get('expires_days')
        )
        
        # Update with optional fields
        if data.get('allowed_ips'):
            api_key.allowed_ips = data['allowed_ips']
        if data.get('rate_limit'):
            api_key.rate_limit = data['rate_limit']
        api_key.save()
        
        return Response({
            'id': str(api_key.id),
            'name': api_key.name,
            'key': plain_key,  # Only shown once!
            'permission': api_key.permission,
            'expires_at': api_key.expires_at
        }, status=status.HTTP_201_CREATED)


class APIKeyDetailView(APIView):
    """Manage single API key."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['API Keys'])
    def delete(self, request, key_id):
        """Revoke an API key."""
        from .models import APIKey
        try:
            key = APIKey.objects.get(id=key_id, user=request.user)
            key.revoke()
            return Response({'message': 'API key đã được thu hồi'})
        except APIKey.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


# ==================== Trusted Device Views ====================

class TrustedDeviceListView(APIView):
    """List trusted devices."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(responses={200: TrustedDeviceSerializer(many=True)}, tags=['Trusted Devices'])
    def get(self, request):
        """Get trusted devices."""
        from .models import TrustedDevice
        devices = TrustedDevice.objects.filter(user=request.user, is_active=True)
        return Response(TrustedDeviceSerializer(devices, many=True).data)


class TrustedDeviceRevokeView(APIView):
    """Revoke trusted device."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Trusted Devices'])
    def post(self, request, device_id):
        """Revoke trust for a device."""
        from .models import TrustedDevice
        try:
            device = TrustedDevice.objects.get(id=device_id, user=request.user)
            device.revoke()
            return Response({'message': 'Đã thu hồi trust'})
        except TrustedDevice.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class TrustedDeviceRevokeAllView(APIView):
    """Revoke all trusted devices."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Trusted Devices'])
    def post(self, request):
        """Revoke all trusted devices."""
        from .models import TrustedDevice
        count = TrustedDevice.objects.filter(
            user=request.user, is_active=True
        ).update(is_active=False)
        return Response({'revoked': count})


# ==================== Login History Views ====================

class LoginHistoryView(APIView):
    """View login history."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(responses={200: LoginAttemptSerializer(many=True)}, tags=['Security'])
    def get(self, request):
        """Get login history."""
        attempts = LoginAuditService.get_recent_attempts(
            request.user.email,
            hours=int(request.query_params.get('hours', 168))  # 7 days default
        )
        return Response(LoginAttemptSerializer(attempts, many=True).data)


# ==================== Security Audit Views ====================

class SecurityAuditView(APIView):
    """View security audit log."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(responses={200: SecurityAuditLogSerializer(many=True)}, tags=['Security'])
    def get(self, request):
        """Get security audit log."""
        from .models import SecurityAuditLog
        
        logs = SecurityAuditLog.objects.filter(
            user=request.user
        ).order_by('-created_at')[:100]
        
        return Response(SecurityAuditLogSerializer(logs, many=True).data)


# ==================== Security Overview ====================

class SecurityOverviewView(APIView):
    """Security overview dashboard."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Security'])
    def get(self, request):
        """Get security overview."""
        from .models import TwoFactorConfig, TrustedDevice, APIKey, LoginAttempt
        from django.utils import timezone
        from datetime import timedelta
        
        user = request.user
        last_30_days = timezone.now() - timedelta(days=30)
        
        # 2FA status
        try:
            two_fa = user.two_factor
            two_fa_enabled = two_fa.is_enabled
        except TwoFactorConfig.DoesNotExist:
            two_fa_enabled = False
        
        # Counts
        trusted_devices = TrustedDevice.objects.filter(user=user, is_active=True).count()
        api_keys = APIKey.objects.filter(user=user, is_active=True).count()
        
        # Recent login stats
        recent_logins = LoginAttempt.objects.filter(
            user=user,
            created_at__gte=last_30_days
        )
        successful_logins = recent_logins.filter(success=True).count()
        failed_logins = recent_logins.filter(success=False).count()
        
        # Last login
        last_login = LoginAttempt.objects.filter(
            user=user, success=True
        ).order_by('-created_at').first()
        
        return Response({
            'two_factor_enabled': two_fa_enabled,
            'trusted_devices_count': trusted_devices,
            'api_keys_count': api_keys,
            'recent_logins': {
                'successful': successful_logins,
                'failed': failed_logins
            },
            'last_login': {
                'at': last_login.created_at if last_login else None,
                'ip': last_login.ip_address if last_login else None,
                'location': f"{last_login.city}, {last_login.country}" if last_login and last_login.city else None
            } if last_login else None
        })
