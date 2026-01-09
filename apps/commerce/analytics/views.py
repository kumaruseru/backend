"""Commerce Analytics - API Views.

REST API endpoints for analytics data access.
"""
from datetime import date, timedelta
from decimal import Decimal

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone

from .models import (
    DailyMetric, MonthlyReport, ProductAnalytics,
    CustomerSegment, SalesFunnel, RevenueBreakdown,
    TrafficSource, AbandonedCartMetric
)
from .serializers import (
    DailyMetricSerializer, DailyMetricSummarySerializer,
    MonthlyReportSerializer, ProductAnalyticsSerializer,
    ProductAnalyticsSummarySerializer, CustomerSegmentSerializer,
    CustomerSegmentSummarySerializer, SalesFunnelSerializer,
    RevenueBreakdownSerializer, TrafficSourceSerializer,
    AbandonedCartMetricSerializer, DashboardKPISerializer,
)
from .services import (
    AnalyticsService, SalesAnalyticsService, ProductAnalyticsService,
    CustomerAnalyticsService, FunnelAnalyticsService, RevenueAnalyticsService
)


class DashboardAPIView(APIView):
    """Main dashboard KPIs and summary data."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        days = min(max(days, 7), 365)  # Clamp between 7-365
        
        summary = AnalyticsService.get_dashboard_summary(days)
        
        # Add additional summary data
        summary['orders_by_status'] = AnalyticsService.get_orders_by_status(days)
        summary['top_products'] = AnalyticsService.get_top_products(days, limit=5)
        
        return Response(summary)


class RevenueChartAPIView(APIView):
    """Revenue trend chart data."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        days = min(max(days, 7), 365)
        
        chart_data = AnalyticsService.get_revenue_chart_data(days)
        
        return Response({
            'period_days': days,
            'data': chart_data,
        })


class SalesTrendAPIView(APIView):
    """Sales trend and statistics."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        trend_data = SalesAnalyticsService.get_daily_sales_trend(days)
        aov_trend = SalesAnalyticsService.calculate_aov_trend(days)
        hourly = SalesAnalyticsService.get_hourly_distribution(min(days, 7))
        
        return Response({
            'period_days': days,
            'daily_trend': trend_data,
            'aov_trend': aov_trend,
            'hourly_distribution': hourly,
        })


class DailyMetricsListView(ListAPIView):
    """List daily metrics with pagination."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = DailyMetricSerializer
    
    def get_queryset(self):
        queryset = DailyMetric.objects.all()
        
        # Date range filter
        start = self.request.query_params.get('start_date')
        end = self.request.query_params.get('end_date')
        
        if start:
            queryset = queryset.filter(date__gte=start)
        if end:
            queryset = queryset.filter(date__lte=end)
        
        return queryset.order_by('-date')


class MonthlyReportsListView(ListAPIView):
    """List monthly reports."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = MonthlyReportSerializer
    queryset = MonthlyReport.objects.all().order_by('-year', '-month')


class ProductAnalyticsListView(ListAPIView):
    """List product analytics with filtering."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ProductAnalyticsSummarySerializer
    
    def get_queryset(self):
        queryset = ProductAnalytics.objects.select_related('product').all()
        
        # Filters
        trending = self.request.query_params.get('trending')
        slow_mover = self.request.query_params.get('slow_mover')
        
        if trending == 'true':
            queryset = queryset.filter(trending_up=True)
        if slow_mover == 'true':
            queryset = queryset.filter(slow_mover=True)
        
        # Ordering
        order_by = self.request.query_params.get('order_by', '-revenue_30d')
        valid_orders = ['-revenue_30d', 'revenue_30d', '-performance_score', 
                       'performance_score', '-total_revenue', 'total_revenue']
        
        if order_by in valid_orders:
            queryset = queryset.order_by(order_by)
        
        return queryset


class TopProductsAPIView(APIView):
    """Get top performing products."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        limit = min(max(limit, 5), 50)
        
        top_performers = ProductAnalyticsService.get_top_performers(limit)
        trending = ProductAnalyticsService.get_trending_products(limit)
        slow_movers = ProductAnalyticsService.get_slow_movers(limit)
        
        return Response({
            'top_performers': ProductAnalyticsSummarySerializer(top_performers, many=True).data,
            'trending': ProductAnalyticsSummarySerializer(trending, many=True).data,
            'slow_movers': ProductAnalyticsSummarySerializer(slow_movers, many=True).data,
        })


class CustomerSegmentsListView(ListAPIView):
    """List customer segments."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = CustomerSegmentSummarySerializer
    
    def get_queryset(self):
        queryset = CustomerSegment.objects.select_related('user').all()
        
        # Filter by segment
        segment = self.request.query_params.get('segment')
        if segment:
            queryset = queryset.filter(segment=segment)
        
        # Filter high churn risk
        high_risk = self.request.query_params.get('high_risk')
        if high_risk == 'true':
            queryset = queryset.filter(churn_risk__gte=70)
        
        return queryset.order_by('-total_spent')


