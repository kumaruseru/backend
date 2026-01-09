"""Commerce Returns - URL Configuration."""
from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    # User
    path('returns/', views.UserReturnListView.as_view(), name='list'),
    path('returns/create/', views.UserReturnCreateView.as_view(), name='create'),
    path('returns/<uuid:return_id>/', views.UserReturnDetailView.as_view(), name='detail'),
    path('returns/<uuid:return_id>/cancel/', views.UserReturnCancelView.as_view(), name='cancel'),

    # Admin
    path('admin/returns/', views.AdminReturnListView.as_view(), name='admin_list'),
    path('admin/returns/<uuid:return_id>/', views.AdminReturnDetailView.as_view(), name='admin_detail'),
    path('admin/returns/<uuid:return_id>/approve/', views.AdminReturnApproveView.as_view(), name='admin_approve'),
    path('admin/returns/<uuid:return_id>/reject/', views.AdminReturnRejectView.as_view(), name='admin_reject'),
    path('admin/returns/<uuid:return_id>/receive/', views.AdminReturnReceiveView.as_view(), name='admin_receive'),
    path('admin/returns/<uuid:return_id>/complete/', views.AdminReturnCompleteView.as_view(), name='admin_complete'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
]
