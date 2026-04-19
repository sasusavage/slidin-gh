# Slidein GH — Store

Flask + PostgreSQL e-commerce. Balenciaga-inspired editorial design.
No customer accounts — just order, confirm, done.

## Stack
- **Backend**: Python / Flask
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Storage**: Local filesystem (`app/static/uploads/`)
- **Frontend**: Jinja2 + vanilla CSS/JS (no framework)

## Setup

```bash
# 1. Create virtualenv
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create PostgreSQL database
createdb slidin_store
psql slidin_store -f schema.sql   # creates tables + seed categories

# 4. Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD

# 5. Run
python run.py
```

Open `http://localhost:5000` — store  
Open `http://localhost:5000/admin` — admin CRM (password from .env)

## Deployment (Coolify / Docker)

```bash
gunicorn "app:create_app('production')" --bind 0.0.0.0:8000 --workers 4
```

Set `DATABASE_URL` to your PostgreSQL connection string.  
Mount a persistent volume at `app/static/uploads/` for product images.

## Order Flow
1. Browse → select size + color → Add to Bag
2. Checkout form (name, phone, address) — **no account required**
3. Place Order → order confirmed, stock deducted
4. Customer receives order number, can track via `/order/track`
5. Admin sees order + auto-created customer profile in CRM

## Admin CRM
- `/admin` — dashboard, stats, low-stock alerts
- `/admin/orders` — all orders, filter by status, update status
- `/admin/customers` — auto-built from orders, search, notes
- `/admin/products` — CRUD, image uploads, variant grid
- `/admin/categories` — manage categories