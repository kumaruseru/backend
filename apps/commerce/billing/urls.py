"""Commerce Billing - URL Configuration (Production-Ready)."""
from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # ===== User Endpoints =====
    
    # Payments
    path('payments/', views.PaymentListView.as_view(), name='list'),
    path('payments/create/', views.PaymentCreateView.as_view(), name='create'),
    path('payments/<uuid:payment_id>/', views.PaymentDetailView.as_view(), name='detail'),
    path('payments/<uuid:payment_id>/retry/', views.PaymentRetryView.as_view(), name='retry'),
    path('payments/<uuid:payment_id>/cancel/', views.PaymentCancelView.as_view(), name='cancel'),
    
    # Saved payment methods
    path('methods/', views.PaymentMethodListView.as_view(), name='methods'),
    path('methods/<uuid:method_id>/', views.PaymentMethodDetailView.as_view(), name='method_detail'),
    path('methods/<uuid:method_id>/default/', views.PaymentMethodSetDefaultView.as_view(), name='method_default'),
    
    # ===== Webhooks =====
    path('callback/vnpay/', views.VNPayCallbackView.as_view(), name='callback_vnpay'),
    path('callback/momo/', views.MoMoCallbackView.as_view(), name='callback_momo'),
    
    # ===== Admin Endpoints =====
    path('admin/', views.AdminPaymentListView.as_view(), name='admin_list'),
    path('admin/statistics/', views.AdminPaymentStatisticsView.as_view(), name='admin_stats'),
    path('admin/<uuid:payment_id>/', views.AdminPaymentDetailView.as_view(), name='admin_detail'),
    path('admin/refund/', views.AdminRefundView.as_view(), name='admin_refund'),
]
