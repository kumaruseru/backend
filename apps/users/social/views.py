"""
Users Social - API Views.

REST API endpoints for OAuth authentication.
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from django.conf import settings
from apps.common.utils.security import IPValidator
from .services import OAuthService, OAuthError
from .models import OAuthProvider
from .serializers import (
    OAuthProviderSerializer, OAuthAuthorizeSerializer, OAuthAuthorizeResponseSerializer,
    OAuthCallbackSerializer, OAuthTokensSerializer,
    SocialConnectionSerializer, DisconnectSerializer
)


FRONTEND_URL = getattr(settings, 'FRONTEND_URL', 'https://owls.vn')
OAUTH_CALLBACK_URL = getattr(settings, 'OAUTH_CALLBACK_URL', f'{FRONTEND_URL}/auth/callback')


class AvailableProvidersView(APIView):
    """List available OAuth providers."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(responses={200: OAuthProviderSerializer(many=True)}, tags=['OAuth'])
    def get(self, request):
        """Get list of available OAuth providers."""
        providers = OAuthService.get_available_providers()
        
        provider_info = {
            'google': {'name': 'Google', 'icon_url': '/icons/google.svg', 'button_color': '#4285F4'},
            'github': {'name': 'GitHub', 'icon_url': '/icons/github.svg', 'button_color': '#24292E'},
            'facebook': {'name': 'Facebook', 'icon_url': '/icons/facebook.svg', 'button_color': '#1877F2'},
            'apple': {'name': 'Apple', 'icon_url': '/icons/apple.svg', 'button_color': '#000000'},
            'discord': {'name': 'Discord', 'icon_url': '/icons/discord.svg', 'button_color': '#5865F2'},
        }
        
        result = []
        for provider in providers:
            info = provider_info.get(provider, {'name': provider.title()})
            result.append({
                'provider': provider,
                'name': info.get('name', provider.title()),
                'icon_url': info.get('icon_url', ''),
                'button_color': info.get('button_color', '#333333')
            })
        
        return Response(result)


class OAuthAuthorizeView(APIView):
    """Initiate OAuth flow."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=OAuthAuthorizeSerializer,
        responses={200: OAuthAuthorizeResponseSerializer},
        tags=['OAuth']
    )
    def post(self, request):
        """Get OAuth authorization URL."""
        serializer = OAuthAuthorizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        provider = serializer.validated_data['provider']
        next_url = serializer.validated_data.get('next_url', '')
        
        # Determine action
        if request.user.is_authenticated:
            action = 'link'
            user = request.user
        else:
            action = 'login'
            user = None
        
        try:
            auth_url = OAuthService.get_authorization_url(
                provider=provider,
                redirect_uri=f"{OAUTH_CALLBACK_URL}/{provider}",
                user=user,
                action=action,
                next_url=next_url
            )
            return Response({'authorization_url': auth_url})
        except OAuthError as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class OAuthCallbackView(APIView):
    """Handle OAuth callback."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=OAuthCallbackSerializer,
        responses={200: OAuthTokensSerializer},
        tags=['OAuth']
    )
    def post(self, request, provider):
        """Handle OAuth callback and exchange code for tokens."""
        serializer = OAuthCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code']
        state = serializer.validated_data['state']
        
        ip_address = IPValidator.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        try:
            user, tokens = OAuthService.handle_callback(
                provider=provider,
                code=code,
                state=state,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return Response({
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'next_url': tokens.get('next_url', '/'),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'name': user.full_name
                }
            })
            
        except OAuthError as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class SocialConnectionsView(APIView):
    """Manage social connections."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(responses={200: SocialConnectionSerializer(many=True)}, tags=['Social Connections'])
    def get(self, request):
        """Get user's social connections."""
        connections = OAuthService.get_user_connections(request.user)
        return Response(SocialConnectionSerializer(connections, many=True).data)


class DisconnectView(APIView):
    """Disconnect social account."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(request=DisconnectSerializer, tags=['Social Connections'])
    def post(self, request):
        """Disconnect a social account."""
        serializer = DisconnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            OAuthService.disconnect(
                request.user,
                serializer.validated_data['provider']
            )
            return Response({'message': 'Đã ngắt kết nối thành công'})
        except OAuthError as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class ConnectView(APIView):
    """Connect/link social account to existing user."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=OAuthAuthorizeSerializer,
        responses={200: OAuthAuthorizeResponseSerializer},
        tags=['Social Connections']
    )
    def post(self, request):
        """Get OAuth URL to link a social account."""
        serializer = OAuthAuthorizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        provider = serializer.validated_data['provider']
        next_url = serializer.validated_data.get('next_url', '')
        
        try:
            auth_url = OAuthService.get_authorization_url(
                provider=provider,
                redirect_uri=f"{OAUTH_CALLBACK_URL}/{provider}",
                user=request.user,
                action='link',
                next_url=next_url
            )
            return Response({'authorization_url': auth_url})
        except OAuthError as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
