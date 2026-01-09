"""
Django settings for OWLS E-Commerce Backend.
Architecture: Domain-Driven Design (DDD)
UI Theme: Django Unfold (Tailwind CSS) + Dashboard
Mode: STRICT PRODUCTION PREPARED

This settings file is configured for:
1. High Security: 2FA, CSP, HSTS, Secure Cookies, Brute-force protection, Input Sanitization.
2. Performance: Redis Caching, Connection Pooling, Celery Async Tasks, ORM Caching (Cacheops).
3. Scalability: R2 Cloud Storage, MeiliSearch, Docker-ready, WebSockets (Channels).
4. UX/UI: Django Unfold Admin with Custom Dashboard & Sidebar.
"""

import os
import sys
import environ
import sentry_sdk
from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab
from django.utils.translation import gettext_lazy as _

# --- THIRD PARTY INTEGRATIONS ---
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from django_guid.integrations import SentryIntegration

# --- ENVIRONMENT CONFIGURATION ---
env = environ.Env()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(BASE_DIR / '.env')

# Add 'apps' to sys.path to allow cleaner imports
sys.path.append(str(BASE_DIR / 'apps'))

# --- CORE SECURITY SETTINGS ---
SECRET_KEY = env('DJANGO_SECRET_KEY')
# CRITICAL: False in production to prevent leaking internals
DEBUG = env.bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS')

# Data Encryption Keys (Rotatable)
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY')
FIELD_ENCRYPTION_KEY_PREVIOUS = env.list('FIELD_ENCRYPTION_KEY_PREVIOUS', default=[])

# --- APPLICATION DEFINITION ---
ROOT_URLCONF = 'backend.urls'
# [UPDATED] Switch to ASGI for Channels/WebSockets support
ASGI_APPLICATION = 'backend.asgi.application'
WSGI_APPLICATION = 'backend.wsgi.application' # Fallback
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SITE_ID = 1

# --- INSTALLED APPS CONFIGURATION ---
DJANGO_APPS = [
    'daphne',                       # ASGI Server (Must be at the top)

    # [UPDATED] Unfold Admin Theme (Must be before admin)
    "unfold",
    "unfold.contrib.filters",       # Hỗ trợ filter đẹp hơn
    "unfold.contrib.forms",         # Hỗ trợ form widget đẹp hơn
    "unfold.contrib.import_export", # Tích hợp nút import/export vào giao diện mới
    "unfold.contrib.guardian",      # Tích hợp Object permission vào giao diện mới
    "unfold.contrib.simple_history", # Lịch sử thay đổi
    "unfold.contrib.constance",     # Constance integration với Unfold
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',         # Required for SEO/Sitemap
]

THIRD_PARTY_APPS = [
    # --- API & Networking ---
    'rest_framework',                # Django Rest Framework (DRF)
    'rest_framework_simplejwt',      # JWT Authentication
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',                   # CORS Handling
    'drf_spectacular',               # OpenAPI Schema (Swagger)
    'django_filters',                # URL Query Parameter Filtering
    'channels',                      # WebSockets (Real-time updates)

    # --- Storage & Files ---
    'storages',                      # AWS S3 / Cloudflare R2 Backend
    'django_cleanup.apps.CleanupConfig', # Auto-delete orphaned files
    'versatileimagefield',           # Advanced Image Processing

    # --- Security & Audit ---
    'django_guid',                   # Request Correlation ID (Tracing)
    'axes',                          # Brute-force protection
    'auditlog',                      # Model Change tracking
    'django_admin_trap',             # Fake Admin Login Honeypot
    'guardian',                      # Object-level Permissions
    'safedelete',                    # Soft Delete Support
    'csp',                           # Content Security Policy
    'django_permissions_policy',     # Browser Feature Policy
    'django_bleach',                 # HTML Sanitization
    'django_cryptography',           # Encrypted Fields (API Keys)
    'simple_history',                # [NEW] Track history for Unfold

    # --- 2FA (Two-Factor Authentication) ---
    'django_otp',
    'django_otp.plugins.otp_totp',   # Google Authenticator
    'django_otp.plugins.otp_static', # Backup Codes
    'two_factor',                    # 2FA UI Views

    # --- Async Tasks & Caching ---
    'django_celery_beat',            # Database-backed Periodic Tasks
    'django_celery_results',         # Database-backed Task Results
    'cacheops',                      # Automatic ORM Caching

    # --- E-Commerce Logic & Utilities ---
    'sequences',                     # Gapless Sequences (Invoice Numbers)
    'phonenumber_field',             # E.164 Phone Number Validation
    'djmoney',                       # Money & Currency Handling
    'django_countries',              # ISO Country List
    'import_export',                 # Admin Excel Import/Export
    'taggit',                        # Product Tags
    'treebeard',                     # Tree structure (Categories)
    'anymail',                       # Transactional Email API
    
    # --- Operations & Config ---
    'constance',                     # [NEW] Dynamic Configuration in Admin
    'constance.backends.database',   # Required for Constance DB
    'dbbackup',                      # [NEW] Database Backup
    'health_check',                  # [NEW] Health Checks
    'health_check.db',               # [NEW] Database Health Check
    'health_check.cache',            # [NEW] Cache Health Check
    'health_check.storage',          # [NEW] Storage Health Check
    'health_check.contrib.migrations', # [NEW] Migrations Health Check
    'health_check.contrib.celery',   # [NEW] Celery Health Check
    'health_check.contrib.redis',    # [NEW] Redis Health Check
    'health_check.contrib.psutil',   # [NEW] System Health Check
]

