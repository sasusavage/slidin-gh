import os
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, flash, current_app, jsonify)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import (Product, ProductImage, ProductVariant, Category,
                         Order, Customer, AdminUser, SiteSettings,
                         Banner, Page, CouponCode, ProductReview)
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

    # Optional category image upload (max 4 MB)
    img_file = request.files.get('image')
    if img_file and img_file.filename:
        if not allowed_file(img_file.filename):
            flash('Invalid image type. Use PNG, JPG, WEBP or AVIF.', 'error')
            return redirect(url_for('admin.categories'))
        img_file.seek(0, 2)
        size = img_file.tell()
        img_file.seek(0)
        if size > 4 * 1024 * 1024:
            flash('Image must be under 4 MB.', 'error')
            return redirect(url_for('admin.categories'))
        # Delete old file if replacing
        if cat.image_url:
            old_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                                    os.path.basename(cat.image_url))
            if os.path.exists(old_path):
                os.remove(old_path)
        ext = img_file.filename.rsplit('.', 1)[1].lower()
        fname = f'cat_{uuid.uuid4()}.{ext}'
        img_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
        cat.image_url = f'/static/uploads/{fname}'

    db.session.commit()
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<cat_id>/image/delete', methods=['POST'])
@admin_required
def category_image_delete(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if cat.image_url:
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                                os.path.basename(cat.image_url))
        if os.path.exists(old_path):
            os.remove(old_path)
        cat.image_url = None
        db.session.commit()
    return redirect(url_for('admin.categories'))


# ── CMS / Site Settings ───────────────────────────────────────────────────────

@admin_bp.route('/cms')
@admin_required
def cms():
    return redirect(url_for('admin.settings'))


_ALL_SETTING_KEYS = [
    'site_name','site_tagline','site_logo','site_favicon',
    'contact_email','contact_phone','contact_address','currency','currency_symbol',
    'social_instagram','social_facebook','social_twitter','social_tiktok','social_whatsapp',
    'primary_color','secondary_color','accent_color',
    'hero_style','hero_media_type','hero_media_url','hero_label','hero_title','hero_subheadline',
    'hero_cta_primary_text','hero_cta_primary_url','hero_cta_secondary_text','hero_cta_secondary_url',
    'hero_badge_label','hero_badge_text','hero_badge_subtext',
    'hero_stat1_title','hero_stat1_desc','hero_stat2_title','hero_stat2_desc',
    'hero_stat3_title','hero_stat3_desc',
    'feature1_icon','feature1_title','feature1_desc',
    'feature2_icon','feature2_title','feature2_desc',
    'feature3_icon','feature3_title','feature3_desc',
    'feature4_icon','feature4_title','feature4_desc',
    'announcement_bar_text','announcement_bar_active',
    'header_show_search','header_nav_links_json',
    'footer_col1_title','footer_col1_links_json',
    'footer_col2_title','footer_col2_links_json',
    'footer_col3_title','footer_col3_links_json',
    'footer_copyright_text','footer_show_newsletter',
    'footer_newsletter_title','footer_newsletter_subtitle',
    'about_hero_title','about_hero_subtitle','about_story_title','about_story_content',
    'about_story_image','about_founder_name','about_founder_title',
    'about_mission1_title','about_mission1_content','about_mission2_title','about_mission2_content',
    'about_cta_title','about_cta_subtitle',
    'contact_hero_title','contact_hero_subtitle','contact_hours','contact_whatsapp_hours',
    'contact_map_link','contact_team_json',
    'seo_title','seo_description','seo_keywords','seo_og_image','seo_google_analytics',
]


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        for key in _ALL_SETTING_KEYS:
            val = request.form.get(key, '').strip()
            SiteSettings.set(key, val)

        # Handle file uploads that override URL fields
        _upload_map = {
            'site_logo_file': 'site_logo',
            'site_favicon_file': 'site_favicon',
            'hero_media_file': 'hero_media_url',
            'about_story_image_file': 'about_story_image',
            'seo_og_image_file': 'seo_og_image',
        }
        for field, setting_key in _upload_map.items():
            f = request.files.get(field)
            if f and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                fname = f'{setting_key}_{uuid.uuid4()}.{ext}'
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
                SiteSettings.set(setting_key, f'/static/uploads/{fname}')

        db.session.commit()
        flash('Settings saved.', 'success')
        tab = request.form.get('_tab', 'general')
        return redirect(url_for('admin.settings') + f'?tab={tab}')

    s = SiteSettings.get_all()
    tab = request.args.get('tab', 'general')
    return render_template('admin/settings.html', s=s, tab=tab)


