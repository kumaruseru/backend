"""Common Locations - API Views.

REST API endpoints for Vietnamese administrative units.
Supports cascading dropdowns, search, and autocomplete.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .services import LocationSelector, LocationService
from .serializers import (
    ProvinceSerializer, 
    DistrictSerializer, 
    WardSerializer,
    FullAddressSerializer,
    AutocompleteResultSerializer,
)


class ProvinceListView(APIView):
    """List all provinces."""
    permission_classes = [AllowAny]

    def get(self, request):
        provinces = LocationSelector.get_all_provinces()
        serializer = ProvinceSerializer(provinces, many=True)
        return Response({
            'count': len(provinces),
            'results': serializer.data
        })


class ProvinceDetailView(APIView):
    """Get province detail with districts."""
    permission_classes = [AllowAny]

    def get(self, request, code):
        province = LocationSelector.get_province_by_code(code)
        if not province:
            return Response({'error': 'Province not found'}, status=404)
        
        districts = LocationSelector.get_districts_by_province(code)
        
        return Response({
            'province': ProvinceSerializer(province).data,
            'districts': DistrictSerializer(districts, many=True).data,
        })


class DistrictListView(APIView):
    """List districts by province code."""
    permission_classes = [AllowAny]

    def get(self, request, province_code):
        districts = LocationSelector.get_districts_by_province(province_code)
        serializer = DistrictSerializer(districts, many=True)
        return Response({
            'count': len(districts),
            'results': serializer.data
        })


class DistrictDetailView(APIView):
    """Get district detail with wards."""
    permission_classes = [AllowAny]

    def get(self, request, code):
        district = LocationSelector.get_district_by_code(code)
        if not district:
            return Response({'error': 'District not found'}, status=404)
        
        wards = LocationSelector.get_wards_by_district(code)
        
        return Response({
            'district': DistrictSerializer(district).data,
            'wards': WardSerializer(wards, many=True).data,
        })


class WardListView(APIView):
    """List wards by district code."""
    permission_classes = [AllowAny]

    def get(self, request, district_code):
        wards = LocationSelector.get_wards_by_district(district_code)
        serializer = WardSerializer(wards, many=True)
        return Response({
            'count': len(wards),
            'results': serializer.data
        })


class WardDetailView(APIView):
    """Get ward detail with full hierarchy."""
    permission_classes = [AllowAny]

    def get(self, request, code):
        ward = LocationSelector.get_ward_by_code(code)
        if not ward:
            return Response({'error': 'Ward not found'}, status=404)
        
        return Response({
            'ward': WardSerializer(ward).data,
            'district': DistrictSerializer(ward.district).data,
            'province': ProvinceSerializer(ward.district.province).data,
            'full_address': ward.full_address,
        })


class LocationSearchView(APIView):
    """
    Search locations by query.
    Uses accent-insensitive search via search_slug.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '')
        limit = int(request.query_params.get('limit', 20))
        use_library = request.query_params.get('use_library', 'false').lower() == 'true'
        
        if len(query) < 2:
            return Response({'error': 'Query must be at least 2 characters'}, status=400)
        
        # Use library search if requested (leverages hanhchinhvn's search)
        if use_library:
            results = LocationService.search_from_library(query, limit)
        else:
            results = LocationSelector.search_locations(query, limit)
        
        return Response({
            'query': query,
            'provinces': ProvinceSerializer(results['provinces'], many=True).data,
            'districts': DistrictSerializer(results['districts'], many=True).data,
            'wards': WardSerializer(results.get('wards', []), many=True).data,
        })


class AutocompleteView(APIView):
    """
    Autocomplete for address input.
    Returns unified result format for frontend dropdown.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '')
        level = request.query_params.get('level', 'all')  # province, district, ward, all
        limit = int(request.query_params.get('limit', 10))
        
        if len(query) < 2:
            return Response([])
        
        results = LocationSelector.autocomplete(query, level, limit)
        return Response(results)


class FullAddressResolveView(APIView):
    """
    Resolve full address from ward code.
    
    Useful for:
    - Showing full address from stored ward_code
    - Shipping fee calculation
    """
    permission_classes = [AllowAny]

    def get(self, request, ward_code):
        # Try database first
        ward = LocationSelector.get_ward_by_code(ward_code)
        if ward:
            return Response({
                'ward_code': ward.code,
                'district_code': ward.district.code,
                'province_code': ward.district.province.code,
                'full_address': ward.full_address,
                'ward': WardSerializer(ward).data,
                'district': DistrictSerializer(ward.district).data,
                'province': ProvinceSerializer(ward.district.province).data,
            })
        
        # Try library fallback
        result = LocationService.get_full_address_from_library(ward_code)
        if result:
            return Response({
                'ward_code': ward_code,
                'full_address': result.full_address,
            })
        
        return Response({'error': 'Ward not found'}, status=404)


class ValidateAddressView(APIView):
    """
    Validate address hierarchy.
    
    Ensures province -> district -> ward relationship is correct.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        province_code = request.data.get('province_code')
        district_code = request.data.get('district_code')
        ward_code = request.data.get('ward_code')
        
        if not all([province_code, district_code, ward_code]):
            return Response({
                'valid': False, 
                'error': 'All codes are required'
            }, status=400)
        
        is_valid = LocationService.validate_address_hierarchy(
            province_code, district_code, ward_code
        )
        
        return Response({
            'valid': is_valid,
            'province_code': province_code,
            'district_code': district_code,
            'ward_code': ward_code,
        })


class StatisticsView(APIView):
    """Get location statistics."""
    permission_classes = [AllowAny]

    def get(self, request):
        stats = LocationService.get_statistics()
        return Response(stats)
