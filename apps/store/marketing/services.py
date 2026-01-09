"""Store Marketing - Application Services."""
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Sum, Q

from apps.common.core.exceptions import NotFoundError, BusinessRuleViolation
from .models import Coupon, CouponUsage, Banner, FlashSale, FlashSaleItem, Campaign

logger = logging.getLogger('apps.marketing')


class CouponService:
    @staticmethod
    def get_coupon(code: str) -> Coupon:
        try:
            return Coupon.objects.get(code__iexact=code.strip())
        except Coupon.DoesNotExist:
            raise NotFoundError(message='Coupon not found')

    @staticmethod
    def validate_coupon(code: str, user, order_total: Decimal) -> Dict[str, Any]:
        coupon = CouponService.get_coupon(code)
        can_use, reason = coupon.can_use(user, order_total)
        if not can_use:
            raise BusinessRuleViolation(message=reason)
        discount = coupon.calculate_discount(order_total)
        return {'coupon': coupon, 'discount': discount, 'discount_display': coupon.get_discount_display()}

    @staticmethod
    def apply_coupon(code: str, user, order_id: UUID, order_total: Decimal) -> CouponUsage:
        result = CouponService.validate_coupon(code, user, order_total)
        coupon = result['coupon']
        usage = coupon.use(user=user, order_id=order_id)
        usage.discount_amount = result['discount']
        usage.save(update_fields=['discount_amount'])
        logger.info(f"Coupon {code} applied to order {order_id}")
        return usage

    @staticmethod
    def get_public_coupons() -> List[Coupon]:
        now = timezone.now()
        return list(Coupon.objects.filter(is_active=True, is_public=True, valid_from__lte=now, valid_until__gte=now).order_by('-created_at'))

    @staticmethod
    def get_user_coupons(user) -> List[Coupon]:
        now = timezone.now()
        return list(Coupon.objects.filter(Q(is_active=True, valid_from__lte=now, valid_until__gte=now) & (Q(is_public=True) | Q(specific_users=user))).distinct().order_by('-created_at'))


class BannerService:
    @staticmethod
    def get_active_banners(position: str = None, category_id: UUID = None) -> List[Banner]:
        now = timezone.now()
        queryset = Banner.objects.filter(is_active=True)
        queryset = queryset.filter(Q(start_date__isnull=True) | Q(start_date__lte=now))
        queryset = queryset.filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
        if position:
            queryset = queryset.filter(position=position)
        if category_id:
            queryset = queryset.filter(Q(category_id=category_id) | Q(category__isnull=True))
        return list(queryset.order_by('sort_order'))

    @staticmethod
    def track_view(banner_id: int) -> None:
        Banner.objects.filter(pk=banner_id).update(view_count=models.F('view_count') + 1)

    @staticmethod
    def track_click(banner_id: int) -> None:
        Banner.objects.filter(pk=banner_id).update(click_count=models.F('click_count') + 1)


class FlashSaleService:
    @staticmethod
    def get_active_flash_sales() -> List[FlashSale]:
        now = timezone.now()
        return list(FlashSale.objects.filter(is_active=True, start_time__lte=now, end_time__gte=now).prefetch_related('items__product').order_by('end_time'))

    @staticmethod
    def get_upcoming_flash_sales() -> List[FlashSale]:
        now = timezone.now()
        return list(FlashSale.objects.filter(is_active=True, start_time__gt=now).order_by('start_time')[:5])

    @staticmethod
    def get_flash_sale(flash_sale_id: UUID) -> FlashSale:
        try:
            return FlashSale.objects.prefetch_related('items__product').get(id=flash_sale_id)
        except FlashSale.DoesNotExist:
            raise NotFoundError(message='Flash sale not found')

    @staticmethod
    def get_flash_sale_item(product_id: UUID) -> Optional[FlashSaleItem]:
        now = timezone.now()
        return FlashSaleItem.objects.filter(product_id=product_id, flash_sale__is_active=True, flash_sale__start_time__lte=now, flash_sale__end_time__gte=now, is_active=True).select_related('flash_sale').first()

    @staticmethod
    @transaction.atomic
    def purchase_flash_item(item_id: int, quantity: int = 1) -> bool:
        item = FlashSaleItem.objects.select_for_update().get(pk=item_id)
        if item.is_sold_out:
            return False
        if item.quantity_limit > 0 and item.quantity_sold + quantity > item.quantity_limit:
            return False
        item.purchase(quantity)
        return True


class CampaignService:
    @staticmethod
    def get_campaign(campaign_id: UUID) -> Campaign:
        try:
            return Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            raise NotFoundError(message='Campaign not found')

    @staticmethod
    def get_active_campaigns() -> List[Campaign]:
        return list(Campaign.objects.filter(status=Campaign.Status.ACTIVE).order_by('-created_at'))

    @staticmethod
    def track_open(campaign_id: UUID) -> None:
        Campaign.objects.filter(pk=campaign_id).update(open_count=models.F('open_count') + 1)

    @staticmethod
    def track_click(campaign_id: UUID) -> None:
        Campaign.objects.filter(pk=campaign_id).update(click_count=models.F('click_count') + 1)

    @staticmethod
    def track_conversion(campaign_id: UUID, revenue: Decimal = 0) -> None:
        Campaign.objects.filter(pk=campaign_id).update(conversion_count=models.F('conversion_count') + 1, revenue=models.F('revenue') + revenue)


class MarketingService:
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)
        return {
            'active_coupons': Coupon.objects.filter(is_active=True, valid_from__lte=now, valid_until__gte=now).count(),
            'total_coupon_usages': CouponUsage.objects.filter(created_at__gte=thirty_days_ago).count(),
            'active_banners': Banner.objects.filter(is_active=True).count(),
            'active_flash_sales': FlashSale.objects.filter(is_active=True, start_time__lte=now, end_time__gte=now).count(),
            'active_campaigns': Campaign.objects.filter(status=Campaign.Status.ACTIVE).count(),
            'total_campaign_conversions': Campaign.objects.filter(created_at__gte=thirty_days_ago).aggregate(total=Sum('conversion_count'))['total'] or 0,
        }
