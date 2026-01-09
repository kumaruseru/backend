"""Common Locations - Services.

Business logic for Vietnamese administrative units using hanhchinhvn library.
Fully leverages the library's capabilities including lazy loading, search, and full address resolution.
"""
import logging
from typing import Dict, List, Optional, NamedTuple
from django.db import transaction
from django.core.cache import cache

from .models import Province as DBProvince, District as DBDistrict, Ward as DBWard

logger = logging.getLogger('apps.locations')

# Cache timeout in seconds
CACHE_TIMEOUT = 3600 * 24  # 24 hours


class FullAddressResult(NamedTuple):
    """Full address with administrative hierarchy."""
    ward: DBWard
    district: DBDistrict
    province: DBProvince
    full_address: str


class LocationService:
    """
    Service for managing administrative locations.
    Uses hanhchinhvn library for data import and lookup.
    """

    @staticmethod
    def import_all_locations(force: bool = False) -> Dict[str, int]:
        """
        Import all provinces, districts, and wards from hanhchinhvn library.
        
        Uses efficient generators instead of loading all data into memory.
        
        Args:
            force: If True, delete existing data before import
            
        Returns:
            Dict with counts: {'provinces': x, 'districts': y, 'wards': z}
        """
        try:
            from hanhchinhvn import (
                iter_all_provinces,
                iter_all_districts,
                iter_all_wards,
            )
        except ImportError:
            logger.error("hanhchinhvn library not installed. Run: pip install hanhchinhvn")
            raise ImportError("hanhchinhvn library not installed")

        counts = {'provinces': 0, 'districts': 0, 'wards': 0}

        with transaction.atomic():
            if force:
                DBWard.objects.all().delete()
                DBDistrict.objects.all().delete()
                DBProvince.objects.all().delete()

            # Phase 1: Import Provinces
            province_map = {}
            for lib_province in iter_all_provinces():
                db_province, created = DBProvince.objects.update_or_create(
                    code=lib_province.code,
                    defaults={
                        'name': lib_province.name,
                        'name_with_type': lib_province.name_with_type,
                        'slug': lib_province.slug,
                        'type': lib_province.type.value if lib_province.type else '',
                        'search_slug': lib_province.search_slug,
                        'path': lib_province.path or '',
                        'path_with_type': lib_province.path_with_type or '',
                    }
                )
                province_map[lib_province.code] = db_province
                if created:
                    counts['provinces'] += 1

            # Phase 2: Import Districts (using generator)
            district_map = {}
            for province_code, lib_district in iter_all_districts():
                db_province = province_map.get(province_code)
                if not db_province:
                    continue
                    
                db_district, created = DBDistrict.objects.update_or_create(
                    code=lib_district.code,
                    defaults={
                        'province': db_province,
                        'name': lib_district.name,
                        'name_with_type': lib_district.name_with_type,
                        'slug': lib_district.slug,
                        'type': lib_district.type.value if lib_district.type else '',
                        'search_slug': lib_district.search_slug,
                        'path': lib_district.path or '',
                        'path_with_type': lib_district.path_with_type or '',
                    }
                )
                district_map[lib_district.code] = db_district
                if created:
                    counts['districts'] += 1

            # Phase 3: Import Wards (using generator)
            for district_code, lib_ward in iter_all_wards():
                db_district = district_map.get(district_code)
                if not db_district:
                    continue
                    
                _, created = DBWard.objects.update_or_create(
                    code=lib_ward.code,
                    defaults={
                        'district': db_district,
                        'name': lib_ward.name,
                        'name_with_type': lib_ward.name_with_type,
                        'slug': lib_ward.slug,
                        'type': lib_ward.type.value if lib_ward.type else '',
                        'search_slug': lib_ward.search_slug,
                        'path': lib_ward.path or '',
                        'path_with_type': lib_ward.path_with_type or '',
                    }
                )
                if created:
                    counts['wards'] += 1

        # Clear cache after import
        cache.delete_pattern('locations:*')
        logger.info(f"Imported locations: {counts}")
        return counts

    @staticmethod
    def get_full_address_from_library(ward_code: str) -> Optional[FullAddressResult]:
        """
        Get full address using hanhchinhvn's get_full_address_by_ward_code.
        
        This is useful for reverse lookup without hitting the database.
        Returns database objects if available, otherwise None.
        
        Args:
            ward_code: Ward code (e.g., "00001")
            
        Returns:
            FullAddressResult or None
        """
        try:
            from hanhchinhvn import get_full_address_by_ward_code
            
            result = get_full_address_by_ward_code(ward_code)
            if not result:
                return None
            
            # Try to get from database
            try:
                db_ward = DBWard.objects.select_related(
                    'district__province'
                ).get(code=ward_code)
                
                return FullAddressResult(
                    ward=db_ward,
                    district=db_ward.district,
                    province=db_ward.district.province,
                    full_address=result.full_address
                )
            except DBWard.DoesNotExist:
                return None
                
        except ImportError:
            logger.warning("hanhchinhvn library not available")
            return None

    @staticmethod
    def search_from_library(query: str, limit: int = 20) -> Dict[str, List]:
        """
        Search locations using hanhchinhvn's accent-insensitive search.
        
        Args:
            query: Search query (Vietnamese or ASCII)
            limit: Max results per category
            
        Returns:
            Dict with 'provinces', 'districts', 'wards' lists
        """
        try:
            from hanhchinhvn import Province as LibProvince
            import text_unidecode
            
            results = {'provinces': [], 'districts': [], 'wards': []}
            
            if len(query) < 2:
                return results
            
            # Normalize query
            query_normalized = text_unidecode.unidecode(query).lower().strip()
            
            # Search provinces using library's search method
            lib_provinces = LibProvince.search(query)[:limit]
            
            # Convert to database objects
            province_codes = [p.code for p in lib_provinces]
            results['provinces'] = list(
                DBProvince.objects.filter(code__in=province_codes)
            )
            
            # Search districts
            district_codes = []
            for province in LibProvince.all():
                for district in province.districts:
                    if query_normalized in text_unidecode.unidecode(district.name).lower():
                        district_codes.append(district.code)
                        if len(district_codes) >= limit:
                            break
                if len(district_codes) >= limit:
                    break
            
            results['districts'] = list(
                DBDistrict.objects.filter(code__in=district_codes).select_related('province')
            )
            
            return results
            
        except ImportError:
            logger.warning("hanhchinhvn library not available, falling back to database search")
            return LocationSelector.search_locations(query, limit)

    @staticmethod
    def get_statistics() -> Dict[str, int]:
        """Get location statistics."""
        return {
            'provinces': DBProvince.objects.filter(is_active=True).count(),
            'districts': DBDistrict.objects.filter(is_active=True).count(),
            'wards': DBWard.objects.filter(is_active=True).count(),
        }

    @staticmethod
    def validate_address_hierarchy(province_code: str, district_code: str, ward_code: str) -> bool:
        """
        Validate that province -> district -> ward hierarchy is correct.
        
        Uses hanhchinhvn library for fast validation without database hit.
        """
        try:
            from hanhchinhvn import get_full_address_by_ward_code
            
            result = get_full_address_by_ward_code(ward_code)
            if not result:
                return False
            
            return (
                result.province.code == province_code and 
                result.district.code == district_code
            )
        except ImportError:
            # Fallback to database validation
            try:
                ward = DBWard.objects.select_related('district__province').get(code=ward_code)
                return (
                    ward.district.province.code == province_code and
                    ward.district.code == district_code
                )
            except DBWard.DoesNotExist:
                return False


