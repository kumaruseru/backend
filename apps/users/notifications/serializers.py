from rest_framework import serializers
from .models import (
    Notification, NotificationPreference, DeviceToken, NotificationType
)


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True
    )
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'notification_type_display',
            'title', 'message', 'image_url',
            'action_url', 'action_text', 'data',
            'is_read', 'read_at', 'priority',
            'is_expired', 'expires_at', 'created_at'
        ]


class NotificationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message',
            'action_url', 'is_read', 'priority', 'created_at'
        ]


class NotificationPreferenceSerializer(serializers.Serializer):
    notification_type = serializers.CharField()
    label = serializers.CharField()
    in_app = serializers.BooleanField()
    email = serializers.BooleanField()
    push = serializers.BooleanField()
    sms = serializers.BooleanField()


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    notification_type = serializers.ChoiceField(choices=NotificationType.choices)
    in_app = serializers.BooleanField(required=False)
    email = serializers.BooleanField(required=False)
    push = serializers.BooleanField(required=False)
    sms = serializers.BooleanField(required=False)


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'platform', 'device_name', 'is_active', 'last_used', 'created_at']


class DeviceTokenRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=500)
    platform = serializers.ChoiceField(choices=DeviceToken.Platform.choices)
    device_name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class MarkReadSerializer(serializers.Serializer):
    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="List of notification IDs to mark as read. Empty = mark all as read."
    )


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()
