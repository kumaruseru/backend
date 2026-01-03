"""
Celery Configuration for OWLS Backend.

Production-ready Celery setup with:
- Redis broker
- Result backend
- Task routing by domain
- Scheduled tasks (Beat)
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Create Celery app
app = Celery('backend')

# Configure from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all registered apps
app.autodiscover_tasks()


# ==================== Task Configuration ====================

app.conf.update(
    # Broker settings
    broker_connection_retry_on_startup=True,
    
    # Result backend
    result_expires=3600,  # 1 hour
    
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes
    
    # Retry policy
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Worker configuration
    worker_prefetch_multiplier=4,
    worker_concurrency=4,
    
    # Task routing by domain
    task_routes={
        # Users domain
        'apps.users.identity.tasks.*': {'queue': 'users'},
        'apps.users.notifications.tasks.*': {'queue': 'users'},
        'apps.users.security.tasks.*': {'queue': 'users'},
        'apps.users.social.tasks.*': {'queue': 'users'},
        
        # Commerce domain
        'apps.commerce.orders.tasks.*': {'queue': 'commerce'},
        'apps.commerce.billing.tasks.*': {'queue': 'commerce'},
        'apps.commerce.shipping.tasks.*': {'queue': 'commerce'},
        'apps.commerce.cart.tasks.*': {'queue': 'commerce'},
        'apps.commerce.returns.tasks.*': {'queue': 'commerce'},
        
        # Store domain
        'apps.store.catalog.tasks.*': {'queue': 'store'},
        'apps.store.inventory.tasks.*': {'queue': 'store'},
        'apps.store.reviews.tasks.*': {'queue': 'store'},
        'apps.store.wishlist.tasks.*': {'queue': 'store'},
        'apps.store.marketing.tasks.*': {'queue': 'store'},
        
        # Default
        '*': {'queue': 'default'},
    },
    
    # ==================== Scheduled Tasks (Celery Beat) ====================
    beat_schedule={
        # ===== Users Domain =====
        # Identity
        'cleanup-expired-sessions': {
            'task': 'apps.users.identity.tasks.cleanup_expired_sessions',
            'schedule': crontab(minute=0),  # Every hour
        },
        'process-account-deletions': {
            'task': 'apps.users.identity.tasks.process_scheduled_deletions',
            'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        'send-deletion-reminders': {
            'task': 'apps.users.identity.tasks.send_deletion_reminders',
            'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
        },
        'cleanup-login-history': {
            'task': 'apps.users.identity.tasks.cleanup_old_login_history',
            'schedule': crontab(day_of_week=0, hour=3, minute=0),  # Weekly Sunday 3 AM
        },
        
        # ===== Commerce Domain =====
        # Shipping
        'sync-pending-shipments': {
            'task': 'apps.commerce.shipping.tasks.sync_all_pending_shipments',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes
        },
        
        # Cart
        'cleanup-guest-carts': {
            'task': 'apps.commerce.cart.tasks.cleanup_old_guest_carts_task',
            'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
        },
        'send-cart-reminders': {
            'task': 'apps.commerce.cart.tasks.send_abandoned_cart_reminders',
            'schedule': crontab(hour=10, minute=0),  # Daily at 10 AM
        },
        
        # Orders
        'auto-complete-orders': {
            'task': 'apps.commerce.orders.tasks.auto_complete_delivered_orders',
            'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
        },
        'send-review-reminders': {
            'task': 'apps.commerce.orders.tasks.send_review_reminders',
            'schedule': crontab(hour=11, minute=0),  # Daily at 11 AM
        },
        
        # Billing
        'check-pending-payments': {
            'task': 'apps.commerce.billing.tasks.check_pending_payments',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
        },
        
        # ===== Store Domain =====
        # Inventory
        'sync-inventory': {
            'task': 'apps.store.inventory.tasks.sync_inventory_counts',
            'schedule': crontab(hour='*/4'),  # Every 4 hours
        },
        'check-low-stock': {
            'task': 'apps.store.inventory.tasks.check_low_stock_alerts',
            'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
        },
        
        # Wishlist
        'send-price-drop-alerts': {
            'task': 'apps.store.wishlist.tasks.send_price_drop_notifications',
            'schedule': crontab(hour=12, minute=0),  # Daily at noon
        },
        'send-back-in-stock-alerts': {
            'task': 'apps.store.wishlist.tasks.send_back_in_stock_notifications',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes
        },
        
        # Reviews
        'update-product-ratings': {
            'task': 'apps.store.reviews.tasks.update_product_rating_summaries',
            'schedule': crontab(hour='*/6'),  # Every 6 hours
        },
        
        # Marketing
        'expire-promotions': {
            'task': 'apps.store.marketing.tasks.expire_ended_promotions',
            'schedule': crontab(minute=0),  # Every hour
        },
        'send-newsletter': {
            'task': 'apps.store.marketing.tasks.send_scheduled_newsletters',
            'schedule': crontab(hour=14, minute=0),  # Daily at 2 PM
        },
    },
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing."""
    print(f'Request: {self.request!r}')
