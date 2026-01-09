"""Commerce Billing - URL Configuration."""
from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # Payment Gateways
    path('gateways/', views.AvailableGatewaysView.as_view(), name='gateways'),
    
    # Payments
    path('create/', views.CreatePaymentView.as_view(), name='create-payment'),
    path('callback/<str:gateway>/', views.PaymentCallbackView.as_view(), name='payment-callback'),
    path('webhook/<str:gateway>/', views.WebhookView.as_view(), name='webhook'),
    
    # Transactions
    path('transactions/', views.TransactionListView.as_view(), name='transaction-list'),
    path('transactions/<str:transaction_id>/', views.TransactionDetailView.as_view(), name='transaction-detail'),
    
    # Refunds
    path('refunds/', views.RefundListView.as_view(), name='refund-list'),
    path('refunds/create/', views.CreateRefundView.as_view(), name='create-refund'),
]
