import os
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, flash, current_app, jsonify)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import (Product, ProductImage, ProductVariant, Category,
                         Order, OrderItem, Customer, AdminUser, SiteSettings,
                         Banner, Page, CouponCode, ProductReview,
                         NotificationLog, NewsletterSignup, StockNotification,
                         Supplier, PurchaseOrder, PurchaseOrderItem,
                         StockAdjustment, StockMovement, Expense, BlogPost,
                         ImageTemplate)
import csv, io
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func
import re, uuid

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp', 'avif', 'mp4', 'mov', 'webm'}
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100 MB


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
    if new_status in valid and new_status != order.status:
        order.status = new_status
        db.session.commit()
        try:
            from app.notifications import send_status_update, telegram_order_status
            send_status_update(order)
            telegram_order_status(order)
        except Exception:
            pass
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

    # Pre-order settings
    product.pre_order_enabled = bool(request.form.get('pre_order_enabled'))
    po_price = request.form.get('pre_order_price', '').strip()
    po_ship = request.form.get('pre_order_shipping_fee', '').strip()
    product.pre_order_price = float(po_price) if po_price else None
    product.pre_order_shipping_fee = float(po_ship) if po_ship else None
    product.pre_order_notes = request.form.get('pre_order_notes', '').strip()

    upload_folder = current_app.config['UPLOAD_FOLDER']

    # Main product images (with optional template tag)
    images = request.files.getlist('images')
    templates = request.form.getlist('image_template[]')
    pos = product.images.count()
    for idx, f in enumerate(images):
        if f and f.filename and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            if ext in ('mp4', 'mov', 'webm'):
                f.seek(0, 2)
                size = f.tell()
                f.seek(0)
                if size > MAX_VIDEO_BYTES:
                    flash(f'Video "{f.filename}" exceeds 100 MB limit — skipped.', 'error')
                    continue
            fname = f'{uuid.uuid4()}.{ext}'
            f.save(os.path.join(upload_folder, fname))
            tpl = templates[idx] if idx < len(templates) else ''
            img = ProductImage(
                product_id=product.id,
                url=f'/static/uploads/{fname}',
                position=pos,
                image_template=tpl or None,
            )
            db.session.add(img)
            pos += 1

    db.session.flush()

    # Variants — full replacement approach:
    # Posted fields: variant_id[], variant_size[], variant_color[], variant_color_hex[],
    #                variant_qty[], variant_price[], variant_color_image[] (file)
    v_ids = request.form.getlist('variant_id[]')
    sizes = request.form.getlist('variant_size[]')
    colors = request.form.getlist('variant_color[]')
    color_hexes = request.form.getlist('variant_color_hex[]')
    qtys = request.form.getlist('variant_qty[]')
    v_prices = request.form.getlist('variant_price[]')
    color_images = request.files.getlist('variant_color_image[]')

    # Track which variant IDs were submitted (to delete removed ones)
    submitted_ids = set()

    for i, (size, color) in enumerate(zip(sizes, colors)):
        size = size.strip()
        color = color.strip()
        if not size and not color:
            continue

        vid = v_ids[i].strip() if i < len(v_ids) else ''
        qty = int(qtys[i] or 0) if i < len(qtys) else 0
        vp = float(v_prices[i]) if i < len(v_prices) and v_prices[i] else None
        hex_val = color_hexes[i] if i < len(color_hexes) else '#000000'

        # Find or create variant
        if vid:
            variant = ProductVariant.query.get(vid)
            if not variant or variant.product_id != product.id:
                variant = None
        else:
            variant = ProductVariant.query.filter_by(
                product_id=product.id, size=size, color=color).first()

        if not variant:
            variant = ProductVariant(product_id=product.id)
            db.session.add(variant)

        variant.size = size
        variant.color = color
        variant.color_hex = hex_val
        variant.quantity = qty
        variant.price = vp

        # Per-color image upload
        if i < len(color_images) and color_images[i] and color_images[i].filename and allowed_file(color_images[i].filename):
            cf = color_images[i]
            ext = cf.filename.rsplit('.', 1)[1].lower()
            fname = f'variant_{uuid.uuid4()}.{ext}'
            cf.save(os.path.join(upload_folder, fname))
            variant.color_image = f'/static/uploads/{fname}'

        db.session.flush()
        submitted_ids.add(variant.id)

    # Remove variants that were not submitted (deleted by user)
    if not is_new:
        for v in list(product.variants):
            if v.id not in submitted_ids:
                db.session.delete(v)

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
    
    # Physically remove file
    try:
        if img.url.startswith('/static/uploads/'):
            filename = os.path.basename(img.url)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                os.remove(filepath)
    except Exception as e:
        print(f"Error deleting file: {e}")

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

    # Image handling: upload new file, or preserve existing via keep_image
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
        # Delete old file before replacing
        if cat.image_url:
            old_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                                    os.path.basename(cat.image_url))
            if os.path.exists(old_path):
                os.remove(old_path)
        ext = img_file.filename.rsplit('.', 1)[1].lower()
        fname = f'cat_{uuid.uuid4()}.{ext}'
        img_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
        cat.image_url = f'/static/uploads/{fname}'
    else:
        # No new file — keep the existing image sent from the edit form
        keep = request.form.get('keep_image', '').strip()
        if keep:
            cat.image_url = keep
        # If keep is empty and no file, leave cat.image_url unchanged (new category has None)

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


