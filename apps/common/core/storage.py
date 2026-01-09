"""Common Core - Storage Backends."""
import uuid
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


def user_avatar_path(instance, filename: str) -> str:
    """Generate path for user avatar uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    obj_id = getattr(instance, 'id', getattr(instance, 'pk', 'unknown'))
    return f"avatars/{obj_id}/{new_filename}"


def product_image_path(instance, filename: str) -> str:
    """Generate path for product image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    obj_id = getattr(instance, 'product_id', getattr(instance, 'pk', 'unknown'))
    return f"products/{obj_id}/{new_filename}"


def category_image_path(instance, filename: str) -> str:
    """Generate path for category image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    obj_id = getattr(instance, 'slug', getattr(instance, 'pk', 'unknown'))
    return f"categories/{obj_id}/{new_filename}"


def brand_logo_path(instance, filename: str) -> str:
    """Generate path for brand logo uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    obj_id = getattr(instance, 'slug', getattr(instance, 'pk', 'unknown'))
    return f"brands/{obj_id}/{new_filename}"


def review_image_path(instance, filename: str) -> str:
    """Generate path for review image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    obj_id = getattr(instance, 'review_id', getattr(instance, 'pk', 'unknown'))
    return f"reviews/{obj_id}/{new_filename}"


def return_evidence_path(instance, filename: str) -> str:
    """Generate path for return evidence uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    obj_id = getattr(instance, 'return_request_id', getattr(instance, 'pk', 'unknown'))
    return f"returns/{obj_id}/{new_filename}"


def invoice_path(instance, filename: str) -> str:
    """Generate path for invoice uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'pdf'
    new_filename = f"{uuid.uuid4()}.{ext}"
    obj_id = getattr(instance, 'order_id', getattr(instance, 'pk', 'unknown'))
    return f"invoices/{obj_id}/{new_filename}"


def banner_image_path(instance, filename: str) -> str:
    """Generate path for banner image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"banners/{new_filename}"
