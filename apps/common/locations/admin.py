"""Common Locations - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import Province, District, Ward


@admin.register(Province)
class ProvinceAdmin(ModelAdmin):
    list_display = ['code', 'name_with_type', 'district_count_display', 'ghn_id', 'is_active', 'sort_order']
    list_filter = ['is_active', 'type']
    search_fields = ['code', 'name', 'name_with_type']
    list_editable = ['is_active', 'sort_order']
    ordering = ['sort_order', 'name']

    fieldsets = (
        ('Basic Info', {'fields': ('code', 'name', 'name_with_type', 'slug', 'type')}),
        ('Shipping Integration', {'fields': ('ghn_id', 'ghtk_id'), 'classes': ('collapse',)}),
        ('Settings', {'fields': ('is_active', 'sort_order')}),
    )

    @admin.display(description='Districts')
    def district_count_display(self, obj):
        count = obj.districts.count()
        return format_html('<span style="font-weight: bold;">{}</span>', count)


@admin.register(District)
class DistrictAdmin(ModelAdmin):
    list_display = ['code', 'name_with_type', 'province', 'ward_count_display', 'ghn_id', 'is_active']
    list_filter = ['is_active', 'province', 'type']
    search_fields = ['code', 'name', 'name_with_type', 'province__name']
    list_editable = ['is_active']
    raw_id_fields = ['province']
    autocomplete_fields = ['province']
    ordering = ['province', 'name']

    fieldsets = (
        ('Basic Info', {'fields': ('province', 'code', 'name', 'name_with_type', 'slug', 'type')}),
        ('Shipping Integration', {'fields': ('ghn_id', 'ghtk_id'), 'classes': ('collapse',)}),
        ('Settings', {'fields': ('is_active',)}),
    )

    @admin.display(description='Wards')
    def ward_count_display(self, obj):
        count = obj.wards.count()
        return format_html('<span style="font-weight: bold;">{}</span>', count)


@admin.register(Ward)
class WardAdmin(ModelAdmin):
    list_display = ['code', 'name_with_type', 'district', 'province_display', 'is_active']
    list_filter = ['is_active', 'district__province', 'type']
    search_fields = ['code', 'name', 'name_with_type', 'district__name', 'district__province__name']
    list_editable = ['is_active']
    raw_id_fields = ['district']
    autocomplete_fields = ['district']
    ordering = ['district', 'name']

    fieldsets = (
        ('Basic Info', {'fields': ('district', 'code', 'name', 'name_with_type', 'slug', 'type')}),
        ('Shipping Integration', {'fields': ('ghn_code', 'ghtk_id'), 'classes': ('collapse',)}),
        ('Settings', {'fields': ('is_active',)}),
    )

    @admin.display(description='Province')
    def province_display(self, obj):
        return obj.district.province.name_with_type
