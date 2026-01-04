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

# ==================== Upload Path Generators ====================

def get_upload_path(directory: str, id_field='id') -> callable:
    """
    Factory to generate upload path functions.
    
    Args:
        directory: Target directory (e.g., 'avatars', 'products')
        id_field: Field to use for sub-directory (default: 'id')
                  Can be a specific field name or 'pk'.
                  Can also handle special cases via custom logic check in wrapper if needed.
    """
    def wrapper(instance, filename: str) -> str:
        ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
        new_filename = f"{uuid.uuid4()}.{ext}"
        
        # Determine ID based on instance type and configuration
        obj_id = 'unknown'
        
        # Handle specific cases first
        if directory == 'products' and hasattr(instance, 'product_id'):
             obj_id = instance.product_id
        elif directory == 'reviews' and hasattr(instance, 'review_id'):
             obj_id = instance.review_id
        elif directory == 'returns' and hasattr(instance, 'return_request_id'):
             obj_id = instance.return_request_id
        elif directory == 'invoices' and hasattr(instance, 'order_id'):
            obj_id = instance.order_id
        elif directory == 'blog' and not getattr(instance, 'slug', None):
            obj_id = 'draft'
        else:
            # Default lookup
            obj_id = getattr(instance, id_field, getattr(instance, 'pk', 'unknown'))
            
        return f"{directory}/{obj_id}/{new_filename}"
        
    return wrapper


user_avatar_path = get_upload_path('avatars')
product_image_path = get_upload_path('products')
category_image_path = get_upload_path('categories', id_field='slug')
brand_logo_path = get_upload_path('brands', id_field='slug')
review_image_path = get_upload_path('reviews')
return_evidence_path = get_upload_path('returns')

def banner_image_path(instance, filename: str) -> str:
    """Generate path for banner image uploads."""
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"banners/{new_filename}"

blog_image_path = get_upload_path('blog', id_field='slug')
invoice_path = get_upload_path('invoices')
