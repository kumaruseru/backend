"""
Common Core - Storage Backends.

Provides custom storage backends for static and media files
using Cloudflare R2 (S3-compatible object storage).
"""
import os
import uuid
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    """Storage backend for static files (CSS, JS, images)."""
    location = 'static'
    default_acl = None
    file_overwrite = True
    querystring_auth = False


class MediaStorage(S3Boto3Storage):
    """Storage backend for user-uploaded media files."""
    location = 'media'
    default_acl = None
    file_overwrite = False
    querystring_auth = False


class PrivateMediaStorage(S3Boto3Storage):
    """Storage backend for private files (invoices, documents)."""
    location = 'private'
    default_acl = 'private'
    file_overwrite = False
    querystring_auth = True
    custom_domain = False


# ==================== Upload Path Generators ====================

def user_avatar_path(instance, filename: str) -> str:
    """Generate path for user avatar uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"avatars/{instance.id}/{new_filename}"


def product_image_path(instance, filename: str) -> str:
    """Generate path for product image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    product_id = getattr(instance, 'product_id', None) or getattr(instance.product, 'id', 'unknown')
    return f"products/{product_id}/{new_filename}"


def category_image_path(instance, filename: str) -> str:
    """Generate path for category image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"categories/{instance.slug}/{new_filename}"


def brand_logo_path(instance, filename: str) -> str:
    """Generate path for brand logo uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'png'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"brands/{instance.slug}/{new_filename}"


def review_image_path(instance, filename: str) -> str:
    """Generate path for review image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    review_id = getattr(instance, 'review_id', None) or getattr(instance, 'id', 'unknown')
    return f"reviews/{review_id}/{new_filename}"


def return_evidence_path(instance, filename: str) -> str:
    """Generate path for return evidence uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return_id = getattr(instance, 'return_request_id', 'unknown')
    return f"returns/{return_id}/{new_filename}"


def banner_image_path(instance, filename: str) -> str:
    """Generate path for banner image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"banners/{new_filename}"


def blog_image_path(instance, filename: str) -> str:
    """Generate path for blog image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"blog/{instance.slug or 'draft'}/{new_filename}"


def invoice_path(instance, filename: str) -> str:
    """Generate path for invoice uploads (private)."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'pdf'
    new_filename = f"{uuid.uuid4()}.{ext}"
    order_id = getattr(instance, 'order_id', 'unknown')
    return f"invoices/{order_id}/{new_filename}"
