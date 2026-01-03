"""
OWLS Backend Package.

This module configures Celery to work with Django.
"""
from .celery import app as celery_app

__all__ = ('celery_app',)
