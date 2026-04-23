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
    stock_quantity = db.Column(db.Integer, default=0)
    # Pre-order settings
    pre_order_enabled = db.Column(db.Boolean, default=False)
    pre_order_price = db.Column(db.Numeric(10, 2))
    pre_order_shipping_fee = db.Column(db.Numeric(10, 2))
    pre_order_notes = db.Column(db.Text)
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
    image_template = db.Column(db.String(50))  # e.g. 'white_bg', 'shadow', 'studio', None=original
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
    color_image = db.Column(db.String(500))  # per-color image URL
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


class ProductReview(db.Model):
    """Customer product reviews (submitted post-purchase, moderated by admin)."""
    __tablename__ = 'product_reviews'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'))
    reviewer_name = db.Column(db.String(200), nullable=False)
    reviewer_email = db.Column(db.String(200))
    rating = db.Column(db.Integer, nullable=False)   # 1–5
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending | approved | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref=db.backref('reviews', lazy='dynamic'))

    @property
    def stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)


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

    DEFAULTS = {
        # General
        'site_name': 'Slidein GH',
        'site_tagline': 'Premium Sneakers in Ghana',
        'site_logo': '',
        'site_favicon': '',
        'contact_email': '',
        'contact_phone': '',
        'contact_address': '',
        'currency': 'GHS',
        'currency_symbol': 'GH₵',
        # Social
        'social_instagram': '',
        'social_facebook': '',
        'social_twitter': '',
        'social_tiktok': '',
        'social_whatsapp': '',
        # Appearance / colors
        'primary_color': '#000000',
        'secondary_color': '#ffffff',
        'accent_color': '#111111',
        # Hero
        'hero_style': 'balenciaga',
        'hero_media_type': 'image',
        'hero_media_url': '',
        'hero_label': 'SS 2025 — Slidein GH',
        'hero_title': 'Campaign',
        'hero_subheadline': '',
        'hero_cta_primary_text': 'Shop Sneakers',
        'hero_cta_primary_url': '/shop',
        'hero_cta_secondary_text': 'Discover Now',
        'hero_cta_secondary_url': '/shop',
        'hero_badge_label': '',
        'hero_badge_text': '',
        'hero_badge_subtext': '',
        'hero_stat1_title': '',
        'hero_stat1_desc': '',
        'hero_stat2_title': '',
        'hero_stat2_desc': '',
        'hero_stat3_title': '',
        'hero_stat3_desc': '',
        # Trust features
        'feature1_icon': 'ri-truck-line',
        'feature1_title': 'Free Delivery',
        'feature1_desc': 'On orders over GH₵500',
        'feature2_icon': 'ri-shield-check-line',
        'feature2_title': '100% Authentic',
        'feature2_desc': 'All sneakers verified',
        'feature3_icon': 'ri-refresh-line',
        'feature3_title': 'Easy Returns',
        'feature3_desc': '7-day return policy',
        'feature4_icon': 'ri-customer-service-2-line',
        'feature4_title': '24/7 Support',
        'feature4_desc': 'Chat or call us anytime',
        # Announcement bar
        'announcement_bar_text': '',
        'announcement_bar_active': 'false',
        # Header
        'header_show_search': 'true',
        'header_nav_links_json': '[{"label":"Shop","href":"/shop"},{"label":"About","href":"/p/about"}]',
        # Footer
        'footer_col1_title': 'Shop',
        'footer_col1_links_json': '[{"label":"All Sneakers","href":"/shop"},{"label":"New Arrivals","href":"/shop?sort=newest"},{"label":"Sale","href":"/shop?sale=1"}]',
        'footer_col2_title': 'Customer Care',
        'footer_col2_links_json': '[{"label":"Track Order","href":"/track-order"},{"label":"Returns","href":"/p/returns"},{"label":"FAQ","href":"/p/faq"}]',
        'footer_col3_title': 'Company',
        'footer_col3_links_json': '[{"label":"About Us","href":"/p/about"},{"label":"Contact","href":"/p/contact"},{"label":"Privacy","href":"/p/privacy"}]',
        'footer_copyright_text': '© 2025 Slidein GH. All rights reserved.',
        'footer_show_newsletter': 'false',
        'footer_newsletter_title': 'Stay in the loop',
        'footer_newsletter_subtitle': 'New drops, exclusive deals — in your inbox.',
        # About page
        'about_hero_title': 'Our Story',
        'about_hero_subtitle': 'Born in Ghana. Built for Sneakerheads.',
        'about_story_title': 'How we started',
        'about_story_content': '',
        'about_story_image': '',
        'about_founder_name': '',
        'about_founder_title': '',
        'about_mission1_title': 'Our Mission',
        'about_mission1_content': '',
        'about_mission2_title': 'Our Vision',
        'about_mission2_content': '',
        'about_cta_title': 'Ready to step up?',
        'about_cta_subtitle': 'Shop our latest drops.',
        # Contact page
        'contact_hero_title': 'Get in Touch',
        'contact_hero_subtitle': 'We\'d love to hear from you.',
        'contact_hours': 'Mon – Sat: 9am – 6pm',
        'contact_whatsapp_hours': 'Mon – Sun: 8am – 9pm',
        'contact_map_link': '',
        'contact_team_json': '[]',
        # SEO
        'seo_title': 'Slidein GH — Premium Sneakers',
        'seo_description': 'Shop authentic sneakers in Ghana. Fast delivery.',
        'seo_keywords': 'sneakers, shoes, ghana, nike, adidas',
        'seo_og_image': '',
        'seo_google_analytics': '',
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


class Banner(db.Model):
    """Promotional banners with optional date scheduling."""
    __tablename__ = 'banners'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(30), default='promotional')  # promotional | announcement | warning
    title = db.Column(db.String(200))
    subtitle = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    background_color = db.Column(db.String(10), default='#000000')
    text_color = db.Column(db.String(10), default='#FFFFFF')
    button_text = db.Column(db.String(100))
    button_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    position = db.Column(db.String(20), default='top')  # top | bottom | homepage
    sort_order = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_live(self):
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


