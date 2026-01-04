"""
String manipulation utilities.
"""
from django.utils.text import slugify


def truncate(text: str, length: int = 100, suffix: str = '...') -> str:
    """Truncate text to specified length."""
    if len(text) <= length:
        return text
    return text[:length - len(suffix)] + suffix


def mask_email(email: str) -> str:
    """Mask email for display."""
    if '@' not in email:
        return email
    
    local, domain = email.rsplit('@', 1)
    
    if len(local) <= 2:
        masked_local = local[0] + '*'
    else:
        masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
    
    return f"{masked_local}@{domain}"


# ==================== Vietnamese Text Utilities ====================

VIETNAMESE_ACCENTS = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    'đ': 'd',
    'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
    'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
    'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
    'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
    'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
    'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
    'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
    'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
    'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
    'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
    'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
    'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
    'Đ': 'D'
}


def remove_vietnamese_accents(text: str) -> str:
    """Remove Vietnamese diacritics from text."""
    for viet, latin in VIETNAMESE_ACCENTS.items():
        text = text.replace(viet, latin)
    return text


def generate_slug_from_vietnamese(text: str) -> str:
    """Generate slug from Vietnamese text."""
    # Remove accents
    text = remove_vietnamese_accents(text)
    # Generate slug
    return slugify(text, allow_unicode=False)


# ==================== Slug Utilities ====================

def generate_unique_slug(model_class, instance, source_field: str) -> str:
    """
    Generate a unique slug for a model instance.
    
    This is a shared utility for all models that need slugs.
    
    Args:
        model_class: The model class to check against
        instance: The model instance being saved
        source_field: The field name to generate slug from
    
    Returns:
        A unique slug string
    
    Example:
        class Product(models.Model):
            name = models.CharField(max_length=255)
            slug = models.SlugField(unique=True, blank=True)
            
            def save(self, *args, **kwargs):
                if not self.slug:
                    self.slug = generate_unique_slug(Product, self, 'name')
                super().save(*args, **kwargs)
    """
    import uuid
    
    source_value = getattr(instance, source_field, '')
    
    # Use Vietnamese-aware slug generation
    base_slug = generate_slug_from_vietnamese(source_value)
    
    if not base_slug:
        base_slug = str(uuid.uuid4())[:8]
    
    slug = base_slug
    counter = 1
    
    queryset = model_class.objects.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    
    while queryset.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    return slug