class LocationSelector:
    """
    Read-only queries for locations with Redis caching.
    
    Uses database for cached queries, falls back to hanhchinhvn library when needed.
    """

    @staticmethod
    def get_all_provinces(active_only: bool = True) -> List[DBProvince]:
        """Get all provinces with caching."""
        cache_key = f'locations:provinces:all:{active_only}'
        result = cache.get(cache_key)
        
        if result is None:
            qs = DBProvince.objects.all()
            if active_only:
                qs = qs.filter(is_active=True)
            result = list(qs.order_by('sort_order', 'name'))
            cache.set(cache_key, result, CACHE_TIMEOUT)
        
        return result

    @staticmethod
    def get_province_by_code(code: str) -> Optional[DBProvince]:
        """Get province by code with caching."""
        cache_key = f'locations:province:{code}'
        result = cache.get(cache_key)
        
        if result is None:
            try:
                result = DBProvince.objects.get(code=code)
                cache.set(cache_key, result, CACHE_TIMEOUT)
            except DBProvince.DoesNotExist:
                return None
        
        return result

    @staticmethod
    def get_districts_by_province(province_code: str, active_only: bool = True) -> List[DBDistrict]:
        """Get all districts in a province with caching."""
        cache_key = f'locations:districts:province:{province_code}:{active_only}'
        result = cache.get(cache_key)
        
        if result is None:
            qs = DBDistrict.objects.filter(province__code=province_code)
            if active_only:
                qs = qs.filter(is_active=True)
            result = list(qs.select_related('province').order_by('name'))
            cache.set(cache_key, result, CACHE_TIMEOUT)
        
        return result

    @staticmethod
    def get_district_by_code(code: str) -> Optional[DBDistrict]:
        """Get district by code with caching."""
        cache_key = f'locations:district:{code}'
        result = cache.get(cache_key)
        
        if result is None:
            try:
                result = DBDistrict.objects.select_related('province').get(code=code)
                cache.set(cache_key, result, CACHE_TIMEOUT)
            except DBDistrict.DoesNotExist:
                return None
        
        return result

    @staticmethod
    def get_wards_by_district(district_code: str, active_only: bool = True) -> List[DBWard]:
        """Get all wards in a district with caching."""
        cache_key = f'locations:wards:district:{district_code}:{active_only}'
        result = cache.get(cache_key)
        
        if result is None:
            qs = DBWard.objects.filter(district__code=district_code)
            if active_only:
                qs = qs.filter(is_active=True)
            result = list(qs.select_related('district__province').order_by('name'))
            cache.set(cache_key, result, CACHE_TIMEOUT)
        
        return result

    @staticmethod
    def get_ward_by_code(code: str) -> Optional[DBWard]:
        """Get ward by code with caching."""
        cache_key = f'locations:ward:{code}'
        result = cache.get(cache_key)
        
        if result is None:
            try:
                result = DBWard.objects.select_related('district__province').get(code=code)
                cache.set(cache_key, result, CACHE_TIMEOUT)
            except DBWard.DoesNotExist:
                return None
        
        return result

    @staticmethod
    def get_full_address(ward_code: str) -> Optional[str]:
        """Get full address string from ward code."""
        ward = LocationSelector.get_ward_by_code(ward_code)
        if ward:
            return ward.full_address
        return None

    @staticmethod
    def search_locations(query: str, limit: int = 20) -> Dict[str, List]:
        """
        Search provinces, districts, and wards by name.
        Uses search_slug for accent-insensitive matching.
        """
        results = {'provinces': [], 'districts': [], 'wards': []}
        
        if len(query) < 2:
            return results
        
        # Normalize query for search_slug matching
        try:
            import text_unidecode
            query_slug = text_unidecode.unidecode(query).lower().replace(' ', '-')
        except ImportError:
            query_slug = query.lower()

        results['provinces'] = list(
            DBProvince.objects.filter(
                search_slug__icontains=query_slug, 
                is_active=True
            )[:limit]
        )
        
        results['districts'] = list(
            DBDistrict.objects.filter(
                search_slug__icontains=query_slug, 
                is_active=True
            ).select_related('province')[:limit]
        )
        
        results['wards'] = list(
            DBWard.objects.filter(
                search_slug__icontains=query_slug, 
                is_active=True
            ).select_related('district__province')[:limit]
        )
        
        return results

    @staticmethod
    def autocomplete(query: str, level: str = 'all', limit: int = 10) -> List[Dict]:
        """
        Autocomplete for address input.
        
        Args:
            query: Search query
            level: 'province', 'district', 'ward', or 'all'
            limit: Max results
            
        Returns:
            List of dicts with code, name, type, and parent info
        """
        results = []
        
        if len(query) < 2:
            return results
        
        try:
            import text_unidecode
            query_slug = text_unidecode.unidecode(query).lower().replace(' ', '-')
        except ImportError:
            query_slug = query.lower()

        if level in ('province', 'all'):
            provinces = DBProvince.objects.filter(
                search_slug__icontains=query_slug, 
                is_active=True
            )[:limit]
            for p in provinces:
                results.append({
                    'code': p.code,
                    'name': p.name_with_type,
                    'type': 'province',
                    'parent': None,
                })

        if level in ('district', 'all'):
            districts = DBDistrict.objects.filter(
                search_slug__icontains=query_slug, 
                is_active=True
            ).select_related('province')[:limit]
            for d in districts:
                results.append({
                    'code': d.code,
                    'name': d.name_with_type,
                    'type': 'district',
                    'parent': {'code': d.province.code, 'name': d.province.name_with_type},
                })

        if level in ('ward', 'all'):
            wards = DBWard.objects.filter(
                search_slug__icontains=query_slug, 
                is_active=True
            ).select_related('district__province')[:limit]
            for w in wards:
                results.append({
                    'code': w.code,
                    'name': w.name_with_type,
                    'type': 'ward',
                    'parent': {
                        'code': w.district.code, 
                        'name': w.district.name_with_type,
                        'province': {
                            'code': w.district.province.code,
                            'name': w.district.province.name_with_type,
                        }
                    },
                })

        return results[:limit]