class CustomerInsightsAPIView(APIView):
    """Customer analytics insights."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        
        distribution = CustomerAnalyticsService.get_segment_distribution()
        high_value = CustomerAnalyticsService.get_high_value_customers(limit)
        at_risk = CustomerAnalyticsService.get_at_risk_customers(limit)
        
        # Calculate segment percentages
        total = sum(distribution.values())
        segment_data = [
            {
                'segment': seg,
                'count': count,
                'percentage': round((count / total) * 100, 2) if total > 0 else 0
            }
            for seg, count in distribution.items()
        ]
        
        return Response({
            'segment_distribution': segment_data,
            'high_value_customers': CustomerSegmentSummarySerializer(high_value, many=True).data,
            'at_risk_customers': CustomerSegmentSummarySerializer(at_risk, many=True).data,
        })


class SalesFunnelListView(ListAPIView):
    """List sales funnel data."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = SalesFunnelSerializer
    
    def get_queryset(self):
        queryset = SalesFunnel.objects.all()
        
        days = int(self.request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days - 1)
        queryset = queryset.filter(date__gte=start_date)
        
        return queryset.order_by('-date')


class FunnelAnalysisAPIView(APIView):
    """Conversion funnel analysis."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        trend = FunnelAnalyticsService.get_funnel_trend(days)
        drop_off = FunnelAnalyticsService.get_drop_off_analysis(days)
        
        return Response({
            'period_days': days,
            'trend': trend,
            'drop_off_analysis': drop_off,
        })


class RevenueBreakdownAPIView(APIView):
    """Revenue breakdown by various dimensions."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        breakdown_type = request.query_params.get('type', 'payment')
        
        valid_types = {
            'payment': RevenueBreakdown.BreakdownType.PAYMENT_METHOD,
            'source': RevenueBreakdown.BreakdownType.ORDER_SOURCE,
            'region': RevenueBreakdown.BreakdownType.REGION,
            'category': RevenueBreakdown.BreakdownType.CATEGORY,
        }
        
        breakdown_type = valid_types.get(breakdown_type, valid_types['payment'])
        
        data = RevenueAnalyticsService.get_breakdown_summary(breakdown_type, days)
        
        return Response({
            'period_days': days,
            'breakdown_type': breakdown_type,
            'data': data,
        })


class AbandonedCartAnalyticsAPIView(APIView):
    """Abandoned cart analytics."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days - 1)
        
        metrics = AbandonedCartMetric.objects.filter(
            date__gte=start_date
        ).order_by('-date')
        
        serializer = AbandonedCartMetricSerializer(metrics, many=True)
        
        return Response({
            'period_days': days,
            'data': serializer.data,
        })


class ExportAnalyticsAPIView(APIView):
    """Export analytics data (CSV/JSON)."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        export_type = request.data.get('type', 'daily_metrics')
        format_type = request.data.get('format', 'json')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        # Validate dates
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get data based on type
        if export_type == 'daily_metrics':
            data = DailyMetric.objects.filter(
                date__range=(start_date, end_date)
            ).order_by('date')
            serializer = DailyMetricSerializer(data, many=True)
        elif export_type == 'monthly_reports':
            data = MonthlyReport.objects.all().order_by('-year', '-month')
            serializer = MonthlyReportSerializer(data, many=True)
        elif export_type == 'product_analytics':
            data = ProductAnalytics.objects.select_related('product').all()
            serializer = ProductAnalyticsSerializer(data, many=True)
        else:
            return Response(
                {'error': f'Unknown export type: {export_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if format_type == 'csv':
            # For CSV export, you'd typically generate a file response
            # This is a simplified JSON response
            return Response({
                'format': 'csv',
                'message': 'CSV export would be generated here',
                'record_count': len(serializer.data),
            })
        
        return Response({
            'export_type': export_type,
            'record_count': len(serializer.data),
            'data': serializer.data,
        })
