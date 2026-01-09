"""Store Reviews - Product Review Models."""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Avg, Count
from apps.common.core.models import TimeStampedModel, UUIDModel


def review_image_path(instance, filename):
    return f'reviews/{instance.review.product_id}/{filename}'


class ReviewManager(models.Manager):
    def approved(self):
        return self.filter(is_approved=True)

    def pending(self):
        return self.filter(is_approved=False, is_rejected=False)

    def with_images(self):
        return self.filter(images__isnull=False).distinct()

    def verified_only(self):
        return self.filter(is_verified_purchase=True)


class Review(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews', verbose_name='User')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='reviews', verbose_name='Product')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews', verbose_name='Order')

    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], db_index=True, verbose_name='Rating')
    title = models.CharField(max_length=200, blank=True, verbose_name='Title')
    comment = models.TextField(verbose_name='Comment')

    quality_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True, verbose_name='Quality')
    value_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True, verbose_name='Value')
    delivery_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True, verbose_name='Delivery')

    is_verified_purchase = models.BooleanField(default=False, db_index=True, verbose_name='Verified Purchase')

    is_approved = models.BooleanField(default=False, db_index=True, verbose_name='Approved')
    is_rejected = models.BooleanField(default=False, verbose_name='Rejected')
    rejection_reason = models.TextField(blank=True, verbose_name='Rejection Reason')
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_reviews', verbose_name='Moderated By')
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name='Moderated At')

    helpful_count = models.PositiveIntegerField(default=0, verbose_name='Helpful')
    not_helpful_count = models.PositiveIntegerField(default=0, verbose_name='Not Helpful')

    is_featured = models.BooleanField(default=False, verbose_name='Featured')
    is_pinned = models.BooleanField(default=False, verbose_name='Pinned')

    objects = ReviewManager()

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
        unique_together = ['user', 'product']
        indexes = [models.Index(fields=['product', 'is_approved', '-created_at']), models.Index(fields=['product', 'rating']), models.Index(fields=['user', '-created_at'])]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.product.name}: {self.rating}★"

    def save(self, *args, **kwargs):
        if not self.is_verified_purchase and self.user_id and self.product_id:
            self._check_verified_purchase()
        super().save(*args, **kwargs)
        self._update_product_rating()

    def _check_verified_purchase(self):
        try:
            from apps.store.orders.models import OrderItem
            order_query = OrderItem.objects.filter(order__user=self.user, product=self.product, order__status='delivered')
            if order_query.exists():
                self.is_verified_purchase = True
                if not self.order_id:
                    self.order = order_query.first().order
        except:
            pass

    def _update_product_rating(self):
        from apps.store.catalog.models import ProductStat
        stats = Review.objects.filter(product=self.product, is_approved=True).aggregate(avg_rating=Avg('rating'), count=Count('id'))
        ProductStat.objects.update_or_create(product_id=self.product_id, defaults={'rating_avg': stats['avg_rating'] or 0, 'rating_count': stats['count']})

    @property
    def user_display_name(self) -> str:
        if self.user.get_full_name():
            name = self.user.get_full_name()
            parts = name.split()
            if len(parts) > 1:
                return f"{parts[0]} {parts[-1][0]}."
            return parts[0]
        return self.user.email.split('@')[0]

    @property
    def has_images(self) -> bool:
        return self.images.exists()

    @property
    def helpfulness_score(self) -> int:
        return self.helpful_count - self.not_helpful_count

    @property
    def helpfulness_percentage(self) -> int:
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 0
        return int((self.helpful_count / total) * 100)

    def approve(self, moderator=None):
        self.is_approved = True
        self.is_rejected = False
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=['is_approved', 'is_rejected', 'moderated_by', 'moderated_at', 'updated_at'])

    def reject(self, reason: str, moderator=None):
        self.is_approved = False
        self.is_rejected = True
        self.rejection_reason = reason
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=['is_approved', 'is_rejected', 'rejection_reason', 'moderated_by', 'moderated_at', 'updated_at'])

    def vote_helpful(self, user, is_helpful: bool = True):
        vote, created = ReviewVote.objects.update_or_create(review=self, user=user, defaults={'is_helpful': is_helpful})
        stats = self.votes.aggregate(helpful=Count('id', filter=models.Q(is_helpful=True)), not_helpful=Count('id', filter=models.Q(is_helpful=False)))
        self.helpful_count = stats['helpful']
        self.not_helpful_count = stats['not_helpful']
        self.save(update_fields=['helpful_count', 'not_helpful_count', 'updated_at'])
        return vote