# [DELETED] Silk removed from here

LOCAL_APPS = [
    # --- 1. CORE & SHARED ---
    'apps.common.core',              # Core Utilities & Base Models
    'apps.common.locations',         # Locations & Address

    # --- 2. USERS & IDENTITY ---
    'apps.users.identity',           # User Model & Profile
    'apps.users.notifications',      # Notification System
    'apps.users.security',           # Security Logs & Settings
    'apps.users.social',             # Social Login

    # --- 3. STORE (INPUT) ---
    'apps.store.catalog',            # Products, Categories, Brands
    'apps.store.marketing',          # Coupons, Flash Sales
    'apps.store.reviews',            # Product Reviews
    'apps.store.wishlist',           # User Wishlists
    'apps.store.inventory',          # Stock Management

    # --- 4. COMMERCE (OUTPUT) ---
    'apps.commerce.cart',            # Shopping Cart
    'apps.commerce.orders',          # Order Management
    'apps.commerce.billing',         # Payments
    'apps.commerce.shipping',        # Shipping Integrations
    'apps.commerce.returns',         # Return Requests
    
    # [NEW] Analytics nằm ở đây vì nó tổng hợp kết quả của Giao dịch + Hàng hóa
    'apps.commerce.analytics',       # Dashboard, Sales Reports, Funnels
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --- MIDDLEWARE CONFIGURATION ---
MIDDLEWARE = [
    'django_guid.middleware.guid_middleware',               # 1. Correlation ID
    'corsheaders.middleware.CorsMiddleware',                # 2. CORS
    'django.middleware.security.SecurityMiddleware',        # 3. Security
    'django.middleware.gzip.GZipMiddleware',                # 4. GZip
]

# [DELETED] Silk Middleware removed from here

MIDDLEWARE += [
    'django.contrib.sessions.middleware.SessionMiddleware', # 5. Session
    'django.middleware.locale.LocaleMiddleware',            # 5.1 Language Switch
    'django.middleware.common.CommonMiddleware',            # 6. Common
    'django.middleware.csrf.CsrfViewMiddleware',            # 7. CSRF
    'django.contrib.auth.middleware.AuthenticationMiddleware', # 8. Auth
    'django_otp.middleware.OTPMiddleware',                  # 9. 2FA
    'axes.middleware.AxesMiddleware',                       # 10. Brute-force Check
    'csp.middleware.CSPMiddleware',                         # 11. CSP
    'django_permissions_policy.PermissionsPolicyMiddleware',# 12. Browser Permissions
    'django.contrib.messages.middleware.MessageMiddleware', # 13. Messages
    'django.middleware.clickjacking.XFrameOptionsMiddleware', # 14. Clickjacking
    'apps.common.utils.middleware.SecurityHeadersMiddleware', # 15. Custom Headers
    'apps.common.utils.middleware.RequestLoggingMiddleware',  # 16. Log Request
    'apps.common.utils.middleware.SuspiciousActivityMiddleware', # 17. Block Suspicious
    'apps.common.utils.middleware.Admin2FAEnforcementMiddleware', # 18. Force 2FA for Admin
    'simple_history.middleware.HistoryRequestMiddleware',     # 19. History Track
    'maintenance_mode.middleware.MaintenanceModeMiddleware',  # 20. Maintenance (Last)
]

# --- AUTHENTICATION BACKENDS ---
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',        # 1. Brute-force check
    'django.contrib.auth.backends.ModelBackend',  # 2. Default Django Auth
    'guardian.backends.ObjectPermissionBackend',  # 3. Object-level Permissions
]

