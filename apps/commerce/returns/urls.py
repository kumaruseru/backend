"""Commerce Returns - URL Configuration (Production-Ready)."""
from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    # ===== User Endpoints =====
    
    # List and create
    path('', views.ReturnRequestListView.as_view(), name='list'),
    
    # Detail operations
    path('<uuid:request_id>/', views.ReturnRequestDetailView.as_view(), name='detail'),
    path('<uuid:request_id>/cancel/', views.ReturnCancelView.as_view(), name='cancel'),
    path('<uuid:request_id>/images/', views.ReturnImageUploadView.as_view(), name='upload_image'),
    path('<uuid:request_id>/tracking/', views.ReturnTrackingView.as_view(), name='tracking'),
    
    # By request number
    path('number/<str:request_number>/', views.ReturnByNumberView.as_view(), name='by_number'),
    
    # ===== Admin Endpoints =====
    
    # List and statistics
    path('admin/', views.AdminReturnListView.as_view(), name='admin_list'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
    
    # Workflow actions
    path('admin/<uuid:request_id>/', views.AdminReturnDetailView.as_view(), name='admin_detail'),
    path('admin/<uuid:request_id>/review/', views.AdminStartReviewView.as_view(), name='admin_review'),
    path('admin/<uuid:request_id>/approve/', views.AdminApproveView.as_view(), name='admin_approve'),
    path('admin/<uuid:request_id>/reject/', views.AdminRejectView.as_view(), name='admin_reject'),
    path('admin/<uuid:request_id>/receive/', views.AdminReceiveView.as_view(), name='admin_receive'),
    path('admin/<uuid:request_id>/refund/', views.AdminProcessRefundView.as_view(), name='admin_refund'),
    path('admin/<uuid:request_id>/complete/', views.AdminCompleteView.as_view(), name='admin_complete'),
]
