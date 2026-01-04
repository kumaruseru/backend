
import os
import django
import sys
from pathlib import Path

# Setup Django environment
sys.path.append(str(Path("c:/Users/nghia/Owls1/backend")))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Cleanup unused files
files_to_delete = [
    "apps/common/core/admin.py",
    "apps/common/core/tests.py",
    "apps/common/core/views.py"
]
print(">>> Cleaning up unused files...")
for file_path in files_to_delete:
    full_path = Path("c:/Users/nghia/Owls1/backend") / file_path
    if full_path.exists():
        try:
            os.remove(full_path)
            print(f"Deleted: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
    else:
        print(f"Already deleted: {file_path}")

django.setup()

from apps.common.core.utils import normalize_phone, format_phone_display, generate_slug_from_vietnamese
from apps.common.core.storage import get_upload_path, user_avatar_path, product_image_path
from apps.common.core.models import SluggedMixin

print(">>> Verifying Utils")
print(f"Normalize 0901234567: {normalize_phone('0901234567')}")
print(f"Format +84901234567: {format_phone_display('+84901234567')}")
print(f"Slug 'Sản phẩm mới': {generate_slug_from_vietnamese('Sản phẩm mới')}")

assert normalize_phone('0901234567') == '+84901234567'
assert generate_slug_from_vietnamese('Sản phẩm mới') == 'san-pham-moi'

print("\n>>> Verifying Storage Factory")
class MockInstance:
    id = 123
    product_id = 999
    slug = 'test-slug'

instance = MockInstance()
print(f"Avatar Path: {user_avatar_path(instance, 'test.jpg')}")
print(f"Product Path: {product_image_path(instance, 'prod.png')}")

assert 'avatars/123/' in user_avatar_path(instance, 'test.jpg')
assert 'products/999/' in product_image_path(instance, 'prod.png')

print("\n>>> Verification Successful!")