class Page(db.Model):
    """CMS static pages (About, Contact, Privacy, FAQs, etc.)"""
    __tablename__ = 'pages'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    content = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')  # draft | published
    seo_title = db.Column(db.String(200))
    seo_description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationLog(db.Model):
    """Log of every SMS/email sent, for debugging and retry."""
    __tablename__ = 'notification_logs'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    channel = db.Column(db.String(20), nullable=False)   # sms | email
    recipient = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'))
    status = db.Column(db.String(20), default='queued')   # queued | logged | sent | failed
    provider = db.Column(db.String(30))
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StockNotification(db.Model):
    """Back-in-stock alert signup for guests (phone/email, no account)."""
    __tablename__ = 'stock_notifications'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.String(36), db.ForeignKey('product_variants.id'))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(200))
    notified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product')
    variant = db.relationship('ProductVariant')


class NewsletterSignup(db.Model):
    """Footer newsletter signups (email-based)."""
    __tablename__ = 'newsletter_signups'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    email = db.Column(db.String(200), unique=True, nullable=False)
    source = db.Column(db.String(50), default='footer')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CouponCode(db.Model):
    """Discount coupons applied at checkout."""
    __tablename__ = 'coupon_codes'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    discount_type = db.Column(db.String(20), default='percent')  # percent | fixed
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    min_order_amount = db.Column(db.Numeric(10, 2), default=0)
    max_uses = db.Column(db.Integer)
    uses_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_valid(self):
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.max_uses and self.uses_count >= self.max_uses:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


# ── Supplier & purchasing ──────────────────────────────────────────────────

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy='dynamic')


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    po_number = db.Column(db.String(30), unique=True, nullable=False)
    supplier_id = db.Column(db.String(36), db.ForeignKey('suppliers.id'))
    status = db.Column(db.String(20), default='pending')  # pending|partial|received|cancelled
    payment_type = db.Column(db.String(20), default='cash')  # cash|credit
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True,
                             cascade='all, delete-orphan')


class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    purchase_order_id = db.Column(db.String(36), db.ForeignKey('purchase_orders.id'), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'))
    quantity_ordered = db.Column(db.Integer, default=0)
    quantity_received = db.Column(db.Integer, default=0)
    unit_cost = db.Column(db.Numeric(12, 2), default=0)
    total_cost = db.Column(db.Numeric(12, 2), default=0)

    product = db.relationship('Product', foreign_keys=[product_id])


# ── Stock management ───────────────────────────────────────────────────────

class StockAdjustment(db.Model):
    __tablename__ = 'stock_adjustments'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'))
    reason = db.Column(db.String(50))  # damage|theft|correction|recount|expired|other
    quantity_before = db.Column(db.Integer, default=0)
    quantity_after = db.Column(db.Integer, default=0)
    quantity_change = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', foreign_keys=[product_id])


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'))
    movement_type = db.Column(db.String(30))  # sale|purchase|adjustment|refund
    quantity_change = db.Column(db.Integer, default=0)
    quantity_before = db.Column(db.Integer, default=0)
    quantity_after = db.Column(db.Integer, default=0)
    reference_id = db.Column(db.String(36))
    reference_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', foreign_keys=[product_id])


# ── Expenses ───────────────────────────────────────────────────────────────

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    category = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.Text)
    expense_date = db.Column(db.Date, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Blog posts ─────────────────────────────────────────────────────────────

class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    excerpt = db.Column(db.Text)
    body = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    status = db.Column(db.String(20), default='draft')  # draft|published
    published_at = db.Column(db.DateTime)
    seo_title = db.Column(db.String(200))
    seo_description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)