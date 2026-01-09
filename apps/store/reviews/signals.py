"""Store Reviews - Signal Handlers.

Review moderation and product rating updates.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg, Count
from django.core.cache import cache

logger = logging.getLogger('apps.reviews.signals')


@receiver(post_save, sender='reviews.Review')
def on_review_saved(sender, instance, created, **kwargs):
    """Handle review creation and approval."""
    try:
        if created:
            logger.debug(f"New review created for product {instance.product_id}")
            # Notify admin about new review pending approval
            if not instance.is_approved:
                _notify_admin_new_review(instance)
            return
        
        update_fields = kwargs.get('update_fields') or []
        
        # When review is approved, update product ratings
        if 'is_approved' in update_fields and instance.is_approved:
            _update_product_rating(instance.product_id)
            # Notify reviewer
            _send_review_notification(instance, 'review_approved')
            
    except Exception as e:
        logger.warning(f"Error processing review signal: {e}")


@receiver(post_delete, sender='reviews.Review')
def on_review_deleted(sender, instance, **kwargs):
    """Update product rating when review is deleted."""
    try:
        if instance.is_approved:
            _update_product_rating(instance.product_id)
    except Exception as e:
        logger.warning(f"Error processing review deletion: {e}")


@receiver(post_save, sender='reviews.ReviewReply')
def on_review_reply_saved(sender, instance, created, **kwargs):
    """Notify user when their review gets a reply."""
    if not created:
        return
    
    try:
        if instance.review.user:
            _send_review_notification(instance.review, 'review_replied')
    except Exception as e:
        logger.warning(f"Error processing review reply signal: {e}")


@receiver(post_save, sender='reviews.ReviewVote')
def on_review_vote_saved(sender, instance, created, **kwargs):
    """Update review helpful count."""
    if not created:
        return
    
    try:
        review = instance.review
        helpful_count = review.votes.filter(is_helpful=True).count()
        review.helpful_count = helpful_count
        review.save(update_fields=['helpful_count', 'updated_at'])
    except Exception as e:
        logger.warning(f"Error processing review vote: {e}")


def _update_product_rating(product_id):
    """Recalculate product average rating."""
    try:
        from .models import Review, ReviewSummary
        
        # Calculate new averages
        stats = Review.objects.filter(
            product_id=product_id,
            is_approved=True
        ).aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        
        # Update or create review summary
        summary, _ = ReviewSummary.objects.get_or_create(product_id=product_id)
        summary.average_rating = stats['avg_rating'] or 0
        summary.total_reviews = stats['count'] or 0
        summary.save(update_fields=['average_rating', 'total_reviews', 'updated_at'])
        
        # Invalidate cache
        cache.delete(f'product:{product_id}:rating')
        cache.delete(f'product:{product_id}:reviews')
        
        logger.debug(f"Product {product_id} rating updated: {summary.average_rating:.1f} ({summary.total_reviews} reviews)")
        
    except Exception as e:
        logger.warning(f"Error updating product rating: {e}")


def _notify_admin_new_review(review):
    """Notify admins about new review pending approval."""
    try:
        from apps.users.identity.models import User
        from apps.users.notifications.services import NotificationService
        
        admins = User.objects.filter(is_staff=True, is_active=True)[:3]
        for admin in admins:
            NotificationService.create(
                user=admin,
                notification_type='review_pending',
                title='New Review Pending',
                message=f"New {review.rating}-star review needs approval.",
                data={
                    'review_id': review.id,
                    'product_id': str(review.product_id),
                    'rating': review.rating,
                }
            )
    except Exception as e:
        logger.debug(f"Could not notify admins: {e}")


def _send_review_notification(review, notification_type):
    """Send review notification to user."""
    if not review.user:
        return
    
    try:
        from apps.users.notifications.services import NotificationService
        
        messages = {
            'review_approved': 'Your review has been approved and is now visible.',
            'review_replied': 'The seller replied to your review.',
        }
        
        NotificationService.create(
            user=review.user,
            notification_type=notification_type,
            title='Review Update',
            message=messages.get(notification_type, 'Your review has been updated.'),
            data={
                'review_id': review.id,
                'product_id': str(review.product_id),
            }
        )
    except Exception as e:
        logger.debug(f"Could not send review notification: {e}")
