"""
Users Social - OAuth Services.

Production-ready OAuth authentication flow.
"""
import logging
import requests
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.core.exceptions import DomainException
from apps.users.identity.models import User
from .models import (
    ProviderConfig, SocialConnection, OAuthState, SocialLoginLog, OAuthProvider
)

logger = logging.getLogger('apps.social')

FRONTEND_URL = getattr(settings, 'FRONTEND_URL', 'https://owls.vn')


class OAuthError(DomainException):
    """OAuth-specific error."""
    
    def __init__(self, message: str, error_code: str = 'oauth_error'):
        super().__init__(message, error_code)


class OAuthService:
    """
    OAuth authentication service.
    
    Handles OAuth flow for all supported providers.
    """
    
    @staticmethod
    def get_authorization_url(
        provider: str,
        redirect_uri: str,
        user=None,
        action: str = 'login',
        next_url: str = ''
    ) -> str:
        """
        Get OAuth authorization URL for a provider.
        
        Args:
            provider: OAuth provider (google, github, etc.)
            redirect_uri: Callback URI after auth
            user: Optional user for account linking
            action: login, register, or link
            next_url: URL to redirect after complete
            
        Returns:
            Authorization URL
        """
        config = ProviderConfig.get_config(provider)
        if not config:
            raise OAuthError(f'Provider {provider} không được hỗ trợ', 'invalid_provider')
        
        # Create state token
        state = OAuthState.create_state(
            provider=provider,
            redirect_uri=redirect_uri,
            user=user,
            action=action,
            next_url=next_url
        )
        
        # Build authorization URL
        params = {
            'client_id': config.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(config.scopes),
            'state': state,
        }
        
        # Provider-specific params
        if provider == 'google':
            params['access_type'] = 'offline'
            params['prompt'] = 'consent'
        elif provider == 'github':
            params['allow_signup'] = 'true'
        
        return f"{config.authorize_url}?{urlencode(params)}"
    
    @staticmethod
    def handle_callback(
        provider: str,
        code: str,
        state: str,
        ip_address: str = None,
        user_agent: str = ''
    ) -> Tuple[User, Dict[str, str]]:
        """
        Handle OAuth callback.
        
        Args:
            provider: OAuth provider
            code: Authorization code
            state: State token for CSRF
            ip_address: Client IP
            user_agent: Client user agent
            
        Returns:
            Tuple of (User, tokens dict with access_token and refresh_token)
        """
        # Verify state
        oauth_state = OAuthState.verify_state(state)
        if not oauth_state:
            raise OAuthError('Invalid or expired state', 'invalid_state')
        
        if oauth_state.provider != provider:
            raise OAuthError('Provider mismatch', 'provider_mismatch')
        
        try:
            # Exchange code for tokens
            config = ProviderConfig.get_config(provider)
            tokens = OAuthService._exchange_code(config, code, oauth_state.redirect_uri)
            
            # Get user info from provider
            user_info = OAuthService._get_user_info(config, tokens['access_token'], provider)
            
            # Process based on action
            action = oauth_state.action
            user = oauth_state.user
            
            if action == 'link':
                # Link to existing account
                if not user:
                    raise OAuthError('User required for linking', 'user_required')
                result_user = OAuthService._link_account(user, provider, user_info, tokens)
                
            elif action == 'login':
                # Login or register
                result_user = OAuthService._login_or_register(provider, user_info, tokens)
                
            else:  # register
                result_user = OAuthService._register_new_user(provider, user_info, tokens)
            
            # Log success
            SocialLoginLog.objects.create(
                provider=provider,
                user=result_user,
                provider_user_id=user_info.get('id', ''),
                provider_email=user_info.get('email', ''),
                status='success',
                action=action,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(result_user)
            jwt_tokens = {
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'next_url': oauth_state.next_url or '/'
            }
            
            # Consume state
            oauth_state.consume()
            
            logger.info(f"OAuth {action} success: {result_user.email} via {provider}")
            
            return result_user, jwt_tokens
            
        except OAuthError:
            raise
        except Exception as e:
            logger.exception(f"OAuth callback error: {e}")
            
            # Log failure
            SocialLoginLog.objects.create(
                provider=provider,
                status='error',
                action=oauth_state.action,
                error_message=str(e),
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            raise OAuthError(f'OAuth error: {str(e)}', 'oauth_error')
    
    @staticmethod
    def _exchange_code(config: ProviderConfig, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        data = {
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        headers = {'Accept': 'application/json'}
        
        response = requests.post(
            config.token_url,
            data=data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.text}")
            raise OAuthError('Token exchange failed', 'token_error')
        
        return response.json()
    
    @staticmethod
    def _get_user_info(config: ProviderConfig, access_token: str, provider: str) -> Dict[str, Any]:
        """Get user info from provider."""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        response = requests.get(
            config.userinfo_url,
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            raise OAuthError('Failed to get user info', 'userinfo_error')
        
        data = response.json()
        
        # Normalize user info
        return OAuthService._normalize_user_info(provider, data)
    
    @staticmethod
    def _normalize_user_info(provider: str, data: Dict) -> Dict[str, Any]:
        """Normalize user info from different providers."""
        if provider == 'google':
            return {
                'id': data.get('id'),
                'email': data.get('email'),
                'name': data.get('name'),
                'first_name': data.get('given_name'),
                'last_name': data.get('family_name'),
                'avatar': data.get('picture'),
                'verified': data.get('verified_email', False)
            }
        
        elif provider == 'github':
            return {
                'id': str(data.get('id')),
                'email': data.get('email'),
                'username': data.get('login'),
                'name': data.get('name') or data.get('login'),
                'avatar': data.get('avatar_url'),
                'verified': True  # GitHub emails are verified
            }
        
        elif provider == 'facebook':
            return {
                'id': data.get('id'),
                'email': data.get('email'),
                'name': data.get('name'),
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
                'avatar': data.get('picture', {}).get('data', {}).get('url'),
                'verified': True
            }
        
        else:
            return {
                'id': data.get('id') or data.get('sub'),
                'email': data.get('email'),
                'name': data.get('name'),
                'avatar': data.get('picture') or data.get('avatar_url'),
                'verified': False
            }
    
    @staticmethod
    def _login_or_register(provider: str, user_info: Dict, tokens: Dict) -> User:
        """Login or register user via OAuth."""
        provider_user_id = user_info['id']
        email = user_info.get('email')
        
        # Check for existing connection
        connection = SocialConnection.objects.filter(
            provider=provider,
            provider_user_id=provider_user_id
        ).first()
        
        if connection:
            # Existing connection - login
            user = connection.user
            connection.update_tokens(
                tokens.get('access_token'),
                tokens.get('refresh_token'),
                tokens.get('expires_in')
            )
            connection.record_login()
            return user
        
        # Check if email exists
        if email:
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                # Link to existing account
                return OAuthService._link_account(existing_user, provider, user_info, tokens)
        
        # Register new user
        return OAuthService._register_new_user(provider, user_info, tokens)
    
    @staticmethod
    def _register_new_user(provider: str, user_info: Dict, tokens: Dict) -> User:
        """Register a new user from OAuth."""
        email = user_info.get('email')
        
        if not email:
            raise OAuthError('Email required for registration', 'email_required')
        
        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=user_info.get('first_name', user_info.get('name', '').split()[0] if user_info.get('name') else ''),
            last_name=user_info.get('last_name', ''),
            is_email_verified=user_info.get('verified', False)
        )
        
        if user_info.get('verified'):
            user.email_verified_at = timezone.now()
            user.save(update_fields=['email_verified_at'])
        
        # Create connection
        SocialConnection.objects.create(
            user=user,
            provider=provider,
            provider_user_id=user_info['id'],
            provider_username=user_info.get('username', ''),
            provider_email=email,
            provider_name=user_info.get('name', ''),
            provider_avatar=user_info.get('avatar', ''),
            access_token=tokens.get('access_token', ''),
            refresh_token=tokens.get('refresh_token', ''),
            token_expires_at=timezone.now() + timezone.timedelta(seconds=tokens.get('expires_in', 3600)) if tokens.get('expires_in') else None,
            is_primary=True
        )
        
        logger.info(f"New user registered via {provider}: {email}")
        return user
    
    @staticmethod
    def _link_account(user: User, provider: str, user_info: Dict, tokens: Dict) -> User:
        """Link OAuth account to existing user."""
        # Check if already linked
        existing = SocialConnection.objects.filter(
            user=user,
            provider=provider
        ).first()
        
        if existing:
            # Update existing connection
            existing.provider_user_id = user_info['id']
            existing.update_tokens(
                tokens.get('access_token'),
                tokens.get('refresh_token'),
                tokens.get('expires_in')
            )
            return user
        
        # Check if this provider account is linked to another user
        other_connection = SocialConnection.objects.filter(
            provider=provider,
            provider_user_id=user_info['id']
        ).first()
        
        if other_connection:
            raise OAuthError(
                f'Tài khoản {provider} này đã được liên kết với người dùng khác',
                'already_linked'
            )
        
        # Create new connection
        SocialConnection.objects.create(
            user=user,
            provider=provider,
            provider_user_id=user_info['id'],
            provider_username=user_info.get('username', ''),
            provider_email=user_info.get('email', ''),
            provider_name=user_info.get('name', ''),
            provider_avatar=user_info.get('avatar', ''),
            access_token=tokens.get('access_token', ''),
            refresh_token=tokens.get('refresh_token', ''),
            token_expires_at=timezone.now() + timezone.timedelta(seconds=tokens.get('expires_in', 3600)) if tokens.get('expires_in') else None
        )
        
        logger.info(f"Linked {provider} to user: {user.email}")
        return user
    
    # --- Account Management ---
    
    @staticmethod
    def get_user_connections(user: User):
        """Get all social connections for a user."""
        return SocialConnection.objects.filter(user=user)
    
    @staticmethod
    def disconnect(user: User, provider: str):
        """
        Disconnect a social account.
        
        Raises:
            OAuthError: If it's the only login method
        """
        connection = SocialConnection.objects.filter(
            user=user,
            provider=provider
        ).first()
        
        if not connection:
            raise OAuthError('Connection not found', 'not_found')
        
        # Check if user has password or other connections
        has_password = user.has_usable_password()
        other_connections = SocialConnection.objects.filter(user=user).exclude(provider=provider).exists()
        
        if connection.is_primary and not has_password and not other_connections:
            raise OAuthError(
                'Không thể ngắt kết nối phương thức đăng nhập duy nhất',
                'cannot_disconnect'
            )
        
        connection.delete()
        logger.info(f"Disconnected {provider} from user: {user.email}")
    
    @staticmethod
    def get_available_providers():
        """Get list of available OAuth providers."""
        # Get from DB
        db_providers = ProviderConfig.objects.filter(is_active=True).values_list('provider', flat=True)
        
        # Check env for additional providers
        env_providers = []
        for provider in OAuthProvider.values:
            provider_upper = provider.upper()
            if getattr(settings, f'{provider_upper}_CLIENT_ID', None):
                if provider not in db_providers:
                    env_providers.append(provider)
        
        return list(db_providers) + env_providers