# --- DJANGO-GUARDIAN SETTINGS ---
GUARDIAN_GET_INIT_ANONYMOUS_USER = None  # Disable auto-creation of AnonymousUser
ANONYMOUS_USER_NAME = None  # Disable anonymous user feature

AUTH_USER_MODEL = 'identity.User'

# --- PASSWORD SECURITY ---
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- DATABASE CONFIGURATION ---
DATABASES = {
    'default': env.db('DATABASE_URL'),
}
DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=600)
DATABASES['default']['ATOMIC_REQUESTS'] = True

# --- CACHE & SESSION (SEPARATE REDIS) ---
CACHES = {
    'default': env.cache('REDIS_CACHE_URL'),
    'sessions': env.cache('REDIS_SESSION_URL'),
}

# Cấu hình Session Engine sử dụng 'sessions' alias đã định nghĩa ở trên
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'

# --- ORM CACHING (CACHEOPS) ---
# Sử dụng REDIS_CACHE_URL (chung với default)
CACHEOPS_REDIS = env('REDIS_CACHE_URL')
CACHEOPS_DEFAULTS = {'timeout': 60 * 60}
CACHEOPS = {
    'sites.site': {'ops': 'all', 'timeout': 60 * 60 * 24},
    'identity.userpreferences': {'ops': 'get', 'timeout': 60 * 15},
    'catalog.*': {'ops': ('fetch', 'get'), 'timeout': 60 * 60},
    'inventory.*': {'ops': 'get', 'timeout': 60 * 5},
    'commerce.*': None,
}


# --- TEMPLATES ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'constance.context_processors.config',
            ],
        },
    },
]

# --- INTERNATIONALIZATION ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# Supported languages for admin interface
from django.utils.translation import gettext_lazy as _
LANGUAGES = [
    ('vi', _('Tiếng Việt')),
    ('en', _('English')),
]

# Path to locale files for translations
LOCALE_PATHS = [BASE_DIR / 'locale']

# --- API CONFIGURATION (DRF) ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticatedOrReadOnly',),
    'DEFAULT_PAGINATION_CLASS': 'apps.common.core.api.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'COERCE_DECIMAL_TO_STRING': True,
    'EXCEPTION_HANDLER': 'apps.common.core.api.handlers.custom_exception_handler',
    
    # Throttling
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': env('THROTTLE_RATE_ANON'),
        'user': env('THROTTLE_RATE_USER'),
        'login': '60/min',
        '2fa_confirm': '5/min',
        'cart_modify': '120/min',
        'order_create': '10/min',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# --- SWAGGER API DOCS ---
SPECTACULAR_SETTINGS = {
    'TITLE': 'OWLS E-Commerce API',
    'DESCRIPTION': 'API documentation for OWLS E-Commerce Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
}

# --- JWT CONFIGURATION ---
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env.int('JWT_ACCESS_MINUTES')),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env.int('JWT_REFRESH_DAYS')),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
}

# --- NETWORK SECURITY (CORS & CSRF) ---
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True

if CORS_ALLOW_CREDENTIALS:
    for origin in CORS_ALLOWED_ORIGINS:
        if origin == '*' or origin.startswith('*'):
            raise ValueError("SECURITY ERROR: CORS_ALLOWED_ORIGINS cannot contain '*' with credentials enabled.")

# --- BROWSER SECURITY HEADERS ---
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

# --- BRUTE FORCE PROTECTION (AXES) ---
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["ip_address", ["username", "user_agent"]]

# --- BROWSER FEATURES POLICY ---
PERMISSIONS_POLICY = {
    'accelerometer': [],
    'camera': [],
    'geolocation': [],
    'gyroscope': [],
    'magnetometer': [],
    'microphone': [],
    'payment': ['self'],  # Enable 'self' if needed for Stripe elements
    'usb': [],
    'interest-cohort': [],
}

# --- ID OBFUSCATION (HASHIDS) ---
HASHIDS_SALT = env('HASHIDS_SALT')
HASHIDS_MIN_LENGTH = 8
HASHIDS_ALPHABET = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'