# ── Analytics ─────────────────────────────────────────────────────────────────

@admin_bp.route('/analytics')
@admin_required
def analytics():
    today = datetime.utcnow().date()
    start = today - timedelta(days=29)
    prev_start = today - timedelta(days=59)

    # Daily revenue & orders (last 30 days)
    daily = {}
    for n in range(30):
        d = start + timedelta(days=n)
        daily[d.isoformat()] = {'date': d.isoformat(), 'revenue': 0.0, 'orders': 0}

    rows = db.session.query(
        func.date(Order.created_at).label('d'),
        func.count(Order.id).label('n'),
        func.sum(Order.total).label('rev'),
    ).filter(
        func.date(Order.created_at) >= start,
        Order.status != 'cancelled'
    ).group_by('d').all()

    for d, n, rev in rows:
        key = d.isoformat() if hasattr(d, 'isoformat') else str(d)
        if key in daily:
            daily[key]['orders'] = int(n or 0)
            daily[key]['revenue'] = float(rev or 0)
    daily_list = sorted(daily.values(), key=lambda r: r['date'])

    # Totals current period
    total_revenue = sum(r['revenue'] for r in daily_list)
    total_orders  = sum(r['orders']  for r in daily_list)
    avg_order = (total_revenue / total_orders) if total_orders else 0

    # Previous 30d for comparison
    prev_rev = db.session.query(func.sum(Order.total)).filter(
        func.date(Order.created_at) >= prev_start,
        func.date(Order.created_at) < start,
        Order.status != 'cancelled'
    ).scalar() or 0
    prev_orders = db.session.query(func.count(Order.id)).filter(
        func.date(Order.created_at) >= prev_start,
        func.date(Order.created_at) < start,
        Order.status != 'cancelled'
    ).scalar() or 0
    rev_change = ((total_revenue - float(prev_rev)) / float(prev_rev) * 100) if prev_rev else 0
    orders_change = ((total_orders - int(prev_orders)) / int(prev_orders) * 100) if prev_orders else 0

    # Top products (by units sold, all time)
    top_rows = db.session.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label('units'),
        func.sum(OrderItem.price * OrderItem.quantity).label('rev'),
    ).join(Order, OrderItem.order_id == Order.id).filter(
        Order.status != 'cancelled'
    ).group_by(OrderItem.product_name).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(10).all()
    top_products = [{'name': r[0], 'units': int(r[1] or 0), 'revenue': float(r[2] or 0)} for r in top_rows]

    # Status breakdown
    status_rows = db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    status_breakdown = [{'status': s, 'count': int(n)} for s, n in status_rows]
    total_all_orders = sum(s['count'] for s in status_breakdown) or 1

    # Gender breakdown (from product.gender via OrderItem → product lookup)
    gender_rows = db.session.query(
        Product.gender, func.sum(OrderItem.quantity)
    ).join(OrderItem, OrderItem.product_id == Product.id
    ).join(Order, OrderItem.order_id == Order.id
    ).filter(Order.status != 'cancelled'
    ).group_by(Product.gender).all()
    gender_data = [{'gender': g or 'Unspecified', 'units': int(u or 0)} for g, u in gender_rows]

    # Revenue by day of week (0=Mon)
    dow_totals = [0.0] * 7
    for row in daily_list:
        from datetime import date as _date
        d_obj = _date.fromisoformat(row['date'])
        dow_totals[d_obj.weekday()] += row['revenue']
    dow_labels = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

    return render_template('admin/analytics.html',
                           daily=daily_list,
                           top_products=top_products,
                           status_breakdown=status_breakdown,
                           total_all_orders=total_all_orders,
                           total_revenue=total_revenue,
                           total_orders=total_orders,
                           avg_order=avg_order,
                           rev_change=rev_change,
                           orders_change=orders_change,
                           gender_data=gender_data,
                           dow_labels=dow_labels,
                           dow_totals=dow_totals)


# ── Customer Insights ─────────────────────────────────────────────────────────

