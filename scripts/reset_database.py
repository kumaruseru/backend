"""
Database Reset Script.

Drops all tables and recreates the database schema.
USE WITH CAUTION - This will delete all data!

Usage:
    python scripts/reset_database.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection
from django.core.management import call_command


def reset_database():
    """Reset the database by dropping all tables and re-running migrations."""
    
    print("=" * 50)
    print("⚠️  DATABASE RESET SCRIPT")
    print("=" * 50)
    print("\nThis will DELETE ALL DATA in the database!")
    
    confirm = input("\nType 'yes' to confirm: ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return
    
    print("\n🗑️  Dropping all tables...")
    
    with connection.cursor() as cursor:
        # Get all table names
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        if tables:
            # Drop tables using CASCADE (no special permissions needed)
            for table in tables:
                try:
                    print(f"  Dropping {table}...")
                    cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                except Exception as e:
                    print(f"    Warning: {e}")
            
            print(f"\n✅ Dropped {len(tables)} tables")
        else:
            print("  No tables found")
    
    print("\n📦 Running migrations...")
    call_command('migrate', '--run-syncdb')
    
    print("\n✅ Database reset complete!")
    print("=" * 50)


if __name__ == '__main__':
    reset_database()
