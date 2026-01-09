# 🦉 Owls E-commerce Backend

Professional, scalable, and feature-rich E-commerce Backend API built with Django and Django Rest Framework. Designed for high performance, security, and ease of use.

## 🚀 Key Features

### 🛒 Commerce Core
- **Advanced Cart System**: Persistent carts, guest cart merging, stock validation, and abandoned cart tracking.
- **Order Management**: Complete order lifecycle (Pending → Processing → Shipping → Completed), order splitting, and tracking.
- **Product Catalog**: hierarchical categories, brands, variants (SKU), and inventory management.
- **Checkout Flow**: Optimized checkout process with address validation and shipping calculation.

### 💳 Billing & Payments
- **Multi-Gateway Support**: Integrated with **Stripe** (USD), **MoMo** (VND), and **VNPay** (VND).
- **Smart Currency Handling**: Auto-conversion between VND/USD based on gateway support.
- **Refund Management**: Full and partial refunds directly from the admin dashboard.
- **Transaction Logging**: Comprehensive audit trail for all payment events.

### 📊 Analytics & Insights
- **Business Dashboard**: Real-time metrics for Revenue, Orders, AOV, and Active Customers.
- **Traffic Analysis**: Track sources (Google, Facebook, Direct) and conversion rates.
- **Sales Funnel**: Visual funnel analysis (View → Cart → Checkout → Purchase).
- **Customer Segmentation**: RFM (Recency, Frequency, Monetary) analysis to identify VIPs and at-risk users.

### 📦 Shipping & Inventory
- **Inventory Tracking**: Multi-warehouse support, stock movements, and low-stock alerts.
- **Shipping Integration**: Pluggable provider system (default supports GHN, GHTK, manual).
- **COD Reconciliation**: Tools to manage and verify Cash on Delivery payments.

### 🛡️ Security & Identity
- **Robust Authentication**: JWT-based auth (Access/Refresh tokens) via `dj-rest-auth`.
- **Two-Factor Authentication (2FA)**: TOTP support (Google Authenticator) for admin and high-security accounts.
- **Security Hardening**: Rate limiting (`django-axes`), brute-force protection, and secure headers.
- **Role-Based Access**: Granular permissions for Staff, Managers, and Admins.

### 🎨 Modern Admin Interface
- **Unfold Admin Theme**: Beautiful, responsive, and user-friendly admin UI.
- **Custom Dashboard**: Widgets for quick insights and navigation.
- **Sidebar Navigation**: Organized grouping of modules for efficient workflow.

---

## 🛠️ Technology Stack

- **Framework**: Django 5.x, Django Rest Framework (DRF)
- **Database**: PostgreSQL 15+
- **Caching & Async**: Redis, Celery (for emails, reports, background tasks)
- **Search**: PostgreSQL Search / Trigram (or ready for ElasticSearch)
- **Storage**: AWS S3 (via `django-storages`) for static & media
- **Documentation**: OpenAPI (Swagger/Redoc) via `drf-spectacular`

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.10+
- PostgreSQL
- Redis

### 1. Clone the Repository
```bash
git clone <repo_url>
cd backend
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration (.env)
Create a `.env` file in the `backend/` root (copy from `.env.example` if available). Key variables:

```ini
DEBUG=True
SECRET_KEY=your-super-secret-key
ALLOWED_HOSTS=127.0.0.1,localhost

# Database
DATABASE_URL=postgres://user:password@localhost:5432/owls_db

# Redis (Cache & Celery)
REDIS_URL=redis://localhost:6379/1

# Payments
STRIPE_SECRET_KEY=sk_test_...
MOMO_PARTNER_CODE=...
VNPAY_TMN_CODE=...

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=...
```

### 5. Run Migrations
```bash
python manage.py migrate
```

### 6. Create Superuser
```bash
python manage.py createsuperuser
```

### 7. Run Server
```bash
python manage.py runserver
```

Access the admin panel at: `http://127.0.0.1:8000/admin-login/`

---

## 📂 Project Structure

```
backend/
├── apps/
│   ├── common/         # Core utilities, base models, middlewares
│   ├── users/          # Identity, profiles, 2FA, notifications
│   ├── store/          # Catalog, inventory, reviews, marketing
│   └── commerce/       # Cart, orders, billing, shipping, analytics
├── backend/            # Project settings, ASGI/WSGI config
├── media/              # User uploaded files (dev only)
├── static/             # Collected static files
└── manage.py
```

## 📝 API Documentation

API endpoints are fully documented using OpenAPI 3.0.
Once the server is running, visit:

- **Swagger UI**: `http://127.0.0.1:8000/api/docs/swagger/`
- **ReDoc**: `http://127.0.0.1:8000/api/docs/redoc/`

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
