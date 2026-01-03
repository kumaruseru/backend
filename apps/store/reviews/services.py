"""
Store Reviews - Application Services.
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.common.core.exceptions import NotFoundError, ValidationError, BusinessRuleViolation
from .models import Review, ReviewImage, ReviewReply, ReviewVote, ReviewReport, ReviewSummary

logger = logging.getLogger('apps.reviews')


class ReviewService:
    """Review management service."""
    
    @staticmethod
    def get_product_reviews(
        product_id: UUID,
        rating: int = None,
        verified_only: bool = False,
        with_images: bool = False,
        sort: str = 'recent',
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get reviews for a product with filters.
        """
        queryset = Review.objects.filter(
            product_id=product_id,
            is_approved=True
        ).select_related('user').prefetch_related('images', 'replies')
        
        # Filters
        if rating:
            queryset = queryset.filter(rating=rating)
        if verified_only:
            queryset = queryset.filter(is_verified_purchase=True)
        if with_images:
            queryset = queryset.filter(images__isnull=False).distinct()
        
        # Sorting
        if sort == 'helpful':
            queryset = queryset.order_by('-helpful_count', '-created_at')
        elif sort == 'rating_high':
            queryset = queryset.order_by('-rating', '-created_at')
        elif sort == 'rating_low':
            queryset = queryset.order_by('rating', '-created_at')
        else:  # recent
            queryset = queryset.order_by('-created_at')
        
        total = queryset.count()
        reviews = list(queryset[offset:offset + limit])
        
        return {
            'reviews': reviews,
            'total': total,
            'has_more': total > offset + limit
        }
    
    @staticmethod
    def get_review_summary(product_id: UUID) -> ReviewSummary:
        """Get or create review summary for a product."""
        summary, created = ReviewSummary.objects.get_or_create(product_id=product_id)
        
        if created:
            summary.refresh()
        
        return summary
    
    @staticmethod
    @transaction.atomic
    def create_review(
        user,
        product_id: UUID,
        rating: int,
        comment: str,
        title: str = '',
        order_id=None,
        quality_rating: int = None,
        value_rating: int = None,
        delivery_rating: int = None,
        images: list = None
    ) -> Review:
        """
        Create a new review.
        """
        # Check if already reviewed
        if Review.objects.filter(user=user, product_id=product_id).exists():
            raise BusinessRuleViolation(message='Bạn đã đánh giá sản phẩm này rồi')
        
        review = Review.objects.create(
            user=user,
            product_id=product_id,
            order_id=order_id,
            rating=rating,
            title=title,
            comment=comment,
            quality_rating=quality_rating,
            value_rating=value_rating,
            delivery_rating=delivery_rating,
            is_approved=False  # Pending moderation
        )
        
        # Add images
        if images:
            for i, img in enumerate(images[:5]):  # Max 5 images
                ReviewImage.objects.create(
                    review=review,
                    image=img,
                    sort_order=i
                )
        
        logger.info(f"Review created: {review.id} for product {product_id}")
        
        # Refresh summary
        ReviewService._refresh_summary(product_id)
        
        return review
    
    @staticmethod
    @transaction.atomic
    def update_review(
        review: Review,
        rating: int = None,
        title: str = None,
        comment: str = None,
        **kwargs
    ) -> Review:
        """Update an existing review."""
        if rating is not None:
            review.rating = rating
        if title is not None:
            review.title = title
        if comment is not None:
            review.comment = comment
        
        for key, value in kwargs.items():
            if hasattr(review, key) and value is not None:
                setattr(review, key, value)
        
        # Reset moderation if content changed
        if any([rating, title, comment]):
            review.is_approved = False
            review.is_rejected = False
        
        review.save()
        
        ReviewService._refresh_summary(review.product_id)
        
        return review
    
    @staticmethod
    def delete_review(review: Review) -> None:
        """Delete a review."""
        product_id = review.product_id
        review.delete()
        ReviewService._refresh_summary(product_id)
    
    # --- Moderation ---
    
    @staticmethod
    def get_pending_reviews(limit: int = 50) -> List[Review]:
        """Get pending reviews for moderation."""
        return list(
            Review.objects.filter(is_approved=False, is_rejected=False)
            .select_related('user', 'product')
            .prefetch_related('images', 'reports')
            .order_by('created_at')[:limit]
        )
    
    @staticmethod
    @transaction.atomic
    def approve_review(review: Review, moderator=None) -> Review:
        """Approve a review."""
        review.approve(moderator)
        ReviewService._refresh_summary(review.product_id)
        
        logger.info(f"Review {review.id} approved by {moderator}")
        
        return review
    
    @staticmethod
    @transaction.atomic
    def reject_review(review: Review, reason: str, moderator=None) -> Review:
        """Reject a review."""
        review.reject(reason, moderator)
        ReviewService._refresh_summary(review.product_id)
        
        logger.info(f"Review {review.id} rejected by {moderator}: {reason}")
        
        return review
    
    @staticmethod
    @transaction.atomic
    def bulk_moderate(review_ids: list, action: str, moderator=None, reason: str = '') -> int:
        """Bulk moderate reviews."""
        reviews = Review.objects.filter(id__in=review_ids)
        count = 0
        
        for review in reviews:
            if action == 'approve':
                review.approve(moderator)
            elif action == 'reject':
                review.reject(reason, moderator)
            count += 1
            ReviewService._refresh_summary(review.product_id)
        
        return count
    
    # --- Replies ---
    
    @staticmethod
    def add_reply(review: Review, user, content: str, is_official: bool = False) -> ReviewReply:
        """Add a reply to a review."""
        reply = ReviewReply.objects.create(
            review=review,
            user=user,
            content=content,
            is_official=is_official
        )
        
        logger.info(f"Reply added to review {review.id}")
        
        return reply
    
    # --- Votes ---
    
    @staticmethod
    def vote_review(review: Review, user, is_helpful: bool) -> ReviewVote:
        """Vote on a review."""
        if review.user == user:
            raise BusinessRuleViolation(message='Không thể vote đánh giá của chính mình')
        
        return review.vote_helpful(user, is_helpful)
    
    # --- Reports ---
    
    @staticmethod
    def report_review(review: Review, reporter, reason: str, details: str = '') -> ReviewReport:
        """Report a review."""
        if review.user == reporter:
            raise BusinessRuleViolation(message='Không thể báo cáo đánh giá của chính mình')
        
        # Check if already reported
        if ReviewReport.objects.filter(review=review, reporter=reporter).exists():
            raise BusinessRuleViolation(message='Bạn đã báo cáo đánh giá này rồi')
        
        report = ReviewReport.objects.create(
            review=review,
            reporter=reporter,
            reason=reason,
            details=details
        )
        
        logger.info(f"Review {review.id} reported by {reporter}")
        
        return report
    
    @staticmethod
    def get_pending_reports(limit: int = 50) -> List[ReviewReport]:
        """Get pending reports."""
        return list(
            ReviewReport.objects.filter(status='pending')
            .select_related('review__user', 'review__product', 'reporter')
            .order_by('created_at')[:limit]
        )
    
    @staticmethod
    def resolve_report(report: ReviewReport, action: str, handler=None, notes: str = '') -> ReviewReport:
        """Resolve a report."""
        report.resolve(action, handler, notes)
        return report
    
    # --- User Reviews ---
    
    @staticmethod
    def get_user_reviews(user, limit: int = 20) -> List[Review]:
        """Get reviews by a user."""
        return list(
            Review.objects.filter(user=user)
            .select_related('product')
            .prefetch_related('images')
            .order_by('-created_at')[:limit]
        )
    
    @staticmethod
    def get_reviewable_products(user, limit: int = 10) -> list:
        """Get products user can review (purchased but not reviewed)."""
        from apps.commerce.orders.models import OrderItem
        from apps.store.catalog.models import Product
        
        # Products user has purchased
        purchased = OrderItem.objects.filter(
            order__user=user,
            order__status='delivered'
        ).values_list('product_id', flat=True).distinct()
        
        # Products already reviewed
        reviewed = Review.objects.filter(user=user).values_list('product_id', flat=True)
        
        # Products that can be reviewed
        reviewable_ids = set(purchased) - set(reviewed)
        
        return list(
            Product.objects.filter(id__in=reviewable_ids)
            .select_related('category', 'brand')[:limit]
        )
    
    # --- Statistics ---
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get review statistics."""
        today = timezone.now().date()
        
        total = Review.objects.count()
        pending = Review.objects.filter(is_approved=False, is_rejected=False).count()
        approved = Review.objects.filter(is_approved=True).count()
        rejected = Review.objects.filter(is_rejected=True).count()
        
        avg = Review.objects.filter(is_approved=True).aggregate(avg=Avg('rating'))
        
        today_count = Review.objects.filter(created_at__date=today).count()
        pending_reports = ReviewReport.objects.filter(status='pending').count()
        
        return {
            'total_reviews': total,
            'pending_reviews': pending,
            'approved_reviews': approved,
            'rejected_reviews': rejected,
            'average_rating': avg['avg'] or 0,
            'reviews_today': today_count,
            'pending_reports': pending_reports
        }
    
    # --- Helpers ---
    
    @staticmethod
    def _refresh_summary(product_id: UUID):
        """Refresh review summary for a product."""
        summary, _ = ReviewSummary.objects.get_or_create(product_id=product_id)
        summary.refresh()