@admin_bp.route('/customer-insights')
@admin_required
def customer_insights():
    customers = Customer.query.all()
    total = len(customers)
    repeat = sum(1 for c in customers if c.order_count > 1)
    repeat_rate = (repeat / total * 100) if total else 0
    ltv = (sum(float(c.total_spent or 0) for c in customers) / total) if total else 0
    max_spent = max((float(c.total_spent or 0) for c in customers), default=0) or 1

    top = sorted(customers, key=lambda c: float(c.total_spent or 0), reverse=True)[:15]

    # New vs returning (last 30 days)
    today = datetime.utcnow().date()
    start = today - timedelta(days=29)
    new_30 = Customer.query.filter(Customer.created_at >= start).count()
    active_30 = db.session.query(Order.customer_id).filter(
        Order.created_at >= start).distinct().count()

    # Spend distribution buckets
    buckets = {'0–50': 0, '50–200': 0, '200–500': 0, '500+': 0}
    for c in customers:
        v = float(c.total_spent or 0)
        if v < 50:      buckets['0–50'] += 1
        elif v < 200:   buckets['50–200'] += 1
        elif v < 500:   buckets['200–500'] += 1
        else:           buckets['500+'] += 1

    # Monthly new customers (last 6 months)
    monthly_new = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        if i == 0:
            m_end = today
        else:
            m_end = (m_start + timedelta(days=32)).replace(day=1)
        count = Customer.query.filter(
            Customer.created_at >= m_start,
            Customer.created_at < m_end
        ).count()
        monthly_new.append({'month': m_start.strftime('%b'), 'count': count})

    return render_template('admin/customer_insights.html',
                           total=total, repeat=repeat,
                           repeat_rate=repeat_rate, ltv=ltv,
                           top_customers=top, max_spent=max_spent,
                           new_30=new_30, active_30=active_30,
                           buckets=buckets, monthly_new=monthly_new)


# ── Notifications Log ─────────────────────────────────────────────────────────

@admin_bp.route('/notifications')
@admin_required
def notifications():
    status_filter = request.args.get('status', 'all')
    channel_filter = request.args.get('channel', 'all')
    page = request.args.get('page', 1, type=int)
    q = NotificationLog.query.order_by(NotificationLog.created_at.desc())
    if status_filter != 'all':
        q = q.filter_by(status=status_filter)
    if channel_filter != 'all':
        q = q.filter_by(channel=channel_filter)
    pagination = q.paginate(page=page, per_page=50, error_out=False)
    counts = {
        'all': NotificationLog.query.count(),
        'logged': NotificationLog.query.filter_by(status='logged').count(),
        'sent': NotificationLog.query.filter_by(status='sent').count(),
        'failed': NotificationLog.query.filter_by(status='failed').count(),
    }
    return render_template('admin/notifications.html',
                           pagination=pagination,
                           current_status=status_filter,
                           current_channel=channel_filter,
                           counts=counts)


@admin_bp.route('/notifications/send-sms', methods=['POST'])
@admin_required
def send_individual_sms():
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()
    if not phone or not message:
        flash('Phone and message are required.', 'danger')
        return redirect(request.referrer or url_for('admin.notifications'))
    
    from app.notifications import send_sms
    try:
        send_sms(phone, message)
        flash(f'SMS sent to {phone}.', 'success')
    except Exception as e:
        flash(f'Failed to send SMS: {e}', 'danger')
    
    return redirect(request.referrer or url_for('admin.notifications'))


@admin_bp.route('/notifications/bulk-sms', methods=['POST'])
@admin_required
def send_bulk_sms():
    target = request.form.get('target', 'all')  # all | newsletter
    message = request.form.get('message', '').strip()
    if not message:
        flash('Message content is required.', 'danger')
        return redirect(request.referrer or url_for('admin.notifications'))
    
    from app.notifications import bulk_send_sms
    from app.models import Customer, NewsletterSignup
    
    recipients = []
    if target == 'all':
        customers = Customer.query.filter(Customer.phone != None).all()
        recipients = [c.phone for c in customers]
    elif target == 'newsletter':
        # This assumes newsletter signups have phone numbers, but they usually only have emails.
        # Let's just use all customers for now as a safe default.
        customers = Customer.query.filter(Customer.phone != None).all()
        recipients = [c.phone for c in customers]
    
    if not recipients:
        flash('No recipients found.', 'warning')
        return redirect(request.referrer or url_for('admin.notifications'))
        
    try:
        count = bulk_send_sms(message, recipients=recipients)
        flash(f'Bulk SMS campaign started for {count} recipients.', 'success')
    except Exception as e:
        flash(f'Failed to start bulk SMS: {e}', 'danger')
        
    return redirect(request.referrer or url_for('admin.notifications'))


@admin_bp.route('/notifications/schedule-sms', methods=['POST'])
@admin_required
def schedule_sms_route():
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()
    schedule_time = request.form.get('schedule_time', '').strip() # Expecting YYYY-MM-DD HH:MM
    
    if not phone or not message or not schedule_time:
        flash('All fields are required for scheduling.', 'danger')
        return redirect(request.referrer or url_for('admin.notifications'))
    
    # Simple validation of schedule_time format
    try:
        datetime.strptime(schedule_time, '%Y-%m-%d %H:%M')
    except ValueError:
        flash('Invalid date format. Use YYYY-MM-DD HH:MM', 'danger')
        return redirect(request.referrer or url_for('admin.notifications'))

    from app.notifications import schedule_sms
    try:
        schedule_sms(phone, message, schedule_time)
        flash(f'SMS scheduled for {phone} at {schedule_time}.', 'success')
    except Exception as e:
        flash(f'Failed to schedule SMS: {e}', 'danger')
        
    return redirect(request.referrer or url_for('admin.notifications'))


