"""
Store Reviews - Production-Ready Models.

Comprehensive review system with:
- Review: Product reviews with ratings, images
- ReviewImage: Photo attachments
- ReviewReply: Seller/Admin responses
- ReviewVote: Helpful votes
- ReviewReport: Abuse reporting
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Avg, Count, Sum

from apps.common.core.models import TimeStampedModel, UUIDModel
from apps.common.core.storage import review_image_path


class ReviewManager(models.Manager):
    """Manager for reviews."""
    
    def approved(self):
        """Get approved reviews only."""
        return self.filter(is_approved=True)
    
    def pending(self):
        """Get pending reviews."""
        return self.filter(is_approved=False, is_rejected=False)
    
    def with_images(self):
        """Get reviews with images."""
        return self.filter(images__isnull=False).distinct()
    
    def verified_only(self):
        """Get verified purchase reviews only."""
        return self.filter(is_verified_purchase=True)


class Review(UUIDModel):
    """
    Product review with comprehensive features.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Người dùng'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Sản phẩm'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name='Đơn hàng'
    )
    
    # Rating and content
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_index=True,
        verbose_name='Đánh giá'
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Tiêu đề'
    )
    comment = models.TextField(verbose_name='Nhận xét')
    
    # Detailed ratings (optional)
    quality_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        verbose_name='Chất lượng'
    )
    value_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        verbose_name='Giá trị'
    )
    delivery_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        verbose_name='Giao hàng'
    )
    
    # Verification
    is_verified_purchase = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Đã mua hàng'
    )
    
    # Moderation
    is_approved = models.BooleanField(default=False, db_index=True, verbose_name='Đã duyệt')
    is_rejected = models.BooleanField(default=False, verbose_name='Bị từ chối')
    rejection_reason = models.TextField(blank=True, verbose_name='Lý do từ chối')
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='moderated_reviews',
        verbose_name='Người duyệt'
    )
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name='Duyệt lúc')
    
    # Engagement
    helpful_count = models.PositiveIntegerField(default=0, verbose_name='Hữu ích')
    not_helpful_count = models.PositiveIntegerField(default=0, verbose_name='Không hữu ích')
    
    # Featured
    is_featured = models.BooleanField(default=False, verbose_name='Nổi bật')
    is_pinned = models.BooleanField(default=False, verbose_name='Ghim')
    
    objects = ReviewManager()
    
    class Meta:
        verbose_name = 'Đánh giá'
        verbose_name_plural = 'Đánh giá'
        ordering = ['-created_at']
        unique_together = ['user', 'product']
        indexes = [
            models.Index(fields=['product', 'is_approved', '-created_at']),
            models.Index(fields=['product', 'rating']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.product.name}: {self.rating}★"
    
    def save(self, *args, **kwargs):
        # Auto-verify purchase
        if not self.is_verified_purchase and self.user_id and self.product_id:
            self._check_verified_purchase()
        
        super().save(*args, **kwargs)
        
        # Update product average rating
        self._update_product_rating()
    
    def _check_verified_purchase(self):
        """Check if user has purchased this product."""
        from apps.commerce.orders.models import OrderItem
        
        order_query = OrderItem.objects.filter(
            order__user=self.user,
            product=self.product,
            order__status='delivered'
        )
        
        if order_query.exists():
            self.is_verified_purchase = True
            # Link to the order
            if not self.order_id:
                self.order = order_query.first().order
    
    def _update_product_rating(self):
        """Update product's average rating and review count."""
        from apps.store.catalog.models import Product
        
        stats = Review.objects.filter(
            product=self.product,
            is_approved=True
        ).aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        
        Product.objects.filter(id=self.product_id).update(
            average_rating=stats['avg_rating'] or 0,
            review_count=stats['count']
        )
    
    # Properties
    
    @property
    def user_display_name(self) -> str:
        """Get user display name."""
        if self.user.get_full_name():
            name = self.user.get_full_name()
            # Mask last name
            parts = name.split()
            if len(parts) > 1:
                return f"{parts[0]} {parts[-1][0]}."
            return parts[0]
        return self.user.email.split('@')[0]
    
    @property
    def has_images(self) -> bool:
        """Check if review has images."""
        return self.images.exists()
    
    @property
    def helpfulness_score(self) -> int:
        """Net helpfulness score."""
        return self.helpful_count - self.not_helpful_count
    
    @property
    def helpfulness_percentage(self) -> int:
        """Percentage of helpful votes."""
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 0
        return int((self.helpful_count / total) * 100)
    
    # Actions
    
    def approve(self, moderator=None):
        """Approve the review."""
        self.is_approved = True
        self.is_rejected = False
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=['is_approved', 'is_rejected', 'moderated_by', 'moderated_at', 'updated_at'])
    
    def reject(self, reason: str, moderator=None):
        """Reject the review."""
        self.is_approved = False
        self.is_rejected = True
        self.rejection_reason = reason
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=['is_approved', 'is_rejected', 'rejection_reason', 'moderated_by', 'moderated_at', 'updated_at'])
    
    def vote_helpful(self, user, is_helpful: bool = True):
        """Record a helpful vote."""
        vote, created = ReviewVote.objects.update_or_create(
            review=self,
            user=user,
            defaults={'is_helpful': is_helpful}
        )
        
        # Update counts
        stats = self.votes.aggregate(
            helpful=Count('id', filter=models.Q(is_helpful=True)),
            not_helpful=Count('id', filter=models.Q(is_helpful=False))
        )
        
        self.helpful_count = stats['helpful']
        self.not_helpful_count = stats['not_helpful']
        self.save(update_fields=['helpful_count', 'not_helpful_count', 'updated_at'])
        
        return vote


