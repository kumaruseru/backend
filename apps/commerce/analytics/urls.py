"""Commerce Analytics - URL Configuration."""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardAPIView.as_view(), name='dashboard'),
    path('revenue-chart/', views.RevenueChartAPIView.as_view(), name='revenue-chart'),
    
    # Sales
    path('sales/trend/', views.SalesTrendAPIView.as_view(), name='sales-trend'),
    
    # Daily & Monthly Metrics
    path('daily/', views.DailyMetricsListView.as_view(), name='daily-metrics'),
    path('monthly/', views.MonthlyReportsListView.as_view(), name='monthly-reports'),
    
    # Products
    path('products/', views.ProductAnalyticsListView.as_view(), name='product-analytics'),
    path('products/top/', views.TopProductsAPIView.as_view(), name='top-products'),
    
    # Customers
    path('customers/', views.CustomerSegmentsListView.as_view(), name='customer-segments'),
    path('customers/insights/', views.CustomerInsightsAPIView.as_view(), name='customer-insights'),
    
    # Funnel
    path('funnel/', views.SalesFunnelListView.as_view(), name='sales-funnel'),
    path('funnel/analysis/', views.FunnelAnalysisAPIView.as_view(), name='funnel-analysis'),
    
    # Revenue
    path('revenue/breakdown/', views.RevenueBreakdownAPIView.as_view(), name='revenue-breakdown'),
    
    # Abandoned Carts
    path('abandoned-carts/', views.AbandonedCartAnalyticsAPIView.as_view(), name='abandoned-carts'),
    
    # Export
    path('export/', views.ExportAnalyticsAPIView.as_view(), name='export'),
]