# ── Banners ───────────────────────────────────────────────────────────────────

@admin_bp.route('/banners')
@admin_required
def banners():
    items = Banner.query.order_by(Banner.sort_order, Banner.created_at.desc()).all()
    return render_template('admin/banners.html', banners=items)


@admin_bp.route('/banners/save', methods=['POST'])
@admin_required
def banner_save():
    bid = request.form.get('id')
    if bid:
        banner = Banner.query.get_or_404(bid)
    else:
        banner = Banner(id=str(uuid.uuid4()))
        db.session.add(banner)

    banner.name = request.form.get('name', '').strip() or 'Banner'
    banner.type = request.form.get('type', 'promotional')
    banner.title = request.form.get('title', '').strip()
    banner.subtitle = request.form.get('subtitle', '').strip()
    banner.background_color = request.form.get('background_color', '#000000')
    banner.text_color = request.form.get('text_color', '#FFFFFF')
    banner.button_text = request.form.get('button_text', '').strip()
    banner.button_url = request.form.get('button_url', '').strip()
    banner.position = request.form.get('position', 'top')
    banner.sort_order = int(request.form.get('sort_order', 0))
    banner.is_active = bool(request.form.get('is_active'))

    sd = request.form.get('start_date', '').strip()
    ed = request.form.get('end_date', '').strip()
    banner.start_date = datetime.fromisoformat(sd) if sd else None
    banner.end_date = datetime.fromisoformat(ed) if ed else None

    img_file = request.files.get('image')
    if img_file and allowed_file(img_file.filename):
        ext = img_file.filename.rsplit('.', 1)[1].lower()
        fname = f'banner_{uuid.uuid4()}.{ext}'
        img_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
        banner.image_url = f'/static/uploads/{fname}'

    db.session.commit()
    flash('Banner saved.', 'success')
    return redirect(url_for('admin.banners'))


