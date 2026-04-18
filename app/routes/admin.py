import os
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, flash, current_app, jsonify)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import (Product, ProductImage, ProductVariant, Category,
                         Order, Customer, AdminUser, SiteSettings)
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func
import re, uuid

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp', 'avif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


# ── Auth ──────────────────────────────────────────────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == current_app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect(url_for('admin.dashboard'))
        error = 'Invalid password.'
    return render_template('admin/login.html', error=error)


@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def dashboard():
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)

    total_orders = Order.query.count()
    total_revenue = db.session.query(func.sum(Order.total)).filter(
        Order.status != 'cancelled').scalar() or 0
    total_customers = Customer.query.count()
    total_products = Product.query.filter_by(status='active').count()

    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()

    weekly_orders = Order.query.filter(
        func.date(Order.created_at) >= week_ago
    ).count()

    low_stock = ProductVariant.query.filter(
        ProductVariant.quantity > 0,
        ProductVariant.quantity <= 3
    ).all()

    return render_template('admin/dashboard.html',
                           total_orders=total_orders,
                           total_revenue=total_revenue,
                           total_customers=total_customers,
                           total_products=total_products,
                           recent_orders=recent_orders,
                           weekly_orders=weekly_orders,
                           low_stock=low_stock)


# ── Orders ────────────────────────────────────────────────────────────────────

@admin_bp.route('/orders')
@admin_required
def orders():
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    q = Order.query.order_by(Order.created_at.desc())
    if status_filter:
        q = q.filter_by(status=status_filter)
    pagination = q.paginate(page=page, per_page=25, error_out=False)
    return render_template('admin/orders.html', pagination=pagination,
                           current_status=status_filter)


@admin_bp.route('/orders/<order_id>')
@admin_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_detail.html', order=order)


