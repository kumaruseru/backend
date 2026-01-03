# OWLS E-Commerce Backend

Production-ready Django REST API for e-commerce platform.

## 🚀 Features

### Users Domain
- **Identity**: User registration, authentication (JWT), profile management
- **Security**: 2FA (TOTP/Email), API keys, trusted devices, IP blacklisting
- **Social**: OAuth login (Google, GitHub, Facebook)
- **Notifications**: Multi-channel (in-app, email, push via FCM)

### Store Domain
- **Catalog**: Products, categories, brands, variants, attributes
- **Marketing**: Promotions, coupons, banners, flash sales
- **Reviews**: Ratings, images, replies, moderation
- **Wishlist**: Multiple lists, price tracking, sharing
- **Inventory**: Stock management, reservations, alerts

### Commerce Domain
- **Cart**: Guest/user carts, saved items, abandonment tracking
- **Orders**: Order lifecycle, status history, notes
- **Billing**: VNPay, MoMo integration, refunds
- **Shipping**: GHN integration, tracking, COD reconciliation
- **Returns**: Return requests, QC workflow, refund processing

## 🛠 Tech Stack

- **Framework**: Django 5.2 + Django REST Framework
- **Database**: PostgreSQL
- **Cache**: Redis
- **Task Queue**: Celery + Redis
- **Auth**: JWT (SimpleJWT)
- **Storage**: AWS S3 / Cloudflare R2
- **Payments**: VNPay, MoMo
- **Shipping**: GHN (Giao Hàng Nhanh)
- **Monitoring**: Sentry

## 📋 Requirements

- Python 3.12+
- PostgreSQL 15+
- Redis 7+

## ⚙️ Installation

```bash
# Clone repository
git clone https://github.com/kumaruseru/backend.git
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

## 🔧 Environment Variables

```env
# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:pass@localhost:5432/owls

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=7

# Payments
VNPAY_TMN_CODE=xxx
VNPAY_HASH_SECRET=xxx
MOMO_PARTNER_CODE=xxx
MOMO_ACCESS_KEY=xxx
MOMO_SECRET_KEY=xxx

# Shipping
GHN_API_TOKEN=xxx
GHN_SHOP_ID=xxx

# AWS S3
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_STORAGE_BUCKET_NAME=xxx
```

## 🚦 Running Services

```bash
# Django server
python manage.py runserver

# Celery worker
celery -A backend worker -l info -Q users,commerce,store,default

# Celery beat (scheduled tasks)
celery -A backend beat -l info

# Flower (monitoring)
celery -A backend flower
```

## 📚 API Documentation

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI Schema: `/api/schema/`

## 📁 Project Structure

```
backend/
├── apps/
│   ├── common/          # Shared utilities
│   │   ├── core/        # Base models, exceptions, handlers
│   │   └── utils/       # Security, middleware
│   ├── users/           # User management
│   │   ├── identity/    # Auth, profile
│   │   ├── security/    # 2FA, API keys
│   │   ├── social/      # OAuth
│   │   └── notifications/
│   ├── store/           # Product management
│   │   ├── catalog/
│   │   ├── marketing/
│   │   ├── reviews/
│   │   ├── wishlist/
│   │   └── inventory/
│   └── commerce/        # Order processing
│       ├── cart/
│       ├── orders/
│       ├── billing/
│       ├── shipping/
│       └── returns/
├── backend/             # Django project settings
├── scripts/             # Utility scripts
└── manage.py
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 👤 Author

OWLS Team
