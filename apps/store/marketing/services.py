"""
Store Marketing - Application Services.
"""
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone

from apps.common.core.exceptions import NotFoundError, ValidationError, BusinessRuleViolation
from .models import Coupon, CouponUsage, Banner, FlashSale, FlashSaleItem, Campaign

logger = logging.getLogger('apps.marketing')


class CouponService:
    """Coupon management service."""
    
    @staticmethod
    def get_coupon(code: str) -> Coupon:
        """Get coupon by code."""
        try:
            return Coupon.objects.get(code__iexact=code.strip())
        except Coupon.DoesNotExist:
            raise NotFoundError(code='COUPON_NOT_FOUND', message='Mã giảm giá không tồn tại')
    
    @staticmethod
    def validate_coupon(code: str, user, order_total: Decimal) -> Dict[str, Any]:
        """
        Validate a coupon for an order.
        
        Returns dict with valid, discount_amount, message, coupon.
        """
        try:
            coupon = CouponService.get_coupon(code)
        except NotFoundError:
            return {
                'valid': False,
                'discount_amount': Decimal('0'),
                'message': 'Mã giảm giá không tồn tại',
                'coupon': None
            }
        
        can_use, reason = coupon.can_use(user, order_total)
        
        if not can_use:
            return {
                'valid': False,
                'discount_amount': Decimal('0'),
                'message': reason,
                'coupon': None
            }
        
        discount = coupon.calculate_discount(order_total)
        
        return {
            'valid': True,
            'discount_amount': discount,
            'message': f'Giảm {discount:,.0f}₫',
            'coupon': coupon
        }
    
    @staticmethod
    @transaction.atomic
    def use_coupon(coupon: Coupon, user, order_id, discount_amount: Decimal) -> CouponUsage:
        """Use a coupon for an order."""
        usage = coupon.use(user, order_id)
        usage.discount_amount = discount_amount
        usage.save(update_fields=['discount_amount'])
        
        logger.info(f"Coupon {coupon.code} used for order {order_id}")
        
        return usage
    
    @staticmethod
    def get_available_coupons(user=None) -> List[Coupon]:
        """Get available public coupons."""
        now = timezone.now()
        
        queryset = Coupon.objects.filter(
            is_active=True,
            is_public=True,
            valid_from__lte=now,
            valid_until__gte=now
        ).filter(
            Q(usage_limit__isnull=True) |
            Q(used_count__lt=F('usage_limit'))
        )
        
        if user and user.is_authenticated:
            # Also include exclusive coupons for this user
            exclusive = Coupon.objects.filter(
                specific_users=user,
                is_active=True,
                valid_from__lte=now,
                valid_until__gte=now
            )
            queryset = queryset | exclusive
        
        return list(queryset.distinct().order_by('-created_at'))
    
    @staticmethod
    def get_user_coupon_history(user, limit: int = 20) -> List[CouponUsage]:
        """Get user's coupon usage history."""
        return list(
            CouponUsage.objects.filter(user=user)
            .select_related('coupon')
            .order_by('-created_at')[:limit]
        )


class BannerService:
    """Banner management service."""
    
    @staticmethod
    def get_active_banners(position: str = None, category_id: int = None) -> List[Banner]:
        """Get active banners for display."""
        now = timezone.now()
        
        queryset = Banner.objects.filter(is_active=True).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        
        if position:
            queryset = queryset.filter(position=position)
        
        if category_id:
            queryset = queryset.filter(
                Q(category_id=category_id) | Q(category__isnull=True)
            )
        
        return list(queryset.order_by('sort_order'))
    
    @staticmethod
    def track_view(banner_id: int) -> None:
        """Track banner view."""
        Banner.objects.filter(id=banner_id).update(view_count=F('view_count') + 1)
    
    @staticmethod
    def track_click(banner_id: int) -> None:
        """Track banner click."""
        Banner.objects.filter(id=banner_id).update(click_count=F('click_count') + 1)


