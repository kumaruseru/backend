"""Maintenance Mode Backend using Redis."""
from django.core.cache import cache
from maintenance_mode.backends import AbstractStateBackend


class ConstanceMaintenanceBackend(AbstractStateBackend):
    """Redis-based maintenance mode state backend."""

    CACHE_KEY = 'maintenance_mode'

    def get_value(self) -> bool:
        return cache.get(self.CACHE_KEY, False)

    def set_value(self, value: bool) -> None:
        cache.set(self.CACHE_KEY, value, timeout=None)

