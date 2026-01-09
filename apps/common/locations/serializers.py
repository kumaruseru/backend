"""Common Locations - Serializers."""
from rest_framework import serializers
from .models import Province, District, Ward


class ProvinceSerializer(serializers.ModelSerializer):
    """Serializer for Province model."""

    class Meta:
        model = Province
        fields = [
            'code', 'name', 'name_with_type', 'slug', 'type',
            'search_slug', 'ghn_id', 'ghtk_id'
        ]


class ProvinceMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for Province (for nested use)."""

    class Meta:
        model = Province
        fields = ['code', 'name', 'name_with_type']


class DistrictSerializer(serializers.ModelSerializer):
    """Serializer for District model."""
    province_code = serializers.CharField(source='province.code', read_only=True)
    province_name = serializers.CharField(source='province.name_with_type', read_only=True)

    class Meta:
        model = District
        fields = [
            'code', 'name', 'name_with_type', 'slug', 'type',
            'search_slug', 'province_code', 'province_name',
            'ghn_id', 'ghtk_id'
        ]


class DistrictMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for District (for nested use)."""

    class Meta:
        model = District
        fields = ['code', 'name', 'name_with_type']


class WardSerializer(serializers.ModelSerializer):
    """Serializer for Ward model."""
    district_code = serializers.CharField(source='district.code', read_only=True)
    district_name = serializers.CharField(source='district.name_with_type', read_only=True)
    province_code = serializers.CharField(source='district.province.code', read_only=True)
    province_name = serializers.CharField(source='district.province.name_with_type', read_only=True)
    full_address = serializers.CharField(read_only=True)

    class Meta:
        model = Ward
        fields = [
            'code', 'name', 'name_with_type', 'slug', 'type',
            'search_slug', 'district_code', 'district_name',
            'province_code', 'province_name', 'full_address',
            'ghn_code', 'ghtk_id'
        ]


class WardMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for Ward (for nested use)."""

    class Meta:
        model = Ward
        fields = ['code', 'name', 'name_with_type']


class FullAddressSerializer(serializers.Serializer):
    """Serializer for full address response."""
    ward = WardSerializer()
    district = DistrictSerializer()
    province = ProvinceSerializer()
    full_address = serializers.CharField()


class AutocompleteResultSerializer(serializers.Serializer):
    """Serializer for autocomplete results."""
    code = serializers.CharField()
    name = serializers.CharField()
    type = serializers.CharField()  # 'province', 'district', 'ward'
    parent = serializers.DictField(allow_null=True)


class AddressInputSerializer(serializers.Serializer):
    """
    Serializer for address input validation.
    Used by other modules (checkout, user address, etc.)
    """
    province_code = serializers.CharField(max_length=20)
    district_code = serializers.CharField(max_length=20)
    ward_code = serializers.CharField(max_length=20)
    street_address = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        from .services import LocationService
        
        is_valid = LocationService.validate_address_hierarchy(
            data['province_code'],
            data['district_code'],
            data['ward_code']
        )
        
        if not is_valid:
            raise serializers.ValidationError(
                'Invalid address hierarchy. Ward must belong to the specified district and province.'
            )
        
        return data

    def get_full_address(self, include_street: bool = True) -> str:
        """Get formatted full address string."""
        from .services import LocationSelector
        
        ward = LocationSelector.get_ward_by_code(self.validated_data['ward_code'])
        if not ward:
            return ''
        
        full_addr = ward.full_address
        street = self.validated_data.get('street_address', '')
        
        if include_street and street:
            return f"{street}, {full_addr}"
        return full_addr