class FlashSaleService:
    """Flash sale management service."""
    
    @staticmethod
    def get_active_flash_sale() -> Optional[FlashSale]:
        """Get currently active flash sale."""
        now = timezone.now()
        
        sale = FlashSale.objects.filter(
            is_active=True,
            start_time__lte=now,
            end_time__gte=now
        ).prefetch_related(
            'items__product'
        ).first()
        
        if sale:
            sale.update_status()
        
        return sale
    
    @staticmethod
    def get_upcoming_flash_sales(limit: int = 5) -> List[FlashSale]:
        """Get upcoming flash sales."""
        now = timezone.now()
        
        return list(
            FlashSale.objects.filter(
                is_active=True,
                start_time__gt=now
            ).order_by('start_time')[:limit]
        )
    
    @staticmethod
    def get_flash_sale_by_id(sale_id) -> FlashSale:
        """Get flash sale by ID."""
        try:
            sale = FlashSale.objects.prefetch_related('items__product').get(id=sale_id)
            sale.update_status()
            return sale
        except FlashSale.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy Flash Sale')
    
    @staticmethod
    def get_flash_price(product_id) -> Optional[Dict[str, Any]]:
        """Get flash sale price for a product if applicable."""
        now = timezone.now()
        
        item = FlashSaleItem.objects.filter(
            is_active=True,
            product_id=product_id,
            flash_sale__is_active=True,
            flash_sale__start_time__lte=now,
            flash_sale__end_time__gte=now
        ).select_related('flash_sale').first()
        
        if item and not item.is_sold_out:
            return {
                'flash_price': item.flash_price,
                'original_price': item.original_price,
                'discount_percentage': item.discount_percentage,
                'remaining_quantity': item.remaining_quantity,
                'flash_sale_id': str(item.flash_sale.id),
                'flash_sale_name': item.flash_sale.name,
                'ends_at': item.flash_sale.end_time
            }
        
        return None
    
    @staticmethod
    @transaction.atomic
    def record_purchase(product_id, quantity: int = 1) -> None:
        """Record flash sale purchase."""
        now = timezone.now()
        
        FlashSaleItem.objects.filter(
            product_id=product_id,
            is_active=True,
            flash_sale__is_active=True,
            flash_sale__start_time__lte=now,
            flash_sale__end_time__gte=now
        ).update(quantity_sold=F('quantity_sold') + quantity)


class CampaignService:
    """Campaign management service."""
    
    @staticmethod
    def get_active_campaigns() -> List[Campaign]:
        """Get active campaigns."""
        return list(
            Campaign.objects.filter(status=Campaign.Status.ACTIVE)
            .order_by('-created_at')
        )
    
    @staticmethod
    def record_event(campaign_id, event_type: str, revenue: Decimal = 0) -> None:
        """Record campaign event."""
        update_fields = {}
        
        if event_type == 'send':
            update_fields['sent_count'] = F('sent_count') + 1
        elif event_type == 'open':
            update_fields['open_count'] = F('open_count') + 1
        elif event_type == 'click':
            update_fields['click_count'] = F('click_count') + 1
        elif event_type == 'conversion':
            update_fields['conversion_count'] = F('conversion_count') + 1
            update_fields['revenue'] = F('revenue') + revenue
        
        if update_fields:
            Campaign.objects.filter(id=campaign_id).update(**update_fields)


class MarketingService:
    """Combined marketing statistics service."""
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get marketing dashboard statistics."""
        now = timezone.now()
        
        active_coupons = Coupon.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        ).count()
        
        coupon_stats = CouponUsage.objects.aggregate(
            total_uses=Count('id'),
            total_discount=Sum('discount_amount')
        )
        
        active_banners = Banner.objects.filter(
            is_active=True
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).count()
        
        active_flash_sales = FlashSale.objects.filter(
            is_active=True,
            start_time__lte=now,
            end_time__gte=now
        ).count()
        
        active_campaigns = Campaign.objects.filter(
            status=Campaign.Status.ACTIVE
        ).count()
        
        return {
            'active_coupons': active_coupons,
            'total_coupon_uses': coupon_stats['total_uses'] or 0,
            'total_discount_given': coupon_stats['total_discount'] or Decimal('0'),
            'active_banners': active_banners,
            'active_flash_sales': active_flash_sales,
            'active_campaigns': active_campaigns
        }
