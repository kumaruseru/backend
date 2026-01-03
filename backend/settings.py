"""
Django settings for OWLS E-Commerce Backend (DDD Architecture).
STRICT PRODUCTION MODE.
"""
import os
import sys
import environ
from pathlib import Path
from datetime import timedelta

# --- THIRD PARTY IMPORTS (Sentry) ---
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# --- INITIALIZATION ---
env = environ.Env()
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(BASE_DIR / '.env')
sys.path.append(str(BASE_DIR / 'apps'))

# --- CORE SETTINGS ---
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS')
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY')

# Key Rotation: Add old keys here when rotating, newest first
FIELD_ENCRYPTION_KEY_PREVIOUS = env.list('FIELD_ENCRYPTION_KEY_PREVIOUS', default=[])

# --- APPS CONFIGURATION ---
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'storages',
    'drf_spectacular',
    'django_filters',
    'sequences',
]

LOCAL_APPS = [
    # Common
    'apps.common.core',
    # Users
    'apps.users.identity',
    'apps.users.notifications',
    'apps.users.security',
    'apps.users.social',
    # Store
    'apps.store.catalog',
    'apps.store.marketing',
    'apps.store.reviews',
    'apps.store.wishlist',
    'apps.store.inventory',
    # Commerce
    'apps.commerce.cart',
    'apps.commerce.orders',
    'apps.commerce.billing',
    'apps.commerce.shipping',
    'apps.commerce.returns',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.common.utils.middleware.SecurityHeadersMiddleware',
    'apps.common.utils.middleware.RequestLoggingMiddleware',
    'apps.common.utils.middleware.SuspiciousActivityMiddleware',
]

ROOT_URLCONF = 'backend.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# --- DATABASE ---
DATABASES = {
    'default': env.db('DATABASE_URL'),
}

DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=600)
DATABASES['default']['ATOMIC_REQUESTS'] = True

# --- CACHE & SESSION ---
CACHES = {
    'default': env.cache('REDIS_URL')
}
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# --- AUTHENTICATION ---
AUTH_USER_MODEL = 'identity.User'

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

# --- INTERNATIONALIZATION ---
LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# --- CLOUD STORAGE (MANDATORY) ---
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL')
AWS_S3_CUSTOM_DOMAIN = env('AWS_S3_CUSTOM_DOMAIN')
AWS_S3_REGION_NAME = 'auto'
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None

STORAGES = {
    "default": {"BACKEND": "apps.common.core.storage.MediaStorage"},
    "staticfiles": {"BACKEND": "apps.common.core.storage.StaticStorage"},
}

STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# --- EMAIL ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env.int('EMAIL_PORT')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')

# --- PAYMENTS ---
SITE_URL = env('SITE_URL')
FRONTEND_URL = env('FRONTEND_URL')

STRIPE_PUBLIC_KEY = env('STRIPE_PUBLIC_KEY')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')

# VNPay
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

# --- COMMERCE SETTINGS ---
# Shipping fee in VND when GHN API fails
DEFAULT_SHIPPING_FEE = env.int('DEFAULT_SHIPPING_FEE', default=30000)
# Orders above this value get free shipping
FREE_SHIPPING_THRESHOLD = env.int('FREE_SHIPPING_THRESHOLD', default=500000)

# --- API CONFIGURATION ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticatedOrReadOnly',),
    'DEFAULT_PAGINATION_CLASS': 'apps.common.core.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'COERCE_DECIMAL_TO_STRING': True,
    'EXCEPTION_HANDLER': 'apps.common.core.handlers.custom_exception_handler',
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
        '2fa_login': '5/min',
        '2fa_disable': '5/min',
        '2fa_email': '5/min',
        '2fa_backup_codes': '5/min',
        # Cart & Orders
        'cart_modify': '120/min',
        'order_create': '10/min',
        'payment_create': '10/min',
        'tracking': '60/min',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


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

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env.int('JWT_ACCESS_MINUTES')),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env.int('JWT_REFRESH_DAYS')),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
}

# --- SECURITY ---
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True

if CORS_ALLOW_CREDENTIALS:
    for origin in CORS_ALLOWED_ORIGINS:
        if origin == '*' or origin.startswith('*'):
            raise ValueError("SECURITY ERROR: CORS_ALLOWED_ORIGINS cannot contain '*' with credentials enabled.")

# Basic Security (Always ON)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# SSL/HTTPS Security (Production ONLY)
# Fix: Prevent auto-redirect to HTTPS on Localhost when DEBUG=True
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    # Development Settings
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- LOGGING & MONITORING ---
SENTRY_DSN = env('SENTRY_DSN', default=None)

# Initialize Sentry unconditionally (it handles DSN=None safely)
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
    },
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(levelname)s %(asctime)s %(message)s %(pathname)s %(lineno)d',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['mask_sensitive'],
        },
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': env('DJANGO_LOG_LEVEL', default='INFO'), 'propagate': True},
        'apps': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
    },
}

# --- SOCIAL AUTH ---
GITHUB_CLIENT_ID = env('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = env('GITHUB_CLIENT_SECRET')
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = env('GOOGLE_CLIENT_SECRET')

# --- TASKS ---
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 1800

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'sync-pending-shipments': {
        'task': 'apps.commerce.shipping.tasks.sync_all_pending_shipments',
        'schedule': crontab(minute='*/30'),
    },
    'cleanup-old-guest-carts': {
        'task': 'apps.commerce.cart.tasks.cleanup_old_guest_carts_task',
        'schedule': crontab(hour=3, minute=0),
    },
}

# --- BUSINESS LOGIC ---
CART_RETENTION_DAYS = env.int('CART_RETENTION_DAYS', default=30)

# --- SECURITY: CLOUDFLARE TURNSTILE ---
CLOUDFLARE_TURNSTILE_SECRET_KEY = env('CLOUDFLARE_TURNSTILE_SECRET_KEY')
CLOUDFLARE_TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'