# ── Newsletter subscribers ────────────────────────────────────────────────────

@admin_bp.route('/newsletter')
@admin_required
def newsletter():
    items = NewsletterSignup.query.order_by(
        NewsletterSignup.created_at.desc()).all()
    return render_template('admin/newsletter.html', signups=items)


# ── Stock alert signups ───────────────────────────────────────────────────────

@admin_bp.route('/stock-alerts')
@admin_required
def stock_alerts():
    items = StockNotification.query.filter_by(notified_at=None).order_by(
        StockNotification.created_at.desc()).all()
    return render_template('admin/stock_alerts.html', signups=items)


# ══════════════════════════════════════════════════════════════════════════════
#  SUPPLIERS
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/suppliers')
@admin_required
def suppliers():
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    return render_template('admin/suppliers.html', suppliers=suppliers)


@admin_bp.route('/suppliers/save', methods=['POST'])
@admin_required
def suppliers_save():
    sid = request.form.get('id', '').strip()
    if sid:
        s = Supplier.query.get_or_404(sid)
    else:
        s = Supplier()
        db.session.add(s)
    s.name = request.form.get('name', '').strip()
    s.contact_person = request.form.get('contact_person', '').strip()
    s.phone = request.form.get('phone', '').strip()
    s.email = request.form.get('email', '').strip()
    s.address = request.form.get('address', '').strip()
    s.notes = request.form.get('notes', '').strip()
    db.session.commit()
    flash('Supplier saved.', 'success')
    return redirect(url_for('admin.suppliers'))


@admin_bp.route('/suppliers/<sid>/delete', methods=['POST'])
@admin_required
def suppliers_delete(sid):
    s = Supplier.query.get_or_404(sid)
    s.is_active = False
    db.session.commit()
    flash('Supplier removed.', 'success')
    return redirect(url_for('admin.suppliers'))


# ══════════════════════════════════════════════════════════════════════════════
#  PURCHASE ORDERS
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/purchase-orders')
@admin_required
def purchase_orders():
    pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    products = Product.query.filter_by(status='active').order_by(Product.name).all()
    return render_template('admin/purchase_orders.html',
                           purchase_orders=pos, suppliers=suppliers, products=products)


@admin_bp.route('/purchase-orders/create', methods=['POST'])
@admin_required
def purchase_orders_create():
    supplier_id = request.form.get('supplier_id')
    payment_type = request.form.get('payment_type', 'cash')
    notes = request.form.get('notes', '')
    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    unit_costs = request.form.getlist('unit_cost[]')

    if not product_ids:
        flash('Add at least one product.', 'error')
        return redirect(url_for('admin.purchase_orders'))

    # Generate PO number
    count = PurchaseOrder.query.count() + 1
    po_number = f'PO-{datetime.utcnow().strftime("%Y%m")}-{count:04d}'

    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=supplier_id or None,
        payment_type=payment_type,
        notes=notes,
    )
    db.session.add(po)
    db.session.flush()

    total = 0
    for pid, qty, cost in zip(product_ids, quantities, unit_costs):
        try:
            qty = int(qty)
            cost = float(cost)
        except (ValueError, TypeError):
            continue
        tc = qty * cost
        total += tc
        item = PurchaseOrderItem(
            purchase_order_id=po.id,
            product_id=pid,
            quantity_ordered=qty,
            unit_cost=cost,
            total_cost=tc,
        )
        db.session.add(item)

    po.total_amount = total
    db.session.commit()
    flash(f'Purchase order {po_number} created.', 'success')
    return redirect(url_for('admin.purchase_orders'))


