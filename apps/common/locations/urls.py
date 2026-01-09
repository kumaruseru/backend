"""Common Locations - URL Configuration."""
from django.urls import path
from .views import (
    ProvinceListView, ProvinceDetailView,
    DistrictListView, DistrictDetailView,
    WardListView, WardDetailView,
    LocationSearchView, AutocompleteView,
    FullAddressResolveView, ValidateAddressView,
    StatisticsView,
)

app_name = 'locations'

urlpatterns = [
    # Provinces
    path('provinces/', ProvinceListView.as_view(), name='province-list'),
    path('provinces/<str:code>/', ProvinceDetailView.as_view(), name='province-detail'),
    
    # Districts
    path('provinces/<str:province_code>/districts/', DistrictListView.as_view(), name='district-list'),
    path('districts/<str:code>/', DistrictDetailView.as_view(), name='district-detail'),
    
    # Wards
    path('districts/<str:district_code>/wards/', WardListView.as_view(), name='ward-list'),
    path('wards/<str:code>/', WardDetailView.as_view(), name='ward-detail'),
    
    # Search & Autocomplete
    path('search/', LocationSearchView.as_view(), name='location-search'),
    path('autocomplete/', AutocompleteView.as_view(), name='autocomplete'),
    
    # Utilities
    path('resolve/<str:ward_code>/', FullAddressResolveView.as_view(), name='resolve-address'),
    path('validate/', ValidateAddressView.as_view(), name='validate-address'),
    path('statistics/', StatisticsView.as_view(), name='statistics'),
]
