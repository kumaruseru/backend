"""Users Security - API Views."""
import json
import logging
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator

from apps.common.core.exceptions import DomainException
from apps.common.utils.security import get_client_ip
from .models import TwoFactorConfig, APIKey, TrustedDevice, LoginAttempt, SecurityAuditLog, CSPReport, IPBlacklist
from .services import TwoFactorService
from .serializers import (
    TwoFactorStatusSerializer, APIKeySerializer, APIKeyCreateSerializer,
    TrustedDeviceSerializer, LoginAttemptSerializer, SecurityAuditLogSerializer
)

logger = logging.getLogger('apps.security')


class TwoFactorStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: TwoFactorStatusSerializer}, tags=['2FA'])
    def get(self, request):
        config, _ = TwoFactorConfig.objects.get_or_create(user=request.user)
        return Response(TwoFactorStatusSerializer(config).data)


class TwoFactorSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description='QR code URI for TOTP setup')}, tags=['2FA'])
    def post(self, request):
        result = TwoFactorService.setup_totp(request.user)
        return Response(result)


class TwoFactorEnableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['2FA'])
    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'Code required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            backup_codes = TwoFactorService.enable_2fa(request.user, code)
            SecurityAuditLog.log('2fa_enabled', user=request.user, ip_address=get_client_ip(request))
            return Response({'enabled': True, 'backup_codes': backup_codes})
        except DomainException as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorDisableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['2FA'])
    def post(self, request):
        password = request.data.get('password')
        if not password:
            return Response({'error': 'Password required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            TwoFactorService.disable_2fa(request.user, password)
            SecurityAuditLog.log('2fa_disabled', user=request.user, ip_address=get_client_ip(request))
            return Response({'enabled': False})
        except DomainException as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['2FA'])
    def post(self, request):
        user_id = request.data.get('user_id')
        code = request.data.get('code')
        is_backup = request.data.get('is_backup', False)
        if not user_id or not code:
            return Response({'error': 'user_id and code required'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.users.identity.models import User
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        if is_backup:
            valid = TwoFactorService.verify_backup_code(user, code)
        else:
            valid = TwoFactorService.verify_totp(user, code)
        if valid:
            return Response({'valid': True})
        return Response({'valid': False, 'error': 'Invalid code'}, status=status.HTTP_400_BAD_REQUEST)


class BackupCodesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['2FA'])
    def get(self, request):
        count = TwoFactorService.get_remaining_backup_codes(request.user)
        return Response({'remaining': count})

    @extend_schema(tags=['2FA'])
    def post(self, request):
        password = request.data.get('password')
        if not password:
            return Response({'error': 'Password required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            backup_codes = TwoFactorService.regenerate_backup_codes(request.user, password)
            return Response({'backup_codes': backup_codes})
        except DomainException as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class APIKeyListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: APIKeySerializer(many=True)}, tags=['API Keys'])
    def get(self, request):
        keys = APIKey.objects.filter(user=request.user, is_active=True)
        return Response(APIKeySerializer(keys, many=True).data)

    @extend_schema(request=APIKeyCreateSerializer, tags=['API Keys'])
    def post(self, request):
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        api_key, plain_key = APIKey.generate(
            user=request.user,
            name=data['name'],
            permission=data.get('permission', 'read'),
            expires_days=data.get('expires_days')
        )
        if data.get('allowed_ips'):
            api_key.allowed_ips = data['allowed_ips']
        if data.get('rate_limit'):
            api_key.rate_limit = data['rate_limit']
        api_key.save()
        SecurityAuditLog.log('api_key_created', user=request.user, ip_address=get_client_ip(request), description=f'Created API key: {api_key.name}')
        return Response({
            'id': str(api_key.id),
            'name': api_key.name,
            'key': plain_key,
            'permission': api_key.permission,
            'expires_at': api_key.expires_at
        }, status=status.HTTP_201_CREATED)


class APIKeyDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['API Keys'])
    def delete(self, request, key_id):
        try:
            key = APIKey.objects.get(id=key_id, user=request.user)
            key.revoke()
            SecurityAuditLog.log('api_key_revoked', user=request.user, ip_address=get_client_ip(request), description=f'Revoked API key: {key.name}')
            return Response({'message': 'API key revoked'})
        except APIKey.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class TrustedDeviceListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: TrustedDeviceSerializer(many=True)}, tags=['Trusted Devices'])
    def get(self, request):
        devices = TrustedDevice.objects.filter(user=request.user, is_active=True)
        return Response(TrustedDeviceSerializer(devices, many=True).data)


class TrustedDeviceRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Trusted Devices'])
    def post(self, request, device_id):
        try:
            device = TrustedDevice.objects.get(id=device_id, user=request.user)
            device.revoke()
            return Response({'message': 'Device trust revoked'})
        except TrustedDevice.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class TrustedDeviceRevokeAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Trusted Devices'])
    def post(self, request):
        count = TrustedDevice.objects.filter(user=request.user, is_active=True).update(is_active=False)
        return Response({'revoked': count})


class LoginHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: LoginAttemptSerializer(many=True)}, tags=['Security'])
    def get(self, request):
        attempts = LoginAttempt.objects.filter(user=request.user).order_by('-created_at')[:50]
        return Response(LoginAttemptSerializer(attempts, many=True).data)


class SecurityAuditView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: SecurityAuditLogSerializer(many=True)}, tags=['Security'])
    def get(self, request):
        logs = SecurityAuditLog.objects.filter(user=request.user).order_by('-created_at')[:100]
        return Response(SecurityAuditLogSerializer(logs, many=True).data)


class SecurityOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Security'])
    def get(self, request):
        user = request.user
        two_fa_enabled = TwoFactorService.is_2fa_enabled(user)
        backup_codes_remaining = TwoFactorService.get_remaining_backup_codes(user)
        trusted_devices = TrustedDevice.objects.filter(user=user, is_active=True).count()
        api_keys = APIKey.objects.filter(user=user, is_active=True).count()
        last_login = LoginAttempt.objects.filter(user=user, success=True).order_by('-created_at').first()
        return Response({
            'two_factor_enabled': two_fa_enabled,
            'backup_codes_remaining': backup_codes_remaining,
            'trusted_devices_count': trusted_devices,
            'api_keys_count': api_keys,
            'last_login': {
                'at': last_login.created_at,
                'ip': last_login.ip_address,
                'location': f"{last_login.city}, {last_login.country}" if last_login.city else None
            } if last_login else None
        })


class CheckIPBlockedView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Security'])
    def get(self, request):
        ip = get_client_ip(request)
        is_blocked = IPBlacklist.is_blocked(ip)
        return Response({'ip': ip, 'blocked': is_blocked})


@method_decorator(csrf_exempt, name='dispatch')
class CSPReportView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            if isinstance(request.data, dict):
                report = request.data.get('csp-report', request.data)
            else:
                report = json.loads(request.body).get('csp-report', {})
            CSPReport.objects.create(
                document_uri=report.get('document-uri', '')[:500],
                violated_directive=report.get('violated-directive', '')[:100],
                blocked_uri=report.get('blocked-uri', ''),
                source_file=report.get('source-file', '')[:500],
                line_number=report.get('line-number'),
                column_number=report.get('column-number'),
                original_policy=report.get('original-policy', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=get_client_ip(request)
            )
        except Exception as e:
            logger.error(f"Failed to save CSP report: {e}")
        return HttpResponse(status=204)


def csp_report_view(request):
    if request.method == 'POST':
        try:
            report = json.loads(request.body).get('csp-report', {})
            CSPReport.objects.create(
                document_uri=report.get('document-uri', '')[:500],
                violated_directive=report.get('violated-directive', '')[:100],
                blocked_uri=report.get('blocked-uri', ''),
                source_file=report.get('source-file', '')[:500],
                line_number=report.get('line-number'),
                column_number=report.get('column-number'),
                original_policy=report.get('original-policy', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=get_client_ip(request)
            )
        except Exception as e:
            logger.error(f"Failed to save CSP report: {e}")
        return HttpResponse(status=204)
    return HttpResponse(status=405)


def honeypot_login_view(request):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    logger.warning(f"Honeypot triggered: {ip} - {request.path} - {user_agent}")
    SecurityAuditLog.log('suspicious', ip_address=ip, description=f'Honeypot access: {request.path}', metadata={'user_agent': user_agent}, severity='warning')
    IPBlacklist.block_ip(ip, 'brute_force', hours=24)
    return JsonResponse({'error': 'Access denied'}, status=403)
