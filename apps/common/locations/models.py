"""Common Locations - Administrative Units Models.

Vietnamese administrative units (Province/District/Ward) with full support for:
- search_slug for accent-insensitive search
- path/path_with_type for full hierarchy
- Shipping integration (GHN, GHTK)
"""
from django.db import models


class Province(models.Model):
    """Vietnamese Province (Tỉnh/Thành phố)."""
    code = models.CharField(max_length=20, unique=True, db_index=True, verbose_name='Code')
    name = models.CharField(max_length=100, verbose_name='Name')
    name_with_type = models.CharField(max_length=150, verbose_name='Full Name')
    slug = models.SlugField(max_length=100, blank=True, db_index=True)
    type = models.CharField(max_length=30, blank=True, verbose_name='Type')
    
    # For accent-insensitive search (from hanhchinhvn)
    search_slug = models.CharField(max_length=150, blank=True, db_index=True, verbose_name='Search Slug')
    
    # Full path hierarchy
    path = models.CharField(max_length=255, blank=True, verbose_name='Path')
    path_with_type = models.CharField(max_length=300, blank=True, verbose_name='Full Path')
    
    # For shipping integration (GHN, GHTK, etc.)
    ghn_id = models.IntegerField(null=True, blank=True, verbose_name='GHN Province ID')
    ghtk_id = models.CharField(max_length=20, blank=True, verbose_name='GHTK Province ID')
    
    is_active = models.BooleanField(default=True, verbose_name='Active')
    sort_order = models.IntegerField(default=0, verbose_name='Sort Order')

    class Meta:
        verbose_name = 'Province'
        verbose_name_plural = 'Provinces'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['search_slug']),
        ]

    def __str__(self) -> str:
        return self.name_with_type or self.name

    @property
    def district_count(self) -> int:
        return self.districts.count()


class District(models.Model):
    """Vietnamese District (Quận/Huyện)."""
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='districts', verbose_name='Province')
    code = models.CharField(max_length=20, unique=True, db_index=True, verbose_name='Code')
    name = models.CharField(max_length=100, verbose_name='Name')
    name_with_type = models.CharField(max_length=150, verbose_name='Full Name')
    slug = models.SlugField(max_length=100, blank=True, db_index=True)
    type = models.CharField(max_length=30, blank=True, verbose_name='Type')
    
    # For accent-insensitive search
    search_slug = models.CharField(max_length=150, blank=True, db_index=True, verbose_name='Search Slug')
    
    # Full path hierarchy
    path = models.CharField(max_length=255, blank=True, verbose_name='Path')
    path_with_type = models.CharField(max_length=300, blank=True, verbose_name='Full Path')
    
    # For shipping integration
    ghn_id = models.IntegerField(null=True, blank=True, verbose_name='GHN District ID')
    ghtk_id = models.CharField(max_length=20, blank=True, verbose_name='GHTK District ID')
    
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'District'
        verbose_name_plural = 'Districts'
        ordering = ['province', 'name']
        indexes = [
            models.Index(fields=['province', 'name']),
            models.Index(fields=['search_slug']),
        ]

    def __str__(self) -> str:
        return self.name_with_type or self.name

    @property
    def ward_count(self) -> int:
        return self.wards.count()


class Ward(models.Model):
    """Vietnamese Ward (Phường/Xã/Thị trấn)."""
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='wards', verbose_name='District')
    code = models.CharField(max_length=20, unique=True, db_index=True, verbose_name='Code')
    name = models.CharField(max_length=100, verbose_name='Name')
    name_with_type = models.CharField(max_length=150, verbose_name='Full Name')
    slug = models.SlugField(max_length=100, blank=True, db_index=True)
    type = models.CharField(max_length=30, blank=True, verbose_name='Type')
    
    # For accent-insensitive search
    search_slug = models.CharField(max_length=150, blank=True, db_index=True, verbose_name='Search Slug')
    
    # Full path hierarchy
    path = models.CharField(max_length=255, blank=True, verbose_name='Path')
    path_with_type = models.CharField(max_length=500, blank=True, verbose_name='Full Path')
    
    # For shipping integration
    ghn_code = models.CharField(max_length=20, blank=True, verbose_name='GHN Ward Code')
    ghtk_id = models.CharField(max_length=20, blank=True, verbose_name='GHTK Ward ID')
    
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Ward'
        verbose_name_plural = 'Wards'
        ordering = ['district', 'name']
        indexes = [
            models.Index(fields=['district', 'name']),
            models.Index(fields=['search_slug']),
        ]

    def __str__(self) -> str:
        return self.name_with_type or self.name

    @property
    def full_address(self) -> str:
        """Get full address: Ward, District, Province."""
        return f"{self.name_with_type}, {self.district.name_with_type}, {self.district.province.name_with_type}"

    @property
    def province(self):
        """Shortcut to get province."""
        return self.district.province