@admin_bp.route('/orders/<order_id>/status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    valid = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
    if new_status in valid:
        order.status = new_status
        db.session.commit()
    return redirect(url_for('admin.order_detail', order_id=order_id))


# ── Customers (CRM) ──────────────────────────────────────────────────────────

@admin_bp.route('/customers')
@admin_required
def customers():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Customer.query.order_by(Customer.created_at.desc())
    if q:
        query = query.filter(
            (Customer.full_name.ilike(f'%{q}%')) |
            (Customer.phone.ilike(f'%{q}%')) |
            (Customer.email.ilike(f'%{q}%'))
        )
    pagination = query.paginate(page=page, per_page=25, error_out=False)
    return render_template('admin/customers.html', pagination=pagination, current_q=q)


@admin_bp.route('/customers/<customer_id>')
@admin_required
def customer_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    orders = customer.orders.order_by(Order.created_at.desc()).all()
    return render_template('admin/customer_detail.html', customer=customer, orders=orders)


@admin_bp.route('/customers/<customer_id>/note', methods=['POST'])
@admin_required
def customer_note(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.notes = request.form.get('notes', '')
    db.session.commit()
    return redirect(url_for('admin.customer_detail', customer_id=customer_id))


# ── Products ──────────────────────────────────────────────────────────────────

@admin_bp.route('/products')
@admin_required
def products():
    page = request.args.get('page', 1, type=int)
    pagination = Product.query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('admin/products.html', pagination=pagination)


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    categories = Category.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        return _save_product(None, categories)
    return render_template('admin/product_form.html', product=None, categories=categories)


@admin_bp.route('/products/<product_id>/edit', methods=['GET', 'POST'])
@admin_required
def product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        return _save_product(product, categories)
    return render_template('admin/product_form.html', product=product, categories=categories)


def _save_product(product, categories):
    name = request.form.get('name', '').strip()
    if not name:
        flash('Product name is required.', 'error')
        return redirect(request.url)

    is_new = product is None
    if is_new:
        product = Product(id=str(uuid.uuid4()))
        db.session.add(product)

    product.name = name
    product.slug = slugify(name) + ('-' + str(uuid.uuid4())[:4] if is_new else '')
    product.description = request.form.get('description', '')
    product.price = float(request.form.get('price', 0))
    product.compare_at_price = request.form.get('compare_at_price') or None
    product.category_id = request.form.get('category_id') or None
    product.gender = request.form.get('gender', '')
    product.brand = request.form.get('brand', '')
    product.status = request.form.get('status', 'active')
    product.featured = bool(request.form.get('featured'))

    # Handle image uploads
    upload_folder = current_app.config['UPLOAD_FOLDER']
    images = request.files.getlist('images')
    pos = product.images.count()
    for f in images:
        if f and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            fname = f'{uuid.uuid4()}.{ext}'
            f.save(os.path.join(upload_folder, fname))
            img = ProductImage(
                product_id=product.id,
                url=f'/static/uploads/{fname}',
                position=pos,
            )
            db.session.add(img)
            pos += 1

    db.session.flush()

    # Variants: sizes × colors grid submitted as JSON-ish form fields
    # Expects: variant_size[], variant_color[], variant_color_hex[], variant_qty[], variant_price[]
    sizes = request.form.getlist('variant_size[]')
    colors = request.form.getlist('variant_color[]')
    color_hexes = request.form.getlist('variant_color_hex[]')
    qtys = request.form.getlist('variant_qty[]')
    v_prices = request.form.getlist('variant_price[]')

    for i, (size, color) in enumerate(zip(sizes, colors)):
        size = size.strip()
        color = color.strip()
        if not size and not color:
            continue
        existing = ProductVariant.query.filter_by(
            product_id=product.id, size=size, color=color).first()
        if existing:
            existing.quantity = int(qtys[i] or 0)
            existing.price = float(v_prices[i]) if v_prices[i] else None
        else:
            v = ProductVariant(
                product_id=product.id,
                size=size,
                color=color,
                color_hex=color_hexes[i] if i < len(color_hexes) else None,
                quantity=int(qtys[i] or 0),
                price=float(v_prices[i]) if v_prices[i] else None,
            )
            db.session.add(v)

    db.session.commit()
    flash(f'Product {"created" if is_new else "updated"}.', 'success')
    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<product_id>/delete', methods=['POST'])
@admin_required
def product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    product.status = 'archived'
    db.session.commit()
    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<product_id>/image/<image_id>/delete', methods=['POST'])
@admin_required
def product_image_delete(product_id, image_id):
    img = ProductImage.query.filter_by(id=image_id, product_id=product_id).first_or_404()
    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': True})


# ── Categories ────────────────────────────────────────────────────────────────

@admin_bp.route('/categories')
@admin_required
def categories():
    cats = Category.query.order_by(Category.position).all()
    return render_template('admin/categories.html', categories=cats)


@admin_bp.route('/categories/save', methods=['POST'])
@admin_required
def category_save():
    cat_id = request.form.get('id')
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('admin.categories'))

    if cat_id:
        cat = Category.query.get_or_404(cat_id)
    else:
        cat = Category(id=str(uuid.uuid4()))
        db.session.add(cat)

    cat.name = name
    cat.slug = slugify(name)
    cat.description = request.form.get('description', '')
    cat.position = int(request.form.get('position', 0))
    cat.is_active = bool(request.form.get('is_active'))

    # Optional category image upload
    img_file = request.files.get('image')
    if img_file and allowed_file(img_file.filename):
        ext = img_file.filename.rsplit('.', 1)[1].lower()
        fname = f'cat_{uuid.uuid4()}.{ext}'
        img_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
        cat.image_url = f'/static/uploads/{fname}'

    db.session.commit()
    return redirect(url_for('admin.categories'))


# ── CMS / Site Settings ───────────────────────────────────────────────────────

@admin_bp.route('/cms', methods=['GET', 'POST'])
@admin_required
def cms():
    if request.method == 'POST':
        keys = [
            'hero_style', 'hero_media_type', 'hero_media_url',
            'hero_label', 'hero_title',
            'hero_cta_primary_text', 'hero_cta_primary_url',
            'hero_cta_secondary_text', 'hero_cta_secondary_url',
            'announcement_bar_text', 'announcement_bar_active',
            'site_name',
        ]
        for key in keys:
            val = request.form.get(key, '').strip()
            SiteSettings.set(key, val)

        # Hero media file upload (optional — overrides hero_media_url if provided)
        hero_file = request.files.get('hero_media_file')
        if hero_file and allowed_file(hero_file.filename):
            ext = hero_file.filename.rsplit('.', 1)[1].lower()
            fname = f'hero_{uuid.uuid4()}.{ext}'
            hero_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
            SiteSettings.set('hero_media_url', f'/static/uploads/{fname}')

        db.session.commit()
        flash('Site settings saved.', 'success')
        return redirect(url_for('admin.cms'))

    settings = SiteSettings.get_all()
    return render_template('admin/cms.html', s=settings)