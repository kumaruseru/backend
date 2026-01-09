"""Sync Vietnam addresses from GHN API."""
import os
import requests
from django.core.management.base import BaseCommand
from apps.common.core.addresses import Province, District, Ward


class Command(BaseCommand):
    help = 'Sync Vietnam Province/District/Ward from GHN API'

    GHN_API_URL = 'https://online-gateway.ghn.vn/shiip/public-api/master-data'
    
    def get_headers(self):
        token = os.getenv('GHN_API_TOKEN', '')
        if not token:
            self.stdout.write(self.style.WARNING('GHN_API_TOKEN not found in environment!'))
        return {
            'Token': token,
            'Content-Type': 'application/json'
        }

    def handle(self, *args, **options):
        self.stdout.write('Syncing Vietnam addresses from GHN API...')
        
        # Sync Provinces
        self.sync_provinces()
        
        # Sync Districts
        self.sync_districts()
        
        # Sync Wards
        self.sync_wards()
        
        self.stdout.write(self.style.SUCCESS('Sync completed!'))

    def sync_provinces(self):
        self.stdout.write('Syncing provinces...')
        try:
            response = requests.get(f'{self.GHN_API_URL}/province', headers=self.get_headers(), timeout=30)
            data = response.json()
            
            if data.get('code') == 200:
                provinces = data.get('data', [])
                for p in provinces:
                    Province.objects.update_or_create(
                        ghn_id=p['ProvinceID'],
                        defaults={
                            'name': p.get('ProvinceName', ''),
                            'name_extension': p.get('NameExtension', []),
                            'code': p.get('Code', '')
                        }
                    )
                self.stdout.write(f'  Synced {len(provinces)} provinces')
            else:
                self.stdout.write(self.style.ERROR(f'  API Error: {data.get("message")}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error: {e}'))

    def sync_districts(self):
        self.stdout.write('Syncing districts...')
        provinces = Province.objects.all()
        total = 0
        
        for province in provinces:
            try:
                response = requests.post(
                    f'{self.GHN_API_URL}/district',
                    headers=self.get_headers(),
                    json={'province_id': province.ghn_id},
                    timeout=30
                )
                data = response.json()
                
                if data.get('code') == 200:
                    districts = data.get('data', [])
                    for d in districts:
                        District.objects.update_or_create(
                            ghn_id=d['DistrictID'],
                            defaults={
                                'province': province,
                                'name': d.get('DistrictName', ''),
                                'name_extension': d.get('NameExtension', []),
                                'support_type': d.get('SupportType', 0)
                            }
                        )
                    total += len(districts)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Error syncing {province.name}: {e}'))
        
        self.stdout.write(f'  Synced {total} districts')

    def sync_wards(self):
        self.stdout.write('Syncing wards...')
        districts = District.objects.all()
        total = 0
        
        for district in districts:
            try:
                response = requests.post(
                    f'{self.GHN_API_URL}/ward',
                    headers=self.get_headers(),
                    json={'district_id': district.ghn_id},
                    timeout=30
                )
                data = response.json()
                
                if data.get('code') == 200:
                    wards = data.get('data', []) or []
                    for w in wards:
                        Ward.objects.update_or_create(
                            ghn_code=str(w['WardCode']),
                            defaults={
                                'district': district,
                                'name': w.get('WardName', ''),
                                'name_extension': w.get('NameExtension', []),
                                'support_type': w.get('SupportType', 0)
                            }
                        )
                    total += len(wards)
            except Exception as e:
                pass  # Some districts don't have wards
        
        self.stdout.write(f'  Synced {total} wards')
