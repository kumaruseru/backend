"""
Users Social - Serializers.

DTOs for OAuth API.
"""
from rest_framework import serializers
from .models import SocialConnection, OAuthProvider


class OAuthProviderSerializer(serializers.Serializer):
    """Available OAuth provider."""
    provider = serializers.CharField()
    name = serializers.CharField()
    icon_url = serializers.URLField(required=False, allow_blank=True)
    button_color = serializers.CharField(required=False, allow_blank=True)


class OAuthAuthorizeSerializer(serializers.Serializer):
    """OAuth authorization request input."""
    provider = serializers.ChoiceField(choices=OAuthProvider.choices)
    next_url = serializers.CharField(max_length=500, required=False, allow_blank=True)


class OAuthAuthorizeResponseSerializer(serializers.Serializer):
    """OAuth authorization response."""
    authorization_url = serializers.URLField()


class OAuthCallbackSerializer(serializers.Serializer):
    """OAuth callback input."""
    code = serializers.CharField()
    state = serializers.CharField()


class OAuthTokensSerializer(serializers.Serializer):
    """OAuth tokens response."""
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    next_url = serializers.CharField(required=False)


class SocialConnectionSerializer(serializers.ModelSerializer):
    """Social connection output."""
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    display_name = serializers.ReadOnlyField()
    is_token_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = SocialConnection
        fields = [
            'id', 'provider', 'provider_display',
            'provider_username', 'provider_email', 'provider_name', 'provider_avatar',
            'display_name', 'is_primary', 'is_token_expired',
            'last_login', 'created_at'
        ]


class DisconnectSerializer(serializers.Serializer):
    """Disconnect social account input."""
    provider = serializers.ChoiceField(choices=OAuthProvider.choices)