class ReviewImage(TimeStampedModel):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images', verbose_name='Review')
    image = models.ImageField(upload_to=review_image_path, verbose_name='Image')
    caption = models.CharField(max_length=200, blank=True, verbose_name='Caption')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Review Image'
        verbose_name_plural = 'Review Images'
        ordering = ['sort_order']

    def __str__(self) -> str:
        return f"Image for {self.review}"


class ReviewReply(TimeStampedModel):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='replies', verbose_name='Review')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_replies', verbose_name='User')
    content = models.TextField(verbose_name='Content')
    is_official = models.BooleanField(default=False, verbose_name='Official Reply')

    class Meta:
        verbose_name = 'Review Reply'
        verbose_name_plural = 'Review Replies'
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"Reply to {self.review}"


class ReviewVote(TimeStampedModel):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='votes', verbose_name='Review')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_votes', verbose_name='User')
    is_helpful = models.BooleanField(verbose_name='Helpful')

    class Meta:
        verbose_name = 'Review Vote'
        verbose_name_plural = 'Review Votes'
        unique_together = ['review', 'user']

    def __str__(self) -> str:
        vote_type = "Helpful" if self.is_helpful else "Not helpful"
        return f"{vote_type} vote on {self.review}"


class ReviewReport(TimeStampedModel):
    class Reason(models.TextChoices):
        SPAM = 'spam', 'Spam'
        OFFENSIVE = 'offensive', 'Offensive Language'
        FAKE = 'fake', 'Fake Review'
        IRRELEVANT = 'irrelevant', 'Irrelevant'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWED = 'reviewed', 'Reviewed'
        RESOLVED = 'resolved', 'Resolved'
        DISMISSED = 'dismissed', 'Dismissed'

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='reports', verbose_name='Review')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_reports', verbose_name='Reporter')
    reason = models.CharField(max_length=20, choices=Reason.choices, verbose_name='Reason')
    details = models.TextField(blank=True, verbose_name='Details')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name='Status')
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='Handled By')
    handled_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Review Report'
        verbose_name_plural = 'Review Reports'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Report on {self.review}"

    def resolve(self, action: str, handler=None, notes: str = ''):
        self.status = self.Status.RESOLVED
        self.handled_by = handler
        self.handled_at = timezone.now()
        self.resolution_notes = notes
        self.save()
        if action == 'remove':
            self.review.reject('Removed due to report', handler)


class ReviewSummary(models.Model):
    product = models.OneToOneField('catalog.Product', on_delete=models.CASCADE, related_name='review_summary', primary_key=True)
    total_reviews = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_5 = models.PositiveIntegerField(default=0)
    rating_4 = models.PositiveIntegerField(default=0)
    rating_3 = models.PositiveIntegerField(default=0)
    rating_2 = models.PositiveIntegerField(default=0)
    rating_1 = models.PositiveIntegerField(default=0)
    avg_quality = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    avg_value = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    avg_delivery = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    verified_count = models.PositiveIntegerField(default=0)
    with_images_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Review Summary'
        verbose_name_plural = 'Review Summaries'

    def refresh(self):
        reviews = Review.objects.filter(product=self.product, is_approved=True)
        self.total_reviews = reviews.count()
        if self.total_reviews > 0:
            stats = reviews.aggregate(avg=Avg('rating'), r5=Count('id', filter=models.Q(rating=5)), r4=Count('id', filter=models.Q(rating=4)), r3=Count('id', filter=models.Q(rating=3)), r2=Count('id', filter=models.Q(rating=2)), r1=Count('id', filter=models.Q(rating=1)), avg_q=Avg('quality_rating'), avg_v=Avg('value_rating'), avg_d=Avg('delivery_rating'), verified=Count('id', filter=models.Q(is_verified_purchase=True)))
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
        if self.total_reviews == 0:
            return {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        return {
            5: int((self.rating_5 / self.total_reviews) * 100),
            4: int((self.rating_4 / self.total_reviews) * 100),
            3: int((self.rating_3 / self.total_reviews) * 100),
            2: int((self.rating_2 / self.total_reviews) * 100),
            1: int((self.rating_1 / self.total_reviews) * 100),
        }
