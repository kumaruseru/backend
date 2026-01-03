"""
Store Marketing - Production-Ready API Views.
"""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Coupon, Banner, FlashSale, Campaign
from .serializers import (
    CouponSerializer, CouponSimpleSerializer, CouponApplySerializer, CouponResultSerializer,
    CouponUsageSerializer,
    BannerSerializer, BannerSimpleSerializer,
    FlashSaleSerializer, FlashSaleListSerializer, FlashSaleItemSerializer,
    CampaignSerializer, CampaignListSerializer,
    MarketingStatisticsSerializer
)
from .services import CouponService, BannerService, FlashSaleService, MarketingService


# ==================== Coupon Endpoints ====================

class CouponListView(generics.ListAPIView):
    """List available public coupons."""
    permission_classes = [permissions.AllowAny]
    serializer_class = CouponSimpleSerializer
    pagination_class = None
    
    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        return CouponService.get_available_coupons(user)
    
    @extend_schema(
        responses={200: CouponSimpleSerializer(many=True)},
        tags=['Marketing - Coupons']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CouponValidateView(APIView):
    """Validate a coupon code."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=CouponApplySerializer,
        responses={200: CouponResultSerializer},
        tags=['Marketing - Coupons']
    )
    def post(self, request):
        serializer = CouponApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user if request.user.is_authenticated else None
        
        result = CouponService.validate_coupon(
            code=serializer.validated_data['code'],
            user=user,
            order_total=serializer.validated_data['order_total']
        )
        
        response_data = {
            'valid': result['valid'],
            'discount_amount': result['discount_amount'],
            'message': result['message']
        }
        
        if result['coupon']:
            response_data['coupon'] = CouponSimpleSerializer(result['coupon']).data
        
        return Response(response_data)


class CouponDetailView(APIView):
    """Get coupon details by code."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        responses={200: CouponSerializer},
        tags=['Marketing - Coupons']
    )
    def get(self, request, code):
        try:
            coupon = CouponService.get_coupon(code)
            return Response(CouponSerializer(coupon).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class MyCouponHistoryView(generics.ListAPIView):
    """List user's coupon usage history."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CouponUsageSerializer
    pagination_class = None
    
    def get_queryset(self):
        return CouponService.get_user_coupon_history(self.request.user)
    
    @extend_schema(tags=['Marketing - Coupons'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== Banner Endpoints ====================

class BannerListView(generics.ListAPIView):
    """List active banners."""
    permission_classes = [permissions.AllowAny]
    serializer_class = BannerSimpleSerializer
    pagination_class = None
    
    def get_queryset(self):
        position = self.request.query_params.get('position')
        category_id = self.request.query_params.get('category_id')
        return BannerService.get_active_banners(position, category_id)
    
    @extend_schema(
        parameters=[
            OpenApiParameter('position', str, enum=['hero', 'sidebar', 'category', 'popup', 'footer']),
            OpenApiParameter('category_id', int),
        ],
        responses={200: BannerSimpleSerializer(many=True)},
        tags=['Marketing - Banners']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BannerClickView(APIView):
    """Track banner click."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(tags=['Marketing - Banners'])
    def post(self, request, banner_id):
        BannerService.track_click(banner_id)
        return Response({'success': True})


# ==================== Flash Sale Endpoints ====================

class FlashSaleCurrentView(APIView):
    """Get current active flash sale."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        responses={200: FlashSaleSerializer},
        tags=['Marketing - Flash Sales']
    )
    def get(self, request):
        sale = FlashSaleService.get_active_flash_sale()
        
        if sale:
            return Response(FlashSaleSerializer(sale).data)
        
        return Response({'active': False, 'message': 'Không có Flash Sale đang diễn ra'})


class FlashSaleUpcomingView(generics.ListAPIView):
    """List upcoming flash sales."""
    permission_classes = [permissions.AllowAny]
    serializer_class = FlashSaleListSerializer
    pagination_class = None
    
    def get_queryset(self):
        return FlashSaleService.get_upcoming_flash_sales()
    
    @extend_schema(
        responses={200: FlashSaleListSerializer(many=True)},
        tags=['Marketing - Flash Sales']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class FlashSaleDetailView(APIView):
    """Get flash sale details."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        responses={200: FlashSaleSerializer},
        tags=['Marketing - Flash Sales']
    )
    def get(self, request, sale_id):
        try:
            sale = FlashSaleService.get_flash_sale_by_id(sale_id)
            return Response(FlashSaleSerializer(sale).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class ProductFlashPriceView(APIView):
    """Get flash sale price for a product."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(tags=['Marketing - Flash Sales'])
    def get(self, request, product_id):
        flash_info = FlashSaleService.get_flash_price(product_id)
        
        if flash_info:
            return Response({'has_flash_price': True, **flash_info})
        
        return Response({'has_flash_price': False})


# ==================== Admin Endpoints ====================

class AdminCouponListView(generics.ListAPIView):
    """Admin: List all coupons."""
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CouponSerializer
    
    def get_queryset(self):
        queryset = Coupon.objects.all().order_by('-created_at')
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset
    
    @extend_schema(
        parameters=[OpenApiParameter('is_active', bool)],
        tags=['Marketing - Admin']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminCouponDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Get/Update/Delete coupon."""
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CouponSerializer
    queryset = Coupon.objects.all()
    
    @extend_schema(tags=['Marketing - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(tags=['Marketing - Admin'])
    def patch(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(tags=['Marketing - Admin'])
    def delete(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class AdminBannerListView(generics.ListAPIView):
    """Admin: List all banners."""
    permission_classes = [permissions.IsAdminUser]
    serializer_class = BannerSerializer
    
    def get_queryset(self):
        return Banner.objects.all().order_by('-created_at')
    
    @extend_schema(tags=['Marketing - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminFlashSaleListView(generics.ListAPIView):
    """Admin: List all flash sales."""
    permission_classes = [permissions.IsAdminUser]
    serializer_class = FlashSaleSerializer
    
    def get_queryset(self):
        return FlashSale.objects.prefetch_related('items__product').order_by('-start_time')
    
    @extend_schema(tags=['Marketing - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminCampaignListView(generics.ListAPIView):
    """Admin: List all campaigns."""
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CampaignListSerializer
    
    def get_queryset(self):
        return Campaign.objects.all().order_by('-created_at')
    
    @extend_schema(tags=['Marketing - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminCampaignDetailView(generics.RetrieveAPIView):
    """Admin: Get campaign details with stats."""
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CampaignSerializer
    queryset = Campaign.objects.all()
    
    @extend_schema(tags=['Marketing - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminStatisticsView(APIView):
    """Admin: Marketing statistics dashboard."""
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        responses={200: MarketingStatisticsSerializer},
        tags=['Marketing - Admin']
    )
    def get(self, request):
        stats = MarketingService.get_statistics()
        return Response(stats)
