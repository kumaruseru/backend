"""Users Social - Models for OAuth and Social Authentication."""
from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets
from datetime import timedelta

from apps.common.core.models import TimeStampedModel


class OAuthProvider(models.TextChoices):
    GOOGLE = 'google', 'Google'
    GITHUB = 'github', 'GitHub'
    FACEBOOK = 'facebook', 'Facebook'
    APPLE = 'apple', 'Apple'
    DISCORD = 'discord', 'Discord'


class ProviderConfig(TimeStampedModel):
    provider = models.CharField(max_length=20, choices=OAuthProvider.choices, unique=True, verbose_name='Provider')
    client_id = models.CharField(max_length=200, verbose_name='Client ID')
    client_secret = models.CharField(max_length=200, verbose_name='Client Secret')
    authorize_url = models.URLField(verbose_name='Authorize URL')
    token_url = models.URLField(verbose_name='Token URL')
    userinfo_url = models.URLField(verbose_name='User Info URL')
    scopes = models.JSONField(default=list, verbose_name='Scopes')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    display_name = models.CharField(max_length=50, blank=True)
    icon_url = models.URLField(blank=True)
    button_color = models.CharField(max_length=7, blank=True)

    class Meta:
        verbose_name = 'OAuth Provider Config'
        verbose_name_plural = 'OAuth Provider Configs'

    def __str__(self) -> str:
        return self.get_provider_display()

    @classmethod
    def get_config(cls, provider: str) -> 'ProviderConfig':
        try:
            return cls.objects.get(provider=provider, is_active=True)
        except cls.DoesNotExist:
            return cls._build_from_env(provider)

    @classmethod
    def _build_from_env(cls, provider: str):
        provider_upper = provider.upper()
        client_id = getattr(settings, f'{provider_upper}_CLIENT_ID', '')
        client_secret = getattr(settings, f'{provider_upper}_CLIENT_SECRET', '')
        if not client_id or not client_secret:
            return None
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_connections', verbose_name='User')
    provider = models.CharField(max_length=20, choices=OAuthProvider.choices, verbose_name='Provider')
    provider_user_id = models.CharField(max_length=200, verbose_name='Provider User ID')
    provider_username = models.CharField(max_length=200, blank=True)
    provider_email = models.EmailField(blank=True)
    provider_name = models.CharField(max_length=200, blank=True)
    provider_avatar = models.URLField(blank=True, max_length=500)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    is_primary = models.BooleanField(default=False)
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
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_in:
            self.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        self.save(update_fields=['access_token', 'refresh_token', 'token_expires_at', 'updated_at'])

    def record_login(self):
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])


class OAuthState(TimeStampedModel):
    state = models.CharField(max_length=64, unique=True, db_index=True)
    provider = models.CharField(max_length=20, choices=OAuthProvider.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    redirect_uri = models.URLField()
    next_url = models.CharField(max_length=500, blank=True)
    action = models.CharField(max_length=20, default='login', choices=[('login', 'Login'), ('register', 'Register'), ('link', 'Link Account')])
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
    def create_state(cls, provider: str, redirect_uri: str, user=None, action: str = 'login', next_url: str = '') -> str:
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
        try:
            oauth_state = cls.objects.get(state=state)
            if oauth_state.is_expired:
                oauth_state.delete()
                return None
            return oauth_state
        except cls.DoesNotExist:
            return None

    def consume(self):
        self.delete()


class SocialLoginLog(TimeStampedModel):
    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        ERROR = 'error', 'Error'

    provider = models.CharField(max_length=20, choices=OAuthProvider.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='social_login_logs')
    provider_user_id = models.CharField(max_length=200, blank=True)
    provider_email = models.EmailField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    action = models.CharField(max_length=20, blank=True)
    error_message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Social Login Log'
        verbose_name_plural = 'Social Login Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.provider} - {self.status}"
