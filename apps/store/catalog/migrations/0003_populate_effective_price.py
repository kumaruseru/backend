# Generated data migration to populate effective_price for existing products

from django.db import migrations
from django.utils import timezone


def update_effective_prices(apps, schema_editor):
    """
    Populate effective_price for all existing products.
    """
    Product = apps.get_model('catalog', 'Product')
    
    now = timezone.now()
    
    for product in Product.objects.all().iterator():
        # Determine if sale is currently active
        is_sale_active = False
        
        if product.sale_price and product.sale_price > 0:
            if product.price and product.sale_price < product.price:
                # Check sale dates
                sale_start_ok = product.sale_start is None or now >= product.sale_start
                sale_end_ok = product.sale_end is None or now <= product.sale_end
                
                if sale_start_ok and sale_end_ok:
                    is_sale_active = True
        
        # Set effective price
        if is_sale_active:
            product.effective_price = product.sale_price
        else:
            product.effective_price = product.price
        
        product.save(update_fields=['effective_price'])


def reverse_update(apps, schema_editor):
    """Reverse migration - set all to 0."""
    Product = apps.get_model('catalog', 'Product')
    Product.objects.all().update(effective_price=0)


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_add_effective_price'),
    ]

    operations = [
        migrations.RunPython(update_effective_prices, reverse_update),
    ]
