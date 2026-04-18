from datetime import datetime
from app import db
import uuid


def gen_uuid():
    return str(uuid.uuid4())


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    position = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    compare_at_price = db.Column(db.Numeric(10, 2))
    category_id = db.Column(db.String(36), db.ForeignKey('categories.id'))
    status = db.Column(db.String(20), default='active')  # active, draft, archived
    featured = db.Column(db.Boolean, default=False)
    gender = db.Column(db.String(20))  # men, women, unisex
    brand = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = db.relationship('ProductImage', backref='product', lazy='dynamic',
                              cascade='all, delete-orphan', order_by='ProductImage.position')
    variants = db.relationship('ProductVariant', backref='product', lazy='dynamic',
                                cascade='all, delete-orphan')

    @property
    def primary_image(self):
        img = self.images.first()
        return img.url if img else '/static/img/placeholder.jpg'

    @property
    def all_images(self):
        return [i.url for i in self.images.all()]

    @property
    def sizes(self):
        return sorted({v.size for v in self.variants if v.size and v.quantity > 0})

    @property
    def colors(self):
        seen = set()
        result = []
        for v in self.variants:
            if v.color and v.color.lower() not in seen:
                seen.add(v.color.lower())
                result.append({'name': v.color, 'hex': v.color_hex or '#000000'})
        return result

    @property
    def in_stock(self):
        return any(v.quantity > 0 for v in self.variants)

    @property
    def total_stock(self):
        return sum(v.quantity for v in self.variants)

    def get_variant(self, size, color):
        return self.variants.filter_by(size=size, color=color).first()

    def __repr__(self):
        return f'<Product {self.name}>'


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(200))
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    size = db.Column(db.String(20))
    color = db.Column(db.String(50))
    color_hex = db.Column(db.String(10))
    sku = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def effective_price(self):
        return self.price if self.price else self.product.price


class Customer(db.Model):
    """Auto-created from orders — no auth, CRM only."""
    __tablename__ = 'customers'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(30), nullable=False)
    address_line1 = db.Column(db.String(300))
    address_line2 = db.Column(db.String(300))
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    @property
    def order_count(self):
        return self.orders.count()

    @property
    def total_spent(self):
        return sum(o.total for o in self.orders if o.status not in ('cancelled',))

    def __repr__(self):
        return f'<Customer {self.full_name}>'


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.String(36), db.ForeignKey('customers.id'))

    # Snapshot of delivery info at time of order
    delivery_name = db.Column(db.String(200), nullable=False)
    delivery_phone = db.Column(db.String(30), nullable=False)
    delivery_email = db.Column(db.String(200))
    delivery_address = db.Column(db.String(500), nullable=False)
    delivery_city = db.Column(db.String(100), nullable=False)
    delivery_region = db.Column(db.String(100))
    delivery_notes = db.Column(db.Text)

    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    delivery_fee = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    status = db.Column(db.String(30), default='pending')
    # pending → confirmed → processing → shipped → delivered → cancelled

    payment_method = db.Column(db.String(50), default='cash_on_delivery')
    payment_status = db.Column(db.String(30), default='pending')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy='dynamic',
                             cascade='all, delete-orphan')

    STATUS_LABELS = {
        'pending': 'Pending',
        'confirmed': 'Confirmed',
        'processing': 'Processing',
        'shipped': 'Shipped',
        'delivered': 'Delivered',
        'cancelled': 'Cancelled',
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status.title())

    def __repr__(self):
        return f'<Order {self.order_number}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'))
    variant_id = db.Column(db.String(36), db.ForeignKey('product_variants.id'))

    # Snapshot at time of order
    product_name = db.Column(db.String(200), nullable=False)
    product_image = db.Column(db.String(500))
    size = db.Column(db.String(20))
    color = db.Column(db.String(50))
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    product = db.relationship('Product')
    variant = db.relationship('ProductVariant')

    @property
    def line_total(self):
        return self.price * self.quantity


class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SiteSettings(db.Model):
    """Key-value CMS settings table. One row per setting key."""
    __tablename__ = 'site_settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Defaults used when the row doesn't exist yet
    DEFAULTS = {
        'hero_style': 'balenciaga',        # balenciaga | puma
        'hero_media_type': 'image',        # image | video
        'hero_media_url': '',              # relative static path or absolute URL
        'hero_label': 'SS 2025 — Slidin GH',
        'hero_title': 'Campaign',
        'hero_cta_primary_text': 'Shop Sneakers',
        'hero_cta_primary_url': '/shop',
        'hero_cta_secondary_text': 'Discover Now',
        'hero_cta_secondary_url': '/shop',
        'announcement_bar_text': '',
        'announcement_bar_active': 'false',
        'site_name': 'Slidin GH',
    }

    @classmethod
    def get(cls, key):
        row = cls.query.get(key)
        if row:
            return row.value
        return cls.DEFAULTS.get(key, '')

    @classmethod
    def set(cls, key, value):
        row = cls.query.get(key)
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            db.session.add(cls(key=key, value=value))

    @classmethod
    def get_all(cls):
        rows = {r.key: r.value for r in cls.query.all()}
        result = dict(cls.DEFAULTS)
        result.update(rows)
        return result

    @classmethod
    def seed_defaults(cls):
        for key, value in cls.DEFAULTS.items():
            if not cls.query.get(key):
                db.session.add(cls(key=key, value=value))
        db.session.commit()