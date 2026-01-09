"""Common Utils - String Utilities."""
import re
import unicodedata
from typing import Optional
import bleach
from django.conf import settings


VIETNAMESE_MAP = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'đ': 'd',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
}


def remove_vietnamese_accents(text: str) -> str:
    """Remove Vietnamese diacritics from text."""
    if not text:
        return text
    result = []
    for char in text:
        lower_char = char.lower()
        if lower_char in VIETNAMESE_MAP:
            replacement = VIETNAMESE_MAP[lower_char]
            result.append(replacement.upper() if char.isupper() else replacement)
        else:
            result.append(char)
    return ''.join(result)


def slugify_vietnamese(text: str) -> str:
    """Generate URL-safe slug from Vietnamese text."""
    if not text:
        return ''
    text = remove_vietnamese_accents(text)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    text = text.strip('-')
    return text


def sanitize_html(html: str, allowed_tags: Optional[list] = None) -> str:
    """Sanitize HTML using django_bleach settings."""
    if not html:
        return html
    tags = allowed_tags or getattr(settings, 'BLEACH_ALLOWED_TAGS', ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'ul', 'ol', 'li', 'br'])
    attrs = getattr(settings, 'BLEACH_ALLOWED_ATTRIBUTES', {'a': ['href', 'title', 'target'], '*': ['class']})
    return bleach.clean(html, tags=tags, attributes=attrs, strip=True)


def truncate_words(text: str, num_words: int = 20, suffix: str = '...') -> str:
    """Truncate text to a specified number of words."""
    if not text:
        return text
    words = text.split()
    if len(words) <= num_words:
        return text
    return ' '.join(words[:num_words]) + suffix


def truncate_chars(text: str, num_chars: int = 100, suffix: str = '...') -> str:
    """Truncate text to a specified number of characters."""
    if not text or len(text) <= num_chars:
        return text
    return text[:num_chars].rsplit(' ', 1)[0] + suffix


def generate_excerpt(html: str, num_words: int = 30) -> str:
    """Generate plain text excerpt from HTML."""
    text = bleach.clean(html, tags=[], strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return truncate_words(text, num_words)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    if not text:
        return text
    return re.sub(r'\s+', ' ', text).strip()


def to_snake_case(text: str) -> str:
    """Convert text to snake_case."""
    text = re.sub(r'(?<!^)(?=[A-Z])', '_', text)
    return text.lower().replace(' ', '_').replace('-', '_')


def to_camel_case(text: str) -> str:
    """Convert text to camelCase."""
    words = re.split(r'[-_\s]+', text)
    return words[0].lower() + ''.join(word.capitalize() for word in words[1:])


def generate_unique_slug(model_class, instance, source_field: str, slug_field: str = 'slug') -> str:
    """
    Generate a unique slug for a model instance.
    
    Args:
        model_class: The Django model class
        instance: The model instance
        source_field: The field name to generate slug from (e.g., 'name')
        slug_field: The field name for the slug (default: 'slug')
    
    Returns:
        A unique slug string
    """
    source_value = getattr(instance, source_field, '')
    base_slug = slugify_vietnamese(source_value)
    
    if not base_slug:
        import uuid
        base_slug = str(uuid.uuid4())[:8]
    
    slug = base_slug
    counter = 1
    
    while True:
        qs = model_class.objects.filter(**{slug_field: slug})
        if instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if not qs.exists():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    return slug
