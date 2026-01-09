from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('<uuid:notification_id>/', views.NotificationDetailView.as_view(), name='detail'),
    path('mark-read/', views.MarkReadView.as_view(), name='mark_read'),
    path('unread-count/', views.UnreadCountView.as_view(), name='unread_count'),
    path('preferences/', views.PreferencesView.as_view(), name='preferences'),
    path('devices/', views.DeviceTokenView.as_view(), name='devices'),
]
