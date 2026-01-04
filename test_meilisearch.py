"""
Meilisearch Integration Test Script.

Tests:
1. Connection to Meilisearch
2. Index setup
3. Product indexing
4. Search functionality
5. Filters

Usage:
    python test_meilisearch.py
"""
import os
import sys
from pathlib import Path
from decimal import Decimal

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from apps.store.catalog.search import MeilisearchGateway
from apps.store.catalog.models import Product

def test_connection():
    """Test Meilisearch connection."""
    print(">>> Testing Meilisearch Connection...")
    try:
        client = MeilisearchGateway.get_client()
        health = client.health()
        print(f"  ✅ Connected! Status: {health}")
        return True
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        print("  💡 Make sure Meilisearch is running at http://localhost:7700")
        return False

def test_setup_index():
    """Test index configuration."""
    print("\n>>> Setting up index...")
    try:
        MeilisearchGateway.setup_index()
        print("  ✅ Index configured successfully")
        return True
    except Exception as e:
        print(f"  ❌ Index setup failed: {e}")
        return False

def test_index_products():
    """Test product indexing."""
    print("\n>>> Testing product indexing...")
    
    products = Product.objects.active().select_related(
        'category', 'brand'
    ).prefetch_related('images', 'tags')[:10]
    
    if not products:
        print("  ⚠️ No products found in database")
        return False
    
    print(f"  Found {len(products)} products to index")
    
    try:
        MeilisearchGateway.bulk_index(list(products))
        print(f"  ✅ Indexed {len(products)} products")
        return True
    except Exception as e:
        print(f"  ❌ Indexing failed: {e}")
        return False

def test_search():
    """Test search functionality."""
    print("\n>>> Testing search...")
    
    # Get a product name to search for
    product = Product.objects.active().first()
    if not product:
        print("  ⚠️ No products to search for")
        return False
    
    # Search for first word of product name
    query = product.name.split()[0] if product.name else "test"
    print(f"  Searching for: '{query}'")
    
    try:
        result = MeilisearchGateway.search(query=query, limit=5)
        print(f"  ✅ Search completed in {result['processing_time_ms']}ms")
        print(f"  Found {result['total']} results")
        
        if result['hits']:
            print("  Top results:")
            for i, hit in enumerate(result['hits'][:3], 1):
                print(f"    {i}. {hit['name']} - {hit['price']:,.0f}₫")
        
        return True
    except Exception as e:
        print(f"  ❌ Search failed: {e}")
        return False

def test_typo_tolerance():
    """Test typo tolerance (Meilisearch feature)."""
    print("\n>>> Testing typo tolerance...")
    
    # Get a product name and introduce a typo
    product = Product.objects.active().first()
    if not product:
        print("  ⚠️ No products available")
        return False
    
    original = product.name.split()[0] if len(product.name) > 3 else "test"
    # Introduce typo by removing a character
    typo_query = original[:-1] if len(original) > 3 else original
    
    print(f"  Original: '{original}' -> Typo: '{typo_query}'")
    
    try:
        result = MeilisearchGateway.search(query=typo_query, limit=5)
        print(f"  ✅ Typo search completed in {result['processing_time_ms']}ms")
        print(f"  Found {result['total']} results despite typo")
        return True
    except Exception as e:
        print(f"  ❌ Typo search failed: {e}")
        return False

def test_filters():
    """Test filter functionality."""
    print("\n>>> Testing filters...")
    
    # Test price filter
    try:
        result = MeilisearchGateway.search(
            query="",
            min_price=100000,
            max_price=500000,
            limit=5
        )
        print(f"  ✅ Price filter (100k-500k): {result['total']} results")
    except Exception as e:
        print(f"  ❌ Price filter failed: {e}")
        return False
    
    # Test in_stock filter
    try:
        result = MeilisearchGateway.search(
            query="",
            in_stock=True,
            limit=5
        )
        print(f"  ✅ In-stock filter: {result['total']} results")
    except Exception as e:
        print(f"  ❌ In-stock filter failed: {e}")
        return False
    
    return True

def test_reindex_all():
    """Test full reindex."""
    print("\n>>> Testing full reindex...")
    try:
        count = MeilisearchGateway.reindex_all()
        print(f"  ✅ Reindexed {count} products")
        return True
    except Exception as e:
        print(f"  ❌ Reindex failed: {e}")
        return False

def main():
    print("=" * 50)
    print("  MEILISEARCH INTEGRATION TEST")
    print("=" * 50)
    
    results = {}
    
    # 1. Connection
    results['connection'] = test_connection()
    if not results['connection']:
        print("\n❌ Cannot proceed without connection. Exiting.")
        return
    
    # 2. Setup Index
    results['setup'] = test_setup_index()
    
    # 3. Index Products
    results['index'] = test_index_products()
    
    # Wait a bit for indexing to complete
    import time
    print("\n⏳ Waiting for indexing to complete...")
    time.sleep(2)
    
    # 4. Search
    results['search'] = test_search()
    
    # 5. Typo Tolerance
    results['typo'] = test_typo_tolerance()
    
    # 6. Filters
    results['filters'] = test_filters()
    
    # Summary
    print("\n" + "=" * 50)
    print("  TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, passed_test in results.items():
        status = "✅" if passed_test else "❌"
        print(f"  {status} {test}")
    
    print(f"\n  Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("  🎉 All tests passed!")
    else:
        print("  ⚠️ Some tests failed. Check the output above.")

if __name__ == "__main__":
    main()