@admin_bp.route('/purchase-orders/<po_id>/receive', methods=['POST'])
@admin_required
def purchase_orders_receive(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status in ('received', 'cancelled'):
        flash('This PO is already closed.', 'error')
        return redirect(url_for('admin.purchase_orders'))

    item_ids = request.form.getlist('item_id[]')
    recv_qtys = request.form.getlist('received_qty[]')
    fully_received = True

    for iid, rq in zip(item_ids, recv_qtys):
        item = PurchaseOrderItem.query.get(iid)
        if not item:
            continue
        try:
            rq = int(rq)
        except (ValueError, TypeError):
            continue
        if rq <= 0:
            continue
        item.quantity_received += rq
        # Update product stock
        product = Product.query.get(item.product_id)
        if product:
            before = product.stock_quantity
            product.stock_quantity += rq
            mv = StockMovement(
                product_id=product.id,
                movement_type='purchase',
                quantity_change=rq,
                quantity_before=before,
                quantity_after=product.stock_quantity,
                reference_id=po.id,
                reference_type='purchase_order',
                notes=f'Received via PO {po.po_number}',
            )
            db.session.add(mv)
        if item.quantity_received < item.quantity_ordered:
            fully_received = False

    po.status = 'received' if fully_received else 'partial'
    db.session.commit()
    flash('Stock updated from purchase order.', 'success')
    return redirect(url_for('admin.purchase_orders'))


@admin_bp.route('/purchase-orders/<po_id>/cancel', methods=['POST'])
@admin_required
def purchase_orders_cancel(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    po.status = 'cancelled'
    db.session.commit()
    flash('Purchase order cancelled.', 'success')
    return redirect(url_for('admin.purchase_orders'))


# ══════════════════════════════════════════════════════════════════════════════
#  STOCK ADJUSTMENTS
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/stock-adjustments')
@admin_required
def stock_adjustments():
    page = request.args.get('page', 1, type=int)
    reason_filter = request.args.get('reason', '')
    q = StockAdjustment.query.order_by(StockAdjustment.created_at.desc())
    if reason_filter:
        q = q.filter(StockAdjustment.reason == reason_filter)
    adjustments = q.paginate(page=page, per_page=50, error_out=False)
    products = Product.query.filter_by(status='active').order_by(Product.name).all()
    reasons = ['damage', 'theft', 'correction', 'recount', 'expired', 'other']
    return render_template('admin/stock_adjustments.html',
                           adjustments=adjustments, products=products,
                           reasons=reasons, reason_filter=reason_filter)


@admin_bp.route('/stock-adjustments/create', methods=['POST'])
@admin_required
def stock_adjustments_create():
    product_id = request.form.get('product_id')
    reason = request.form.get('reason', 'correction')
    new_qty = request.form.get('quantity_after', type=int)
    notes = request.form.get('notes', '')

    product = Product.query.get_or_404(product_id)
    before = product.stock_quantity
    change = new_qty - before

    adj = StockAdjustment(
        product_id=product.id,
        reason=reason,
        quantity_before=before,
        quantity_after=new_qty,
        quantity_change=change,
        notes=notes,
    )
    db.session.add(adj)
    product.stock_quantity = new_qty

    mv = StockMovement(
        product_id=product.id,
        movement_type='adjustment',
        quantity_change=change,
        quantity_before=before,
        quantity_after=new_qty,
        reference_id=adj.id,
        reference_type='stock_adjustment',
        notes=f'{reason}: {notes}',
    )
    db.session.add(mv)
    db.session.commit()
    flash(f'Stock adjusted: {product.name} → {new_qty} units.', 'success')
    return redirect(url_for('admin.stock_adjustments'))


# Stock movement log
@admin_bp.route('/stock-movements')
@admin_required
def stock_movements():
    page = request.args.get('page', 1, type=int)
    movements = StockMovement.query.order_by(
        StockMovement.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/stock_movements.html', movements=movements)


# ══════════════════════════════════════════════════════════════════════════════
#  EXPENSES
# ══════════════════════════════════════════════════════════════════════════════

EXPENSE_CATEGORIES = [
    'Rent', 'Utilities', 'Salaries', 'Marketing', 'Packaging',
    'Shipping Costs', 'Equipment', 'Software', 'Miscellaneous',
]

@admin_bp.route('/expenses')
@admin_required
def expenses():
    page = request.args.get('page', 1, type=int)
    cat_filter = request.args.get('category', '')
    start = request.args.get('start', '')
    end = request.args.get('end', '')

    q = Expense.query.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    if cat_filter:
        q = q.filter(Expense.category == cat_filter)
    if start:
        try:
            q = q.filter(Expense.expense_date >= datetime.strptime(start, '%Y-%m-%d').date())
        except ValueError:
            pass
    if end:
        try:
            q = q.filter(Expense.expense_date <= datetime.strptime(end, '%Y-%m-%d').date())
        except ValueError:
            pass

    expenses_page = q.paginate(page=page, per_page=50, error_out=False)
    total = db.session.query(func.sum(Expense.amount)).scalar() or 0
    return render_template('admin/expenses.html',
                           expenses=expenses_page, total=total,
                           categories=EXPENSE_CATEGORIES,
                           cat_filter=cat_filter, start=start, end=end)


@admin_bp.route('/expenses/save', methods=['POST'])
@admin_required
def expenses_save():
    eid = request.form.get('id', '').strip()
    if eid:
        e = Expense.query.get_or_404(eid)
    else:
        e = Expense()
        db.session.add(e)
    e.category = request.form.get('category', 'Miscellaneous')
    e.amount = float(request.form.get('amount', 0))
    e.description = request.form.get('description', '')
    date_str = request.form.get('expense_date', '')
    try:
        e.expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        e.expense_date = datetime.utcnow().date()
    db.session.commit()
    flash('Expense saved.', 'success')
    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/<eid>/delete', methods=['POST'])
@admin_required
def expenses_delete(eid):
    e = Expense.query.get_or_404(eid)
    db.session.delete(e)
    db.session.commit()
    flash('Expense deleted.', 'success')
    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/export')
@admin_required
def expenses_export():
    expenses = Expense.query.order_by(Expense.expense_date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Category', 'Amount (GH₵)', 'Description'])
    for e in expenses:
        writer.writerow([e.expense_date, e.category, float(e.amount), e.description or ''])
    output.seek(0)
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='application/octet-stream',
        headers={'Content-Disposition': 'attachment; filename=expenses.csv'}
    )


# ══════════════════════════════════════════════════════════════════════════════
#  AI INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/ai-insights')
@admin_required
def ai_insights():
    return render_template('admin/ai_insights.html')


@admin_bp.route('/api/ai/insights')
@admin_required
def api_ai_insights():
    from app.ai_engine import get_insights
    data = get_insights(current_app._get_current_object())
    return jsonify(data)


@admin_bp.route('/api/ai/chat', methods=['POST'])
@admin_required
def api_ai_chat():
    from app.ai_engine import chat
    data = request.json or {}
    msg = data.get('message', '').strip()
    history = data.get('history', [])
    if not msg:
        return jsonify({'response': 'Please enter a message.'}), 400
    reply = chat(current_app._get_current_object(), msg, history=history)
    return jsonify({'response': reply})


# ══════════════════════════════════════════════════════════════════════════════
#  END-OF-DAY REPORT
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/eod')
@admin_required
def eod_report():
    date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        report_date = datetime.utcnow().date()

    orders = Order.query.filter(
        func.date(Order.created_at) == report_date,
        Order.status != 'cancelled',
    ).all()

    total_orders = len(orders)
    total_revenue = sum(float(o.total) for o in orders)
    total_delivery = sum(float(o.delivery_fee) for o in orders)

    # Payment breakdown
    payment_breakdown = {}
    for o in orders:
        pm = o.payment_method or 'cash_on_delivery'
        payment_breakdown[pm] = payment_breakdown.get(pm, 0) + float(o.total)

    # Top 5 products
    from collections import Counter
    item_counts = Counter()
    for o in orders:
        for item in o.items:
            item_counts[item.product_name] += item.quantity
    top_products = item_counts.most_common(5)

    # Expenses today
    today_expenses = db.session.query(func.sum(Expense.amount))\
        .filter(Expense.expense_date == report_date).scalar() or 0

    return render_template('admin/eod_report.html',
                           report_date=report_date,
                           date_str=date_str,
                           total_orders=total_orders,
                           total_revenue=total_revenue,
                           total_delivery=total_delivery,
                           payment_breakdown=payment_breakdown,
                           top_products=top_products,
                           today_expenses=float(today_expenses))


# ══════════════════════════════════════════════════════════════════════════════
#  ORDERS — CSV export
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/orders/export')
@admin_required
def orders_export():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Order #', 'Date', 'Customer', 'Phone', 'City',
                     'Subtotal', 'Delivery', 'Total', 'Status', 'Payment'])
    for o in orders:
        writer.writerow([
            o.order_number,
            o.created_at.strftime('%Y-%m-%d %H:%M'),
            o.delivery_name, o.delivery_phone, o.delivery_city,
            float(o.subtotal), float(o.delivery_fee), float(o.total),
            o.status, o.payment_method,
        ])
    output.seek(0)
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='application/octet-stream',
        headers={'Content-Disposition': 'attachment; filename=orders.csv'}
    )


