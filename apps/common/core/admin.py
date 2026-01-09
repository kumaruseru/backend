"""Common Core - Admin Registration for Address Models."""
from django.contrib import admin
from django.contrib.sites.admin import SiteAdmin as DefaultSiteAdmin
from django.contrib.sites.models import Site
from unfold.admin import ModelAdmin
from .addresses import Province, District, Ward


admin.site.unregister(Site)


@admin.register(Site)
class SiteAdmin(ModelAdmin):
    list_display = ['domain', 'name']
    search_fields = ['domain', 'name']
    ordering = ['domain']


@admin.register(Province)
class ProvinceAdmin(ModelAdmin):
    list_display = ['name', 'ghn_id', 'code']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(District)
class DistrictAdmin(ModelAdmin):
    list_display = ['name', 'province_name', 'ghn_id']
    list_filter = ['province']
    search_fields = ['name', 'province__name']
    raw_id_fields = ['province']
    ordering = ['province__name', 'name']
    list_select_related = ['province']

    @admin.display(description='Province', ordering='province__name')
    def province_name(self, obj):
        return obj.province.name if obj.province else '-'


@admin.register(Ward)
class WardAdmin(ModelAdmin):
    list_display = ['name', 'district_name', 'province_name', 'ghn_code']
    list_filter = ['district__province']
    search_fields = ['name', 'district__name', 'district__province__name']
    raw_id_fields = ['district']
    ordering = ['district__province__name', 'district__name', 'name']
    list_select_related = ['district', 'district__province']

    @admin.display(description='District', ordering='district__name')
    def district_name(self, obj):
        return obj.district.name if obj.district else '-'

    @admin.display(description='Province', ordering='district__province__name')
    def province_name(self, obj):
        return obj.district.province.name if obj.district and obj.district.province else '-'