# --- INPUT SANITIZATION (BLEACH) ---
BLEACH_ALLOWED_TAGS = ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'ul', 'ol', 'li', 'br', 'img']
BLEACH_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'title'],
    '*': ['class'],
}
BLEACH_STRIP_TAGS = True
BLEACH_STRIP_COMMENTS = True

# --- CURRENCY SETTINGS (DJMONEY) ---
CURRENCIES = ('VND', 'USD')
DEFAULT_CURRENCY = 'VND'

# --- CLOUD STORAGE (R2 / S3) ---
USE_S3 = env.bool('USE_S3', default=True)
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL')
AWS_S3_CUSTOM_DOMAIN = env('AWS_S3_CUSTOM_DOMAIN')
AWS_S3_REGION_NAME = 'auto'
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None

STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    "default": {"BACKEND": "apps.common.core.storage.MediaStorage"},
    "staticfiles": {"BACKEND": "apps.common.core.storage.StaticStorage"},
}
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# --- IMAGE PROCESSING ---
VERSATILEIMAGEFIELD_SETTINGS = {
    'cache_length': 2592000,
    'cache_name': 'versatileimagefield_cache',
    'jpeg_resize_quality': 85,
    'sized_directory_name': '__sized__',
    'filtered_directory_name': '__filtered__',
    'placeholder_directory_name': '__placeholder__',
    'create_images_on_demand': True,
    'progressive_jpeg': True,
}

# --- CONTENT SECURITY POLICY (CSP) ---
SECURITY_POLICY_DIRECTIVES = {
    'default-src': ["'self'"],
    'script-src': [
        "'self'",
        f"https://{AWS_S3_CUSTOM_DOMAIN}",
        "https://challenges.cloudflare.com",
        "https://cdn.jsdelivr.net",
        "'unsafe-inline'",
        "'unsafe-eval'",
    ],
    'style-src': [
        "'self'",
        f"https://{AWS_S3_CUSTOM_DOMAIN}",
        "https://cdn.jsdelivr.net",
        "https://fonts.googleapis.com",
        "'unsafe-inline'",
    ],
    'font-src': [
        "'self'",
        f"https://{AWS_S3_CUSTOM_DOMAIN}",
        "https://fonts.gstatic.com",
        "https://cdn.jsdelivr.net",
        "data:",
    ],
    'img-src': [
        "'self'",
        f"https://{AWS_S3_CUSTOM_DOMAIN}",
        "data:",
        "https:", 
    ],
    'connect-src': [
        "'self'",
        "https://challenges.cloudflare.com",
        f"https://{AWS_S3_CUSTOM_DOMAIN}",
        f"wss://{AWS_S3_CUSTOM_DOMAIN}", 
        "ws://localhost:8000",
    ],
    'frame-src': [
        "'self'",
        "https://challenges.cloudflare.com",
    ],
    'frame-ancestors': ["'none'"],
    'form-action': ["'self'"],
    'base-uri': ["'self'"],
    'report-uri': "/api/csp-report/",
}

if DEBUG:
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {'DIRECTIVES': SECURITY_POLICY_DIRECTIVES}
else:
    CONTENT_SECURITY_POLICY = {'DIRECTIVES': SECURITY_POLICY_DIRECTIVES}

# --- OBSERVABILITY & LOGGING (SENTRY + GUID) ---
DJANGO_GUID = {
    'GUID_HEADER_NAME': 'Correlation-ID',
    'VALIDATE_GUID': True,
    'RETURN_HEADER': True,
    'EXPOSE_HEADER': True,
    'INTEGRATIONS': [SentryIntegration()],
    'IGNORE_URLS': ['/health/', '/favicon.ico'],
    'UUID_FORMAT': 'hex',
}

SENTRY_DSN = env('SENTRY_DSN', default=None)
sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
        RedisIntegration(),
    ],
    traces_sample_rate=env.float('SENTRY_TRACES_SAMPLE_RATE', default=0.1),
    send_default_pii=False,
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'mask_sensitive': {'()': 'apps.common.utils.SensitiveDataFilter'},
        'correlation_id': {'()': 'django_guid.log_filters.CorrelationId'},
    },
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(levelname)s %(asctime)s %(correlation_id)s %(message)s %(pathname)s %(lineno)d',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['mask_sensitive', 'correlation_id'],
        },
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': env('DJANGO_LOG_LEVEL', default='INFO'), 'propagate': True},
        'apps': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
        'django_guid': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

