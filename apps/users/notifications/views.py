from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Notification, DeviceToken
from .services import NotificationService
from .serializers import (
    NotificationSerializer, NotificationListSerializer,
    NotificationPreferenceSerializer, NotificationPreferenceUpdateSerializer,
    DeviceTokenSerializer, DeviceTokenRegisterSerializer,
    MarkReadSerializer, UnreadCountSerializer
)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter('unread_only', bool, description='Only unread'),
            OpenApiParameter('type', str, description='Filter by type'),
            OpenApiParameter('limit', int, description='Limit'),
            OpenApiParameter('offset', int, description='Offset'),
        ],
        tags=['Notifications']
    )
    def get(self, request):
        result = NotificationService.get_user_notifications(
            user=request.user,
            unread_only=request.query_params.get('unread_only', '').lower() == 'true',
            notification_type=request.query_params.get('type'),
            limit=int(request.query_params.get('limit', 50)),
            offset=int(request.query_params.get('offset', 0))
        )

        return Response({
            'notifications': NotificationListSerializer(
                result['notifications'], many=True
            ).data,
            'total': result['total'],
            'unread_count': result['unread_count']
        })


class NotificationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Notifications'])
    def get(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.mark_as_read()
            return Response(NotificationSerializer(notification).data)
        except Notification.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @extend_schema(tags=['Notifications'])
    def delete(self, request, notification_id):
        if NotificationService.delete_notification(notification_id, request.user):
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_404_NOT_FOUND)


class MarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=MarkReadSerializer, tags=['Notifications'])
    def post(self, request):
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        notification_ids = serializer.validated_data.get('notification_ids', [])

        if notification_ids:
            count = Notification.objects.filter(
                id__in=notification_ids,
                user=request.user,
                is_read=False
            ).update(is_read=True)
        else:
            count = NotificationService.mark_all_as_read(request.user)

        return Response({'marked': count})


class UnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UnreadCountSerializer}, tags=['Notifications'])
    def get(self, request):
        count = NotificationService.get_unread_count(request.user)
        return Response({'unread_count': count})


class PreferencesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Notification Preferences'])
    def get(self, request):
        prefs = NotificationService.get_preferences(request.user)
        pref_list = [
            {'notification_type': k, **v}
            for k, v in prefs.items()
        ]
        return Response(NotificationPreferenceSerializer(pref_list, many=True).data)

    @extend_schema(
        request=NotificationPreferenceUpdateSerializer,
        tags=['Notification Preferences']
    )
    def patch(self, request):
        serializer = NotificationPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        NotificationService.update_preference(
            user=request.user,
            notification_type=data['notification_type'],
            in_app=data.get('in_app'),
            email=data.get('email'),
            push=data.get('push'),
            sms=data.get('sms')
        )

        return Response({'message': 'Đã cập nhật cài đặt'})


class DeviceTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Push Notifications'])
    def get(self, request):
        tokens = DeviceToken.objects.filter(user=request.user, is_active=True)
        return Response(DeviceTokenSerializer(tokens, many=True).data)

    @extend_schema(request=DeviceTokenRegisterSerializer, tags=['Push Notifications'])
    def post(self, request):
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = NotificationService.register_device(
            user=request.user,
            **serializer.validated_data
        )

        return Response(
            DeviceTokenSerializer(device).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(tags=['Push Notifications'])
    def delete(self, request):
        token = request.data.get('token')
        if token:
            NotificationService.unregister_device(token)
        return Response(status=status.HTTP_204_NO_CONTENT)
