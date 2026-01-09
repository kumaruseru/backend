"""Vietnam Address Models - Province, District, Ward."""
from django.db import models


class Province(models.Model):
    """Vietnam Province/City from GHN API."""
    
    ghn_id = models.IntegerField(unique=True, db_index=True, verbose_name='GHN Province ID')
    name = models.CharField(max_length=100, verbose_name='Name')
    name_extension = models.JSONField(default=list, blank=True, verbose_name='Name Extensions')
    code = models.CharField(max_length=20, blank=True, verbose_name='Code')
    
    class Meta:
        verbose_name = 'Province'
        verbose_name_plural = 'Provinces'
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name


class District(models.Model):
    """Vietnam District from GHN API."""
    
    ghn_id = models.IntegerField(unique=True, db_index=True, verbose_name='GHN District ID')
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='districts', verbose_name='Province')
    name = models.CharField(max_length=100, verbose_name='Name')
    name_extension = models.JSONField(default=list, blank=True, verbose_name='Name Extensions')
    support_type = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'District'
        verbose_name_plural = 'Districts'
        ordering = ['name']
    
    def __str__(self) -> str:
        return f"{self.name}, {self.province.name}"


class Ward(models.Model):
    """Vietnam Ward from GHN API."""
    
    ghn_code = models.CharField(max_length=20, unique=True, db_index=True, verbose_name='GHN Ward Code')
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='wards', verbose_name='District')
    name = models.CharField(max_length=100, verbose_name='Name')
    name_extension = models.JSONField(default=list, blank=True, verbose_name='Name Extensions')
    support_type = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Ward'
        verbose_name_plural = 'Wards'
        ordering = ['name']
    
    def __str__(self) -> str:
        return f"{self.name}, {self.district.name}"