@admin_bp.route('/banners/<banner_id>/delete', methods=['POST'])
@admin_required
def banner_delete(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    db.session.delete(banner)
    db.session.commit()
    return redirect(url_for('admin.banners'))


# ── CMS Pages ─────────────────────────────────────────────────────────────────

@admin_bp.route('/pages')
@admin_required
def pages():
    items = Page.query.order_by(Page.updated_at.desc()).all()
    return render_template('admin/pages.html', pages=items)


@admin_bp.route('/pages/new', methods=['GET', 'POST'])
@admin_required
def page_new():
    if request.method == 'POST':
        return _save_page(None)
    return render_template('admin/page_form.html', page=None)


@admin_bp.route('/pages/<page_id>/edit', methods=['GET', 'POST'])
@admin_required
def page_edit(page_id):
    page = Page.query.get_or_404(page_id)
    if request.method == 'POST':
        return _save_page(page)
    return render_template('admin/page_form.html', page=page)


def _save_page(page):
    title = request.form.get('title', '').strip()
    if not title:
        flash('Title is required.', 'error')
        return redirect(request.url)
    is_new = page is None
    if is_new:
        page = Page(id=str(uuid.uuid4()))
        db.session.add(page)
    page.title = title
    page.slug = request.form.get('slug', '').strip() or slugify(title)
    page.content = request.form.get('content', '')
    page.status = request.form.get('status', 'draft')
    page.seo_title = request.form.get('seo_title', '').strip()
    page.seo_description = request.form.get('seo_description', '').strip()
    db.session.commit()
    flash(f'Page {"created" if is_new else "updated"}.', 'success')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<page_id>/delete', methods=['POST'])
@admin_required
def page_delete(page_id):
    page = Page.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    return redirect(url_for('admin.pages'))


# ── Coupons ───────────────────────────────────────────────────────────────────

@admin_bp.route('/coupons')
@admin_required
def coupons():
    items = CouponCode.query.order_by(CouponCode.created_at.desc()).all()
    return render_template('admin/coupons.html', coupons=items)


@admin_bp.route('/coupons/save', methods=['POST'])
@admin_required
def coupon_save():
    cid = request.form.get('id')
    if cid:
        coupon = CouponCode.query.get_or_404(cid)
    else:
        coupon = CouponCode(id=str(uuid.uuid4()))
        db.session.add(coupon)

    coupon.code = request.form.get('code', '').strip().upper()
    coupon.description = request.form.get('description', '').strip()
    coupon.discount_type = request.form.get('discount_type', 'percent')
    coupon.discount_value = float(request.form.get('discount_value', 0))
    coupon.min_order_amount = float(request.form.get('min_order_amount', 0) or 0)
    max_uses = request.form.get('max_uses', '').strip()
    coupon.max_uses = int(max_uses) if max_uses else None
    coupon.is_active = bool(request.form.get('is_active'))

    sd = request.form.get('start_date', '').strip()
    ed = request.form.get('end_date', '').strip()
    coupon.start_date = datetime.fromisoformat(sd) if sd else None
    coupon.end_date = datetime.fromisoformat(ed) if ed else None

    db.session.commit()
    flash('Coupon saved.', 'success')
    return redirect(url_for('admin.coupons'))


@admin_bp.route('/coupons/<coupon_id>/delete', methods=['POST'])
@admin_required
def coupon_delete(coupon_id):
    coupon = CouponCode.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    return redirect(url_for('admin.coupons'))


@admin_bp.route('/coupons/validate', methods=['POST'])
def coupon_validate():
    """Called by checkout JS to validate a coupon code."""
    code = request.json.get('code', '').strip().upper()
    amount = float(request.json.get('amount', 0))
    coupon = CouponCode.query.filter_by(code=code).first()
    if not coupon or not coupon.is_valid:
        return jsonify({'valid': False, 'message': 'Invalid or expired coupon.'})
    if amount < float(coupon.min_order_amount):
        return jsonify({'valid': False,
                        'message': f'Minimum order GH₵{coupon.min_order_amount:.0f} required.'})
    if coupon.discount_type == 'percent':
        discount = round(amount * float(coupon.discount_value) / 100, 2)
        label = f'{coupon.discount_value:.0f}% off'
    else:
        discount = min(float(coupon.discount_value), amount)
        label = f'GH₵{coupon.discount_value:.2f} off'
    return jsonify({'valid': True, 'discount': discount, 'label': label,
                    'coupon_id': coupon.id})

# ── Inventory ─────────────────────────────────────────────────────────────────

@admin_bp.route('/inventory')
@admin_required
def inventory():
    q = request.args.get('q', '').strip()
    stock_filter = request.args.get('stock', 'all')  # all | low | out | good

    query = ProductVariant.query.join(Product).filter(Product.status == 'active')

    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))

    variants = query.order_by(Product.name).all()

    if stock_filter == 'out':
        variants = [v for v in variants if v.quantity == 0]
    elif stock_filter == 'low':
        variants = [v for v in variants if 0 < v.quantity <= 5]
    elif stock_filter == 'good':
        variants = [v for v in variants if v.quantity > 5]

    total_variants = len(variants)
    out_count = sum(1 for v in variants if v.quantity == 0)
    low_count = sum(1 for v in variants if 0 < v.quantity <= 5)

    return render_template('admin/inventory.html',
                           variants=variants,
                           current_q=q,
                           current_stock=stock_filter,
                           total_variants=total_variants,
                           out_count=out_count,
                           low_count=low_count)


@admin_bp.route('/inventory/update', methods=['POST'])
@admin_required
def inventory_update():
    """Inline stock update — called by JS fetch."""
    variant_id = request.json.get('variant_id')
    qty = request.json.get('quantity')
    if variant_id is None or qty is None:
        return jsonify({'error': 'Missing fields'}), 400
    variant = ProductVariant.query.get_or_404(variant_id)
    variant.quantity = max(0, int(qty))
    db.session.commit()
    return jsonify({'success': True, 'quantity': variant.quantity})


# ── Reviews ───────────────────────────────────────────────────────────────────

@admin_bp.route('/reviews')
@admin_required
def reviews():
    status_filter = request.args.get('status', 'all')
    q = ProductReview.query.order_by(ProductReview.created_at.desc())
    if status_filter != 'all':
        q = q.filter_by(status=status_filter)
    items = q.all()
    counts = {
        'all': ProductReview.query.count(),
        'pending': ProductReview.query.filter_by(status='pending').count(),
        'approved': ProductReview.query.filter_by(status='approved').count(),
        'rejected': ProductReview.query.filter_by(status='rejected').count(),
    }
    return render_template('admin/reviews.html', reviews=items,
                           current_status=status_filter, counts=counts)


@admin_bp.route('/reviews/<review_id>/status', methods=['POST'])
@admin_required
def review_status(review_id):
    review = ProductReview.query.get_or_404(review_id)
    new_status = request.form.get('status')
    if new_status in ('pending', 'approved', 'rejected'):
        review.status = new_status
        db.session.commit()
    return redirect(url_for('admin.reviews',
                            status=request.args.get('status', 'all')))


@admin_bp.route('/reviews/<review_id>/delete', methods=['POST'])
@admin_required
def review_delete(review_id):
    review = ProductReview.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    return redirect(url_for('admin.reviews'))