# ══════════════════════════════════════════════════════════════════════════════
#  BLOG / POSTS
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/blog')
@admin_required
def blog():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('admin/blog.html', posts=posts)


@admin_bp.route('/blog/new', methods=['GET', 'POST'])
@admin_required
def blog_new():
    if request.method == 'POST':
        return _blog_save(None)
    return render_template('admin/blog_edit.html', post=None)


@admin_bp.route('/blog/<post_id>/edit', methods=['GET', 'POST'])
@admin_required
def blog_edit(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if request.method == 'POST':
        return _blog_save(post)
    return render_template('admin/blog_edit.html', post=post)


def _blog_save(post):
    is_new = post is None
    if is_new:
        post = BlogPost()
        db.session.add(post)
    post.title = request.form.get('title', '').strip()
    raw_slug = request.form.get('slug', '').strip() or post.title.lower()
    post.slug = re.sub(r'[^a-z0-9-]', '-', raw_slug.lower()).strip('-')
    post.excerpt = request.form.get('excerpt', '').strip()
    post.body = request.form.get('body', '').strip()
    post.seo_title = request.form.get('seo_title', '').strip()
    post.seo_description = request.form.get('seo_description', '').strip()
    status = request.form.get('status', 'draft')
    post.status = status
    if status == 'published' and not post.published_at:
        post.published_at = datetime.utcnow()
    db.session.commit()
    flash('Post saved.', 'success')
    return redirect(url_for('admin.blog'))


@admin_bp.route('/blog/<post_id>/delete', methods=['POST'])
@admin_required
def blog_delete(post_id):
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'success')
    return redirect(url_for('admin.blog'))