# --- ASYNC TASKS (CELERY) ---
# [UPDATED] Sử dụng REDIS_BROKER_URL riêng
CELERY_BROKER_URL = env('REDIS_BROKER_URL')
CELERY_RESULT_BACKEND = env('REDIS_BROKER_URL') # Lưu result chung với broker

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 1800

CELERY_BEAT_SCHEDULE = {
    'sync-pending-shipments': {
        'task': 'apps.commerce.shipping.tasks.sync_all_pending_shipments',
        'schedule': crontab(minute='*/30'),
    },
    'cleanup-old-guest-carts': {
        'task': 'apps.commerce.cart.tasks.cleanup_old_guest_carts_task',
        'schedule': crontab(hour=3, minute=0),
    },
    # --- Analytics Tasks ---
    'aggregate-daily-metrics': {
        'task': 'apps.commerce.analytics.tasks.aggregate_daily_metrics',
        'schedule': crontab(hour=0, minute=30),  # Daily at 00:30
    },
    'generate-monthly-report': {
        'task': 'apps.commerce.analytics.tasks.generate_monthly_report',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),  # 1st of month at 01:00
    },
    'refresh-product-analytics': {
        'task': 'apps.commerce.analytics.tasks.refresh_product_analytics',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    },
    'update-customer-segments': {
        'task': 'apps.commerce.analytics.tasks.update_customer_segments',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),  # Sunday at 02:00
    },
    'calculate-abandoned-cart-metrics': {
        'task': 'apps.commerce.analytics.tasks.calculate_abandoned_cart_metrics',
        'schedule': crontab(hour=1, minute=0),  # Daily at 01:00
    },
    'clean-old-analytics-metrics': {
        'task': 'apps.commerce.analytics.tasks.clean_old_metrics',
        'schedule': crontab(day_of_month=1, hour=4, minute=0),  # Monthly at 04:00
    },
}

# --- EMAIL SERVICES (ANYMAIL ALWAYS ON) ---
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
ANYMAIL = {
    "BREVO_API_KEY": env('BREVO_API_KEY'),
}

# SMTP Fallback
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')

# --- WEBSOCKETS (CHANNELS) ---
# [UPDATED] Sử dụng REDIS_CACHE_URL cho WebSockets
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env('REDIS_CACHE_URL')],
        },
    },
}

# --- DYNAMIC CONFIGURATION (CONSTANCE) ---
# [UPDATED] Use Database backend for better Unfold integration
CONSTANCE_BACKEND = 'constance.backends.database.DatabaseBackend'
CONSTANCE_CONFIG = {
    'DEFAULT_SHIPPING_FEE': (30000, 'Phí ship mặc định (VND)', int),
    'FREE_SHIPPING_THRESHOLD': (500000, 'Mức đơn hàng được freeship (VND)', int),
    'MAINTENANCE_MODE': (False, 'Bật chế độ bảo trì toàn trang', bool),
    'CONTACT_EMAIL': ('support@owls.asia', 'Email hỗ trợ khách hàng', str),
    'HOTLINE': ('1900 1000', 'Số điện thoại hotline', str),
}

# --- FRONTEND INTEGRATION ---
SITE_URL = env('SITE_URL')
FRONTEND_URL = env('FRONTEND_URL')

# --- PAYMENTS ---
# Stripe
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default=env('STRIPE_PUBLIC_KEY', default=''))
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')
from decimal import Decimal
VND_TO_USD_RATE = Decimal(str(env.float('VND_TO_USD_RATE', default=25000.0)))

VNPAY_TMN_CODE = env('VNPAY_TMN_CODE')
VNPAY_HASH_SECRET = env('VNPAY_HASH_SECRET')
VNPAY_PAYMENT_URL = env('VNPAY_PAYMENT_URL')
VNPAY_RETURN_URL = f"{SITE_URL}/api/payments/vnpay/return/"
VNPAY_IPN_URL = f"{SITE_URL}/api/payments/vnpay/ipn/"

MOMO_PARTNER_CODE = env('MOMO_PARTNER_CODE')
MOMO_ACCESS_KEY = env('MOMO_ACCESS_KEY')
MOMO_SECRET_KEY = env('MOMO_SECRET_KEY')
MOMO_ENDPOINT = env('MOMO_ENDPOINT')
MOMO_RETURN_URL = f"{SITE_URL}/api/payments/momo/return/"
MOMO_NOTIFY_URL = f"{SITE_URL}/api/payments/momo/webhook/"