class ReviewImage(TimeStampedModel):
    """
    Image attachment for reviews.
    """
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Đánh giá'
    )
    image = models.ImageField(
        upload_to=review_image_path,
        verbose_name='Hình ảnh'
    )
    caption = models.CharField(max_length=200, blank=True, verbose_name='Chú thích')
    sort_order = models.PositiveSmallIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Hình ảnh đánh giá'
        verbose_name_plural = 'Hình ảnh đánh giá'
        ordering = ['sort_order']
    
    def __str__(self) -> str:
        return f"Image for {self.review}"


class ReviewReply(TimeStampedModel):
    """
    Seller/Admin reply to a review.
    """
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name='Đánh giá'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_replies',
        verbose_name='Người trả lời'
    )
    content = models.TextField(verbose_name='Nội dung')
    is_official = models.BooleanField(default=False, verbose_name='Phản hồi chính thức')
    
    class Meta:
        verbose_name = 'Phản hồi đánh giá'
        verbose_name_plural = 'Phản hồi đánh giá'
        ordering = ['created_at']
    
    def __str__(self) -> str:
        return f"Reply to {self.review}"


class ReviewVote(TimeStampedModel):
    """
    Helpful/Not helpful vote on a review.
    """
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name='Đánh giá'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_votes',
        verbose_name='Người vote'
    )
    is_helpful = models.BooleanField(verbose_name='Hữu ích')
    
    class Meta:
        verbose_name = 'Vote đánh giá'
        verbose_name_plural = 'Vote đánh giá'
        unique_together = ['review', 'user']
    
    def __str__(self) -> str:
        vote_type = "Helpful" if self.is_helpful else "Not helpful"
        return f"{vote_type} vote on {self.review}"


class ReviewReport(TimeStampedModel):
    """
    Report abusive/inappropriate reviews.
    """
    
    class Reason(models.TextChoices):
        SPAM = 'spam', 'Spam'
        OFFENSIVE = 'offensive', 'Ngôn từ xúc phạm'
        FAKE = 'fake', 'Đánh giá giả'
        IRRELEVANT = 'irrelevant', 'Không liên quan'
        OTHER = 'other', 'Lý do khác'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ xử lý'
        REVIEWED = 'reviewed', 'Đã xem xét'
        RESOLVED = 'resolved', 'Đã xử lý'
        DISMISSED = 'dismissed', 'Bác bỏ'
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name='Đánh giá'
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_reports',
        verbose_name='Người báo cáo'
    )
    
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
        verbose_name='Lý do'
    )
    details = models.TextField(blank=True, verbose_name='Chi tiết')
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Trạng thái'
    )
    
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Người xử lý'
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Báo cáo đánh giá'
        verbose_name_plural = 'Báo cáo đánh giá'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"Report on {self.review}"
    
    def resolve(self, action: str, handler=None, notes: str = ''):
        """Resolve the report."""
        self.status = self.Status.RESOLVED
        self.handled_by = handler
        self.handled_at = timezone.now()
        self.resolution_notes = notes
        self.save()
        
        if action == 'remove':
            self.review.reject('Removed due to report', handler)


class ReviewSummary(models.Model):
    """
    Cached review summary for products.
    Updated periodically for performance.
    """
    
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='review_summary',
        primary_key=True
    )
    
    total_reviews = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Rating distribution
    rating_5 = models.PositiveIntegerField(default=0)
    rating_4 = models.PositiveIntegerField(default=0)
    rating_3 = models.PositiveIntegerField(default=0)
    rating_2 = models.PositiveIntegerField(default=0)
    rating_1 = models.PositiveIntegerField(default=0)
    
    # Detailed ratings
    avg_quality = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    avg_value = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    avg_delivery = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Stats
    verified_count = models.PositiveIntegerField(default=0)
    with_images_count = models.PositiveIntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Thống kê đánh giá'
        verbose_name_plural = 'Thống kê đánh giá'
    
    def refresh(self):
        """Recalculate all stats from reviews."""
        reviews = Review.objects.filter(product=self.product, is_approved=True)
        
        self.total_reviews = reviews.count()
        
        if self.total_reviews > 0:
            stats = reviews.aggregate(
                avg=Avg('rating'),
                r5=Count('id', filter=models.Q(rating=5)),
                r4=Count('id', filter=models.Q(rating=4)),
                r3=Count('id', filter=models.Q(rating=3)),
                r2=Count('id', filter=models.Q(rating=2)),
                r1=Count('id', filter=models.Q(rating=1)),
                avg_q=Avg('quality_rating'),
                avg_v=Avg('value_rating'),
                avg_d=Avg('delivery_rating'),
                verified=Count('id', filter=models.Q(is_verified_purchase=True)),
            )
            
            self.average_rating = stats['avg'] or 0
            self.rating_5 = stats['r5']
            self.rating_4 = stats['r4']
            self.rating_3 = stats['r3']
            self.rating_2 = stats['r2']
            self.rating_1 = stats['r1']
            self.avg_quality = stats['avg_q'] or 0
            self.avg_value = stats['avg_v'] or 0
            self.avg_delivery = stats['avg_d'] or 0
            self.verified_count = stats['verified']
            
            self.with_images_count = reviews.filter(images__isnull=False).distinct().count()
        
        self.save()
    
    @property
    def rating_distribution(self) -> dict:
        """Get rating distribution as percentages."""
        if self.total_reviews == 0:
            return {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        return {
            5: int((self.rating_5 / self.total_reviews) * 100),
            4: int((self.rating_4 / self.total_reviews) * 100),
            3: int((self.rating_3 / self.total_reviews) * 100),
            2: int((self.rating_2 / self.total_reviews) * 100),
            1: int((self.rating_1 / self.total_reviews) * 100),
        }
