"""
Users Social - Production-Ready Models.

Social authentication and OAuth management:
- OAuthProvider: Provider configuration (Google, GitHub, Facebook)
- SocialConnection: User's connected social accounts
- OAuthState: CSRF protection for OAuth flow
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets
from datetime import timedelta

from apps.common.core.models import TimeStampedModel


class OAuthProvider(models.TextChoices):
    """Supported OAuth providers."""
    GOOGLE = 'google', 'Google'
    GITHUB = 'github', 'GitHub'
    FACEBOOK = 'facebook', 'Facebook'
    APPLE = 'apple', 'Apple'
    DISCORD = 'discord', 'Discord'


class ProviderConfig(TimeStampedModel):
    """
    OAuth provider configuration.
    
    Stores provider settings (can be in DB for dynamic config
    or use env vars for production).
    """
    
    provider = models.CharField(
        max_length=20,
        choices=OAuthProvider.choices,
        unique=True,
        verbose_name='Provider'
    )
    
    # OAuth credentials
    client_id = models.CharField(max_length=200, verbose_name='Client ID')
    client_secret = models.CharField(max_length=200, verbose_name='Client Secret')
    
    # URLs
    authorize_url = models.URLField(verbose_name='Authorize URL')
    token_url = models.URLField(verbose_name='Token URL')
    userinfo_url = models.URLField(verbose_name='User Info URL')
    
    # Scopes
    scopes = models.JSONField(default=list, verbose_name='Scopes')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='Active')
    
    # Display
    display_name = models.CharField(max_length=50, blank=True)
    icon_url = models.URLField(blank=True)
    button_color = models.CharField(max_length=7, blank=True)  # HEX color
    
    class Meta:
        verbose_name = 'OAuth Provider Config'
        verbose_name_plural = 'OAuth Provider Configs'
    
    def __str__(self) -> str:
        return self.get_provider_display()
    
    @classmethod
    def get_config(cls, provider: str) -> 'ProviderConfig':
        """Get provider config, fallback to environment vars."""
        try:
            return cls.objects.get(provider=provider, is_active=True)
        except cls.DoesNotExist:
            # Build from environment
            return cls._build_from_env(provider)
    
    @classmethod
    def _build_from_env(cls, provider: str):
        """Build config from environment variables."""
        from django.conf import settings
        
        provider_upper = provider.upper()
        
        # Get from settings
        client_id = getattr(settings, f'{provider_upper}_CLIENT_ID', '')
        client_secret = getattr(settings, f'{provider_upper}_CLIENT_SECRET', '')
        
        if not client_id or not client_secret:
            return None
        
        # Provider-specific URLs
        configs = {
            'google': {
                'authorize_url': 'https://accounts.google.com/o/oauth2/v2/auth',
                'token_url': 'https://oauth2.googleapis.com/token',
                'userinfo_url': 'https://www.googleapis.com/oauth2/v2/userinfo',
                'scopes': ['openid', 'email', 'profile']
            },
            'github': {
                'authorize_url': 'https://github.com/login/oauth/authorize',
                'token_url': 'https://github.com/login/oauth/access_token',
                'userinfo_url': 'https://api.github.com/user',
                'scopes': ['user:email']
            },
            'facebook': {
                'authorize_url': 'https://www.facebook.com/v18.0/dialog/oauth',
                'token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',
                'userinfo_url': 'https://graph.facebook.com/me?fields=id,name,email,picture',
                'scopes': ['email', 'public_profile']
            }
        }
        
        config = configs.get(provider, {})
        
        return cls(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url=config.get('authorize_url', ''),
            token_url=config.get('token_url', ''),
            userinfo_url=config.get('userinfo_url', ''),
            scopes=config.get('scopes', [])
        )


class SocialConnection(TimeStampedModel):
    """
    Social account connection for a user.
    
    Stores OAuth tokens and user info from social providers.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='social_connections',
        verbose_name='Người dùng'
    )
    
    provider = models.CharField(
        max_length=20,
        choices=OAuthProvider.choices,
        verbose_name='Provider'
    )
    
    # Provider user info
    provider_user_id = models.CharField(max_length=200, verbose_name='Provider User ID')
    provider_username = models.CharField(max_length=200, blank=True)
    provider_email = models.EmailField(blank=True)
    provider_name = models.CharField(max_length=200, blank=True)
    provider_avatar = models.URLField(blank=True, max_length=500)
    
    # OAuth tokens (encrypted in production)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Extra data from provider
    extra_data = models.JSONField(default=dict, blank=True)
    
    # Status
    is_primary = models.BooleanField(default=False)  # Primary login method
    last_login = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Social Connection'
        verbose_name_plural = 'Social Connections'
        unique_together = ['provider', 'provider_user_id']
        indexes = [
            models.Index(fields=['user', 'provider']),
            models.Index(fields=['provider', 'provider_user_id']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.get_provider_display()}"
    
    @property
    def is_token_expired(self) -> bool:
        if self.token_expires_at:
            return timezone.now() > self.token_expires_at
        return False
    
    @property
    def display_name(self) -> str:
        return self.provider_name or self.provider_username or self.provider_email
    
    def update_tokens(self, access_token: str, refresh_token: str = None, expires_in: int = None):
        """Update OAuth tokens."""
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_in:
            self.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        self.save(update_fields=['access_token', 'refresh_token', 'token_expires_at', 'updated_at'])
    
    def record_login(self):
        """Record a login via this connection."""
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])