# ══════════════════════════════════════════════════════════════════════════════
#  BANNER ADMIN (full CRUD already exists — add activate/deactivate toggle)
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/banners/<banner_id>/toggle', methods=['POST'])
@admin_required
def banners_toggle(banner_id):
    b = Banner.query.get_or_404(banner_id)
    b.is_active = not b.is_active
    db.session.commit()
    state = 'activated' if b.is_active else 'deactivated'
    flash(f'Banner {state}.', 'success')
    return redirect(url_for('admin.banners'))


# ══════════════════════════════════════════════════════════════════════════════
#  TELEGRAM BOT WEBHOOK  — admin can chat with AI via Telegram
# ══════════════════════════════════════════════════════════════════════════════

# In-memory conversation histories per Telegram chat_id (reset on restart)
_tg_histories = {}

@admin_bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """
    Telegram bot webhook. Register with:
      POST https://api.telegram.org/bot<TOKEN>/setWebhook
      {"url": "https://yourdomain.com/admin/telegram/webhook"}
    Only responds to messages from the configured TELEGRAM_CHAT_ID.
    """
    import os
    from app.notifications import send_chat_action
    
    data = request.get_json(silent=True) or {}
    
    # Handle both new and edited messages
    is_edit = 'edited_message' in data
    message = data.get('edited_message') or data.get('message') or {}
    
    chat = message.get('chat', {})
    chat_id = str(chat.get('id', ''))
    text = (message.get('text') or '').strip()
    msg_id = message.get('message_id')
    reply_to = message.get('reply_to_message', {}).get('text', '')

    allowed_chat = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not chat_id or not text or chat_id != allowed_chat:
        return jsonify({'ok': True})

    # Show typing status immediately
    send_chat_action('typing')

    # Handle special commands
    if text.startswith('/'):
        cmd = text.split()[0].lower()
        if cmd == '/start':
            _reply_telegram(chat_id, '👋 Hi! I\'m your Slidein GH AI assistant.\n\nAsk me anything about your sales, stock, customers, or strategy. Type /stats for a quick snapshot or /report for today\'s full report.')
            return jsonify({'ok': True})
        if cmd == '/stats':
            try:
                from app.ai_engine import get_context
                ctx = get_context(current_app._get_current_object())
                msg = (
                    f'📊 <b>Quick Stats — Slidein GH</b>\n'
                    f'────────────────\n'
                    f'📦 Today: {ctx["sales_today"]["count"]} orders · GH₵{ctx["sales_today"]["revenue"]:,.2f}\n'
                    f'📈 7-Day: {ctx["sales_7d"]["count"]} orders · GH₵{ctx["sales_7d"]["revenue"]:,.2f}\n'
                    f'💰 30-Day Revenue: GH₵{ctx["sales_30d"]["revenue"]:,.2f}\n'
                    f'💸 30-Day Expenses: GH₵{ctx["expenses_30d"]:,.2f}\n'
                    f'📉 Est. Profit: GH₵{ctx["profit_estimate_30d"]:,.2f}\n'
                    f'👥 Customers: {ctx["total_customers"]} ({ctx["repeat_customers"]} repeat)\n'
                    f'⚠️ Low stock: {ctx["low_stock_variants"]} variants · {ctx["out_of_stock_variants"]} out\n'
                    f'🕐 Pending orders: {ctx["pending_orders"]}'
                )
                _reply_telegram(chat_id, msg)
            except Exception as e:
                _reply_telegram(chat_id, f'⚠️ Could not fetch stats: {e}')
            return jsonify({'ok': True})
        if cmd == '/report':
            try:
                from app.ai_engine import get_health_report
                report = get_health_report(current_app._get_current_object())
                _reply_telegram(chat_id, f'📋 <b>Daily Report</b>\n\n{report}')
            except Exception as e:
                _reply_telegram(chat_id, f'⚠️ Report unavailable: {e}')
            return jsonify({'ok': True})
        if cmd == '/clear':
            _tg_histories.pop(chat_id, None)
            _reply_telegram(chat_id, '🗑 Conversation cleared.')
            return jsonify({'ok': True})

    # AI chat
    try:
        from app.ai_engine import chat as ai_chat
        history = _tg_histories.get(chat_id, [])
        
        # Add reply context if any
        prompt = text
        if reply_to:
            prompt = f"Context from previous message: \"{reply_to}\"\n\nUser Question: {text}"
            
        reply = ai_chat(current_app._get_current_object(), prompt, history=history)
        
        # Track history
        history.append({'role': 'user', 'content': text})
        history.append({'role': 'assistant', 'content': reply})
        _tg_histories[chat_id] = history[-16:]  # keep last 8 exchanges
        
        _reply_telegram(chat_id, reply)
    except Exception as e:
        _reply_telegram(chat_id, f'⚠️ AI error: {e}')

    return jsonify({'ok': True})


