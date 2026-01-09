"""Common Core - Base Models and Mixins."""
import uuid
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from safedelete.models import SafeDeleteModel
from safedelete.config import SOFT_DELETE_CASCADE


class TimeStampedModel(models.Model):
    """Abstract base model with automatic created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def touch(self):
        self.updated_at = timezone.now()
        self.save(update_fields=['updated_at'])


class UUIDModel(TimeStampedModel):
    """Abstract base model with UUID primary key."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class UUIDSafeDeleteModel(SafeDeleteModel, UUIDModel):
    """UUID model with soft delete using safedelete library."""
    _safedelete_policy = SOFT_DELETE_CASCADE

    class Meta:
        abstract = True


class SluggedMixin(models.Model):
    """Mixin that adds auto-generated slug field."""
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')

    class Meta:
        abstract = True

    def get_slug_source(self) -> str:
        return getattr(self, 'name', '') or getattr(self, 'title', '')

    def generate_unique_slug(self) -> str:
        from apps.common.utils.string import slugify_vietnamese
        base_slug = slugify_vietnamese(self.get_slug_source()) or str(uuid.uuid4())[:8]
        slug = base_slug
        counter = 1
        model_class = self.__class__
        queryset = model_class.objects.all()
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        while queryset.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)


class OrderedMixin(models.Model):
    """Mixin that adds ordering capability."""
    order = models.PositiveIntegerField(default=0, db_index=True, verbose_name='Thứ tự')

    class Meta:
        abstract = True
        ordering = ['order']

    def move_up(self):
        if self.order > 0:
            self.order -= 1
            self.save(update_fields=['order', 'updated_at'])

    def move_down(self):
        self.order += 1
        self.save(update_fields=['order', 'updated_at'])


class PublishableMixin(models.Model):
    """Mixin for content that can be published/unpublished."""
    is_published = models.BooleanField(default=False, db_index=True, verbose_name='Đã xuất bản')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày xuất bản')

    class Meta:
        abstract = True

    def publish(self):
        self.is_published = True
        self.published_at = timezone.now()
        self.save(update_fields=['is_published', 'published_at', 'updated_at'])

    def unpublish(self):
        self.is_published = False
        self.save(update_fields=['is_published', 'updated_at'])


class ActiveMixin(models.Model):
    """Simple is_active toggle mixin."""
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Hoạt động')

    class Meta:
        abstract = True


class MetadataMixin(models.Model):
    """Mixin for entities that need arbitrary metadata storage."""
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Metadata')

    class Meta:
        abstract = True

    def get_meta(self, key: str, default=None):
        return self.metadata.get(key, default)

    def set_meta(self, key: str, value):
        self.metadata[key] = value
        self.save(update_fields=['metadata', 'updated_at'])
