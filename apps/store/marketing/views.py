"""Store Marketing - API Views."""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Coupon, Banner, FlashSale, Campaign
from .serializers import (
    CouponSerializer, CouponValidateSerializer, CouponValidateResponseSerializer,
    BannerSerializer, FlashSaleSerializer, FlashSaleListSerializer, FlashSaleItemSerializer,
    CampaignSerializer, MarketingStatisticsSerializer
)
from .services import CouponService, BannerService, FlashSaleService, CampaignService, MarketingService


class PublicCouponsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CouponSerializer

    def get_queryset(self):
        return CouponService.get_public_coupons()

    @extend_schema(tags=['Marketing'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserCouponsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        return CouponService.get_user_coupons(self.request.user)

    @extend_schema(tags=['Marketing'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ValidateCouponView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=CouponValidateSerializer, responses={200: CouponValidateResponseSerializer}, tags=['Marketing'])
    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = CouponService.validate_coupon(data['code'], request.user, data['order_total'])
            return Response({'valid': True, 'discount': result['discount'], 'discount_display': result['discount_display'], 'message': ''})
        except DomainException as e:
            return Response({'valid': False, 'discount': 0, 'discount_display': '', 'message': str(e.message)})


class BannersView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BannerSerializer

    def get_queryset(self):
        position = self.request.query_params.get('position')
        category_id = self.request.query_params.get('category_id')
        return BannerService.get_active_banners(position, category_id)

    @extend_schema(parameters=[OpenApiParameter('position', str), OpenApiParameter('category_id', str)], tags=['Marketing'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BannerClickView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Marketing'])
    def post(self, request, banner_id):
        BannerService.track_click(banner_id)
        return Response({'success': True})


class FlashSalesView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = FlashSaleListSerializer

    def get_queryset(self):
        return FlashSaleService.get_active_flash_sales()

    @extend_schema(tags=['Marketing'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class FlashSaleDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: FlashSaleSerializer}, tags=['Marketing'])
    def get(self, request, flash_sale_id):
        try:
            flash_sale = FlashSaleService.get_flash_sale(flash_sale_id)
            return Response(FlashSaleSerializer(flash_sale).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class UpcomingFlashSalesView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = FlashSaleListSerializer

    def get_queryset(self):
        return FlashSaleService.get_upcoming_flash_sales()

    @extend_schema(tags=['Marketing'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CheckFlashPriceView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(parameters=[OpenApiParameter('product_id', str)], responses={200: FlashSaleItemSerializer}, tags=['Marketing'])
    def get(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': 'product_id required'}, status=status.HTTP_400_BAD_REQUEST)
        item = FlashSaleService.get_flash_sale_item(product_id)
        if item:
            return Response(FlashSaleItemSerializer(item).data)
        return Response({'flash_sale': None})


class AdminCampaignsView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = CampaignSerializer

    def get_queryset(self):
        queryset = Campaign.objects.all()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by('-created_at')

    @extend_schema(parameters=[OpenApiParameter('status', str)], tags=['Marketing - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminCampaignDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: CampaignSerializer}, tags=['Marketing - Admin'])
    def get(self, request, campaign_id):
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            return Response(CampaignSerializer(campaign).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminStatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: MarketingStatisticsSerializer}, tags=['Marketing - Admin'])
    def get(self, request):
        stats = MarketingService.get_statistics()
        return Response(stats)
