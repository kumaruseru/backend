"""Common Locations - Signal Handlers."""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger('apps.locations.signals')


@receiver(post_save, sender='locations.Province')
def on_province_saved(sender, instance, created, **kwargs):
    """Invalidate province cache on save."""
    try:
        cache.delete('locations:provinces:all')
        cache.delete(f'locations:province:{instance.code}')
    except Exception as e:
        logger.warning(f"Error invalidating province cache: {e}")


@receiver(post_save, sender='locations.District')
def on_district_saved(sender, instance, created, **kwargs):
    """Invalidate district cache on save."""
    try:
        cache.delete(f'locations:districts:province:{instance.province.code}')
        cache.delete(f'locations:district:{instance.code}')
    except Exception as e:
        logger.warning(f"Error invalidating district cache: {e}")


@receiver(post_save, sender='locations.Ward')
def on_ward_saved(sender, instance, created, **kwargs):
    """Invalidate ward cache on save."""
    try:
        cache.delete(f'locations:wards:district:{instance.district.code}')
        cache.delete(f'locations:ward:{instance.code}')
    except Exception as e:
        logger.warning(f"Error invalidating ward cache: {e}")