class OAuthState(TimeStampedModel):
    """
    OAuth state for CSRF protection.
    
    Stores temporary state during OAuth flow.
    """
    
    state = models.CharField(max_length=64, unique=True, db_index=True)
    provider = models.CharField(max_length=20, choices=OAuthProvider.choices)
    
    # Optional user (for linking existing account)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    
    # Where to redirect after auth
    redirect_uri = models.URLField()
    next_url = models.CharField(max_length=500, blank=True)
    
    # Extra context
    action = models.CharField(
        max_length=20,
        default='login',
        choices=[
            ('login', 'Login'),
            ('register', 'Register'),
            ('link', 'Link Account'),
        ]
    )
    
    # Expiration
    expires_at = models.DateTimeField()
    
    class Meta:
        verbose_name = 'OAuth State'
        verbose_name_plural = 'OAuth States'
    
    def __str__(self) -> str:
        return f"{self.provider} - {self.state[:8]}..."
    
    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
    
    @classmethod
    def create_state(cls, provider: str, redirect_uri: str, user=None, 
                     action: str = 'login', next_url: str = '') -> str:
        """Create a new OAuth state."""
        state_token = secrets.token_urlsafe(32)
        
        cls.objects.create(
            state=state_token,
            provider=provider,
            redirect_uri=redirect_uri,
            user=user,
            action=action,
            next_url=next_url,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        return state_token
    
    @classmethod
    def verify_state(cls, state: str) -> 'OAuthState':
        """Verify and consume a state token."""
        try:
            oauth_state = cls.objects.get(state=state)
            if oauth_state.is_expired:
                oauth_state.delete()
                return None
            return oauth_state
        except cls.DoesNotExist:
            return None
    
    def consume(self):
        """Consume (delete) this state after use."""
        self.delete()


class SocialLoginLog(TimeStampedModel):
    """
    Log of social login attempts.
    """
    
    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        ERROR = 'error', 'Error'
    
    provider = models.CharField(max_length=20, choices=OAuthProvider.choices)
    
    # User (if known)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='social_login_logs'
    )
    
    # Provider info
    provider_user_id = models.CharField(max_length=200, blank=True)
    provider_email = models.EmailField(blank=True)
    
    # Result
    status = models.CharField(max_length=10, choices=Status.choices)
    action = models.CharField(max_length=20, blank=True)  # login, register, link
    error_message = models.TextField(blank=True)
    
    # Request info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Social Login Log'
        verbose_name_plural = 'Social Login Logs'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.provider} - {self.status}"