def _reply_telegram(chat_id, text):
    import os
    import requests as _req
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return
    try:
        _req.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'},
            timeout=10,
        )
    except Exception:
        pass


# ── AI Smart Helpers ──────────────────────────────────────────────────────────

@admin_bp.route('/api/ai/generate-description', methods=['POST'])
@admin_required
def api_ai_generate_description():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    brand = data.get('brand', '').strip()
    if not name:
        return jsonify({'error': 'Product name required'}), 400
    try:
        from app import ai_engine
        prompt = (
            f"Write a compelling, concise product description (3-4 sentences, no bullet points) "
            f"for a sneaker called '{name}'"
            + (f" by {brand}" if brand else "")
            + ". Target Ghanaian sneaker enthusiasts. Focus on style, comfort, and exclusivity. "
            "Keep it punchy and exciting. Do not include price."
        )
        client, _ = ai_engine._groq_client()
        if not client:
            return jsonify({'error': 'AI not configured. Add GROQ_API_KEY to .env'}), 400
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=200,
            temperature=0.8,
        )
        desc = resp.choices[0].message.content.strip()
        return jsonify({'description': desc})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/ai/stale-products')
@admin_required
def api_ai_stale_products():
    """Return products with zero sales in the last 30 days — suggest discounts."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    sold_ids = db.session.query(OrderItem.product_id).join(Order).filter(
        Order.created_at >= cutoff
    ).distinct().subquery()
    stale = Product.query.filter(
        Product.status == 'active',
        ~Product.id.in_(sold_ids)
    ).order_by(Product.created_at).limit(10).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': float(p.price),
        'days_listed': (datetime.utcnow() - p.created_at).days,
        'url': url_for('admin.product_edit', product_id=p.id),
    } for p in stale])


# ── Image Templates ───────────────────────────────────────────────────────────

@admin_bp.route('/image-templates')
@admin_required
def image_templates():
    templates = ImageTemplate.query.order_by(ImageTemplate.sort_order, ImageTemplate.name).all()
    return render_template('image_templates.html', templates=templates)


@admin_bp.route('/image-templates/save', methods=['POST'])
@admin_required
def image_template_save():
    tid = request.form.get('id', '').strip()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Template name is required.', 'error')
        return redirect(url_for('admin.image_templates'))

    if tid:
        tmpl = ImageTemplate.query.get_or_404(tid)
    else:
        tmpl = ImageTemplate()
        db.session.add(tmpl)

    tmpl.name = name
    tmpl.slug = slugify(name) + '-' + str(uuid.uuid4())[:4]
    tmpl.description = request.form.get('description', '').strip()
    tmpl.background_css = request.form.get('background_css', '').strip()
    tmpl.overlay_css = request.form.get('overlay_css', '').strip()
    tmpl.sort_order = int(request.form.get('sort_order', 0) or 0)
    tmpl.is_active = 'is_active' in request.form

    # Background image upload
    bg_file = request.files.get('background_image_file')
    if bg_file and bg_file.filename and allowed_file(bg_file.filename):
        ext = bg_file.filename.rsplit('.', 1)[1].lower()
        fname = f'tmpl_{uuid.uuid4().hex}.{ext}'
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'templates')
        os.makedirs(upload_dir, exist_ok=True)
        bg_file.save(os.path.join(upload_dir, fname))
        tmpl.background_image = url_for('static', filename=f'uploads/templates/{fname}')
    elif request.form.get('background_image_url', '').strip():
        tmpl.background_image = request.form.get('background_image_url').strip()

    db.session.commit()
    flash('Template saved.', 'success')
    return redirect(url_for('admin.image_templates'))


@admin_bp.route('/image-templates/delete/<tid>', methods=['POST'])
@admin_required
def image_template_delete(tid):
    tmpl = ImageTemplate.query.get_or_404(tid)
    db.session.delete(tmpl)
    db.session.commit()
    flash('Template deleted.', 'success')
    return redirect(url_for('admin.image_templates'))


@admin_bp.route('/api/image-templates')
@admin_required
def api_image_templates():
    templates = ImageTemplate.query.filter_by(is_active=True).order_by(ImageTemplate.sort_order).all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'background_image': t.background_image,
        'background_css': t.background_css,
        'overlay_css': t.overlay_css,
        'bg_style': t.bg_style,
    } for t in templates])


@admin_bp.route('/telegram/setup')
@admin_required
def telegram_setup():
    """One-click webhook registration helper."""
    import os, requests as _req
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return jsonify({'error': 'TELEGRAM_BOT_TOKEN not set in .env'}), 400
    host = request.host_url.rstrip('/')
    webhook_url = f'{host}/admin/telegram/webhook'
    try:
        r = _req.post(
            f'https://api.telegram.org/bot{token}/setWebhook',
            json={'url': webhook_url, 'allowed_updates': ['message']},
            timeout=10,
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500
