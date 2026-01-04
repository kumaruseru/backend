"""
Common Core - Base Models and Mixins.

Provides abstract base classes for all domain models following DDD principles:
- TimeStampedModel: Adds created_at/updated_at timestamps
- UUIDModel: Adds UUID primary key with timestamps
- SoftDeleteModel: Adds soft delete capability
- SluggedModel: Auto-generates slugs
- OrderedModel: Ordering support
"""
import uuid
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """
    Abstract base model with automatic created/updated timestamps.
    
    All domain entities should inherit from this to maintain
    audit trail of when records were created and modified.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Ngày tạo',
        help_text='Thời điểm bản ghi được tạo'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Ngày cập nhật',
        help_text='Thời điểm bản ghi được cập nhật lần cuối'
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    def touch(self):
        """Update the updated_at timestamp."""
        self.updated_at = timezone.now()
        self.save(update_fields=['updated_at'])


class UUIDModel(TimeStampedModel):
    """
    Abstract base model with UUID primary key.
    
    Use for aggregate roots that need globally unique identifiers.
    Benefits: No sequential ID guessing, better for distributed systems.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID'
    )

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted records by default."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Include soft-deleted records in queryset."""
        return super().get_queryset()
    
    def deleted_only(self):
        """Return only soft-deleted records."""
        return super().get_queryset().filter(is_deleted=True)




class SoftDeleteModel(TimeStampedModel):
    """
    Abstract base model with soft delete capability.
    
    Records are marked as deleted but not removed from database.
    Useful for maintaining data integrity and audit trails.
    """
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Đã xóa',
        help_text='Đánh dấu bản ghi đã bị xóa mềm'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Ngày xóa'
    )
    deleted_by = models.ForeignKey(
        'identity.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Người xóa'
    )

    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        """Mark this record as deleted."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])
    
    def delete(self, using=None, keep_parents=False, hard=False):
        """Override delete to soft delete by default."""
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.soft_delete()


class UUIDSoftDeleteModel(UUIDModel, SoftDeleteModel):
    """
    Combines UUID primary key with soft delete capability.
    
    Ideal for aggregate roots that need both features:
    - User accounts
    - Orders (for audit trail)
    """
    
    class Meta:
        abstract = True


# ==================== Additional Mixins ====================

class SluggedMixin(models.Model):
    """
    Mixin that adds auto-generated slug field.
    
    Override `get_slug_source()` to customize slug source.
    """
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name='Slug'
    )
    
    class Meta:
        abstract = True
    
    def get_slug_source(self) -> str:
        """Return the field value to generate slug from."""
        return getattr(self, 'name', '') or getattr(self, 'title', '')
    
    def generate_unique_slug(self) -> str:
        """Generate a unique slug."""
        # Use custom vietnamese slug generation to avoid accents in URL
        from ..core.utils import generate_slug_from_vietnamese
        
        base_slug = generate_slug_from_vietnamese(self.get_slug_source())
        if not base_slug:
            base_slug = str(uuid.uuid4())[:8]
        
        slug = base_slug
        counter = 1
        model_class = self.__class__
        
        # Check for uniqueness
        queryset = model_class.objects.all()
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        
        while queryset.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def save(self, *args, **kwargs):
        from django.db import IntegrityError
        from ..core.utils import generate_slug_from_vietnamese
        
        max_retries = 5
        for attempt in range(max_retries):
            if not self.slug:
                self.slug = self.generate_unique_slug()
            
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                # Check if it's a slug uniqueness error
                if 'slug' in str(e).lower() and attempt < max_retries - 1:
                    # Regenerate slug with random suffix
                    base_slug = generate_slug_from_vietnamese(self.get_slug_source()) or str(uuid.uuid4())[:8]
                    self.slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
                    continue
                raise


class OrderedMixin(models.Model):
    """
    Mixin that adds ordering capability.
    """
    order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name='Thứ tự'
    )
    
    class Meta:
        abstract = True
        ordering = ['order']
    
    def move_up(self):
        """Move this item up in order."""
        if self.order > 0:
            self.order -= 1
            self.save(update_fields=['order', 'updated_at'])
    
    def move_down(self):
        """Move this item down in order."""
        self.order += 1
        self.save(update_fields=['order', 'updated_at'])


class PublishableMixin(models.Model):
    """
    Mixin for content that can be published/unpublished.
    """
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Đã xuất bản'
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Ngày xuất bản'
    )
    
    class Meta:
        abstract = True
    
    def publish(self):
        """Publish this content."""
        self.is_published = True
        self.published_at = timezone.now()
        self.save(update_fields=['is_published', 'published_at', 'updated_at'])
    
    def unpublish(self):
        """Unpublish this content."""
        self.is_published = False
        self.save(update_fields=['is_published', 'updated_at'])


class ActiveMixin(models.Model):
    """
    Simple is_active toggle mixin.
    """
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Hoạt động'
    )
    
    class Meta:
        abstract = True


class MetadataMixin(models.Model):
    """
    Mixin for entities that need arbitrary metadata storage.
    """
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )
    
    class Meta:
        abstract = True
    
    def get_meta(self, key: str, default=None):
        """Get a metadata value."""
        return self.metadata.get(key, default)
    
    def set_meta(self, key: str, value):
        """Set a metadata value."""
        self.metadata[key] = value
        self.save(update_fields=['metadata', 'updated_at'])


class AuditMixin(models.Model):
    """
    Mixin for tracking who created/updated records.
    """
    created_by = models.ForeignKey(
        'identity.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Người tạo'
    )
    updated_by = models.ForeignKey(
        'identity.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Người cập nhật'
    )
    
    class Meta:
        abstract = True