# --- SHIPPING ---
GHN_TOKEN = env('GHN_API_TOKEN')
GHN_SHOP_ID = env('GHN_SHOP_ID')
GHN_SANDBOX = env.bool('GHN_SANDBOX')

# Vietnam Administrative Data
VIETNAM_LOCATIONS_DATA_PATH = BASE_DIR / 'data' / 'vietnam_units.json'

# --- SEARCH ENGINE (MEILISEARCH) ---
MEILISEARCH_URL = env('MEILISEARCH_URL', default='http://localhost:7700')
MEILISEARCH_API_KEY = env('MEILISEARCH_API_KEY', default='')
USE_MEILISEARCH = env.bool('USE_MEILISEARCH', default=True)

# --- SOCIAL AUTHENTICATION ---
GITHUB_CLIENT_ID = env('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = env('GITHUB_CLIENT_SECRET')
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = env('GOOGLE_CLIENT_SECRET')

# --- HUMAN VERIFICATION (TURNSTILE) ---
CLOUDFLARE_TURNSTILE_SECRET_KEY = env('CLOUDFLARE_TURNSTILE_SECRET_KEY')
CLOUDFLARE_TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

# --- DATA RETENTION ---
CART_RETENTION_DAYS = env.int('CART_RETENTION_DAYS', default=30)

# --- FIELD ENCRYPTION ---
CRYPTOGRAPHY_KEY = env('FIELD_ENCRYPTION_KEY')
CRYPTOGRAPHY_SALT = env('FIELD_ENCRYPTION_SALT')

# --- PHONE NUMBER FORMATTING ---
PHONENUMBER_DB_FORMAT = 'E164'
PHONENUMBER_DEFAULT_REGION = 'VN'
PHONENUMBER_DEFAULT_FORMAT = 'NATIONAL'

# --- SEO CONFIGURATION (ROBOTS & META) ---
ROBOTS_USE_SITEMAP = True
ROBOTS_USE_HOST = False
ROBOTS_CACHE_TIMEOUT = 60 * 60 * 24

META_SITE_PROTOCOL = 'https'
META_USE_SITES = True
META_USE_OG_PROPERTIES = True
META_USE_TWITTER_PROPERTIES = True
META_USE_TITLE_TAG = True
META_OG_NAMESPACES = ['og', 'fb', 'product']

# --- MAINTENANCE MODE ---
# [UPDATED] Use Constance dynamic config via custom backend
MAINTENANCE_MODE = None  # Ignored when using custom backend
MAINTENANCE_MODE_STATE_BACKEND = 'apps.common.utils.maintenance_backend.ConstanceMaintenanceBackend'
MAINTENANCE_MODE_IGNORE_ADMIN_SITE = True
MAINTENANCE_MODE_IGNORE_SUPERUSER = True
MAINTENANCE_MODE_IGNORE_STAFF = True
MAINTENANCE_MODE_IGNORE_URLS = (
    r'^/api/health/?$',
    r'^/admin/?.*$',
)
MAINTENANCE_MODE_REDIRECT_URL = None
MAINTENANCE_MODE_TEMPLATE = '503.html'
MAINTENANCE_MODE_STATUS_CODE = 503

# --- LOGIN REDIRECTS (2FA) ---
LOGIN_URL = 'two_factor:login'
LOGIN_REDIRECT_URL = '/admin/'
TWO_FACTOR_PATCH_ADMIN = True

# --- DJANGO UNFOLD CONFIGURATION ---
UNFOLD = {
    "SITE_TITLE": "OWLS Admin",
    "SITE_HEADER": "OWLS E-Commerce",
    "SITE_URL": "/",
    
    # Dashboard callback for KPIs and analytics
    "DASHBOARD_CALLBACK": "apps.common.utils.dashboard.dashboard_callback",
    
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,  # Disable auto to use custom navigation
        "navigation": [
            # --- Dashboard & Analytics ---
            {
                "title": _("Analytics"),
                "icon": "analytics",
                "collapsible": True,
                "items": [
                    {"title": _("Dashboard"), "icon": "dashboard", "link": "/admin-login/"},
                    {"title": _("Daily Metrics"), "icon": "today", "link": "/admin-login/analytics/dailymetric/"},
                    {"title": _("Monthly Reports"), "icon": "calendar_month", "link": "/admin-login/analytics/monthlyreport/"},
                    {"title": _("Product Analytics"), "icon": "inventory_2", "link": "/admin-login/analytics/productanalytics/"},
                    {"title": _("Customer Segments"), "icon": "groups", "link": "/admin-login/analytics/customersegment/"},
                    {"title": _("Sales Funnel"), "icon": "filter_alt", "link": "/admin-login/analytics/salesfunnel/"},
                    {"title": _("Revenue Breakdown"), "icon": "pie_chart", "link": "/admin-login/analytics/revenuebreakdown/"},
                    {"title": _("Traffic Sources"), "icon": "travel_explore", "link": "/admin-login/analytics/trafficsource/"},
                    {"title": _("Abandoned Carts"), "icon": "remove_shopping_cart", "link": "/admin-login/analytics/abandonedcartmetric/"},
                ],
            },
            # --- Orders & Commerce ---
            {
                "title": _("Orders"),
                "icon": "shopping_bag",
                "collapsible": True,
                "items": [
                    {"title": _("All Orders"), "icon": "list_alt", "link": "/admin-login/orders/order/"},
                    {"title": _("Order Notes"), "icon": "sticky_note_2", "link": "/admin-login/orders/ordernote/"},
                ],
            },
            # --- Billing & Payments ---
            {
                "title": _("Billing"),
                "icon": "payments",
                "collapsible": True,
                "items": [
                    {"title": _("Transactions"), "icon": "receipt_long", "link": "/admin-login/billing/paymenttransaction/"},
                    {"title": _("Refunds"), "icon": "money_off", "link": "/admin-login/billing/paymentrefund/"},
                ],
            },
            # --- Shipping ---
            {
                "title": _("Shipping"),
                "icon": "local_shipping",
                "collapsible": True,
                "items": [
                    {"title": _("Shipments"), "icon": "inventory", "link": "/admin-login/shipping/shipment/"},
                    {"title": _("COD Reconciliation"), "icon": "attach_money", "link": "/admin-login/shipping/codreconciliation/"},
                ],
            },
            # --- Returns ---
            {
                "title": _("Returns"),
                "icon": "assignment_return",
                "collapsible": True,
                "items": [
                    {"title": _("Return Requests"), "icon": "undo", "link": "/admin-login/returns/returnrequest/"},
                ],
            },
            # --- Cart ---
            {
                "title": _("Shopping Cart"),
                "icon": "shopping_cart",
                "collapsible": True,
                "items": [
                    {"title": _("Carts"), "icon": "shopping_basket", "link": "/admin-login/cart/cart/"},
                ],
            },
            # --- Catalog & Products ---
            {
                "title": _("Products"),
                "icon": "inventory_2",
                "collapsible": True,
                "items": [
                    {"title": _("All Products"), "icon": "view_list", "link": "/admin-login/catalog/product/"},
                    {"title": _("Categories"), "icon": "category", "link": "/admin-login/catalog/category/"},
                    {"title": _("Brands"), "icon": "branding_watermark", "link": "/admin-login/catalog/brand/"},
                    {"title": _("Product Tags"), "icon": "label", "link": "/admin-login/catalog/producttag/"},
                ],
            },
            # --- Inventory ---
            {
                "title": _("Inventory"),
                "icon": "warehouse",
                "collapsible": True,
                "items": [
                    {"title": _("Stock Items"), "icon": "inventory", "link": "/admin-login/inventory/stockitem/"},
                    {"title": _("Warehouses"), "icon": "store", "link": "/admin-login/inventory/warehouse/"},
                    {"title": _("Stock Movements"), "icon": "swap_horiz", "link": "/admin-login/inventory/stockmovement/"},
                    {"title": _("Stock Alerts"), "icon": "warning", "link": "/admin-login/inventory/stockalert/"},
                ],
            },
            # --- Marketing ---
            {
                "title": _("Marketing"),
                "icon": "campaign",
                "collapsible": True,
                "items": [
                    {"title": _("Coupons"), "icon": "local_offer", "link": "/admin-login/marketing/coupon/"},
                    {"title": _("Flash Sales"), "icon": "flash_on", "link": "/admin-login/marketing/flashsale/"},
                    {"title": _("Campaigns"), "icon": "campaign", "link": "/admin-login/marketing/campaign/"},
                    {"title": _("Banners"), "icon": "image", "link": "/admin-login/marketing/banner/"},
                ],
            },
            # --- Reviews & Wishlist ---
            {
                "title": _("Engagement"),
                "icon": "favorite",
                "collapsible": True,
                "items": [
                    {"title": _("Reviews"), "icon": "rate_review", "link": "/admin-login/reviews/review/"},
                    {"title": _("Wishlists"), "icon": "bookmark", "link": "/admin-login/wishlist/wishlist/"},
                ],
            },
            # --- Users & Identity ---
            {
                "title": _("Users"),
                "icon": "people",
                "collapsible": True,
                "items": [
                    {"title": _("All Users"), "icon": "person", "link": "/admin-login/identity/user/"},
                    {"title": _("Addresses"), "icon": "location_on", "link": "/admin-login/identity/useraddress/"},
                    {"title": _("Social Accounts"), "icon": "link", "link": "/admin-login/identity/socialaccount/"},
                    {"title": _("Sessions"), "icon": "devices", "link": "/admin-login/identity/usersession/"},
                    {"title": _("Login History"), "icon": "history", "link": "/admin-login/identity/loginhistory/"},
                    {"title": _("Preferences"), "icon": "settings", "link": "/admin-login/identity/userpreferences/"},
                ],
            },
            # --- Notifications ---
            {
                "title": _("Notifications"),
                "icon": "notifications",
                "collapsible": True,
                "items": [
                    {"title": _("All Notifications"), "icon": "notifications_active", "link": "/admin-login/notifications/notification/"},
                    {"title": _("Templates"), "icon": "description", "link": "/admin-login/notifications/notificationtemplate/"},
                    {"title": _("Logs"), "icon": "receipt_long", "link": "/admin-login/notifications/notificationlog/"},
                    {"title": _("Device Tokens"), "icon": "phone_android", "link": "/admin-login/notifications/devicetoken/"},
                ],
            },
            # --- Security ---
            {
                "title": _("Security"),
                "icon": "security",
                "collapsible": True,
                "items": [
                    {"title": _("2FA Config"), "icon": "key", "link": "/admin-login/security/twofactorconfig/"},
                    {"title": _("API Keys"), "icon": "vpn_key", "link": "/admin-login/security/apikey/"},
                    {"title": _("Trusted Devices"), "icon": "verified_user", "link": "/admin-login/security/trusteddevice/"},
                    {"title": _("Access Attempts (Axes)"), "icon": "login", "link": "/admin-login/axes/accessattempt/"},
                    {"title": _("Access Failures"), "icon": "block", "link": "/admin-login/axes/accessfailurelog/"},
                    {"title": _("IP Blacklist"), "icon": "gpp_bad", "link": "/admin-login/security/ipblacklist/"},
                    {"title": _("Audit Log"), "icon": "fact_check", "link": "/admin-login/auditlog/logentry/"},
                    {"title": _("Security Audit Log"), "icon": "security_update_warning", "link": "/admin-login/security/securityauditlog/"},
                ],
            },
            # --- Settings & System ---
            {
                "title": _("Settings"),
                "icon": "settings",
                "collapsible": True,
                "items": [
                    {"title": _("Site Config"), "icon": "settings_applications", "link": "/admin-login/constance/config/"},
                    {"title": _("Sites"), "icon": "public", "link": "/admin-login/sites/site/"},
                    {"title": _("Groups & Permissions"), "icon": "admin_panel_settings", "link": "/admin-login/auth/group/"},
                ],
            },
            # --- Background Tasks ---
            {
                "title": _("Background Tasks"),
                "icon": "schedule",
                "collapsible": True,
                "items": [
                    {"title": _("Periodic Tasks"), "icon": "timer", "link": "/admin-login/django_celery_beat/periodictask/"},
                    {"title": _("Crontabs"), "icon": "event_repeat", "link": "/admin-login/django_celery_beat/crontabschedule/"},
                    {"title": _("Intervals"), "icon": "av_timer", "link": "/admin-login/django_celery_beat/intervalschedule/"},
                    {"title": _("Task Results"), "icon": "task_alt", "link": "/admin-login/django_celery_results/taskresult/"},
                    {"title": _("Group Results"), "icon": "folder", "link": "/admin-login/django_celery_results/groupresult/"},
                ],
            },
        ],
    },
    
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
    },
}