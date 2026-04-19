from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for, abort
from app.models import Product, Category, ProductVariant, SiteSettings, Banner, Page
from app import db

store_bp = Blueprint('store', __name__)


@store_bp.route('/')
def home():
    featured = Product.query.filter_by(status='active', featured=True).limit(6).all()
    if len(featured) < 6:
        extra = Product.query.filter_by(status='active').filter(
            Product.featured == False
        ).order_by(Product.created_at.desc()).limit(6 - len(featured)).all()
        featured += extra
    categories = Category.query.filter_by(is_active=True).order_by(Category.position).all()
    hero = SiteSettings.get_all()
    return render_template('home.html', featured=featured, categories=categories, hero=hero)


@store_bp.route('/shop')
def shop():
    q = request.args.get('q', '').strip()
    gender = request.args.get('gender', '')
    category_slug = request.args.get('category', '')
    brand = request.args.get('brand', '').strip()
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)

    query = Product.query.filter_by(status='active')

    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))
    if gender:
        query = query.filter(Product.gender == gender)
    if category_slug:
        cat = Category.query.filter_by(slug=category_slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)
    if brand:
        query = query.filter(Product.brand.ilike(brand))
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.filter_by(is_active=True).order_by(Category.position).all()
    brands = [b[0] for b in db.session.query(Product.brand)
              .filter(Product.brand.isnot(None), Product.brand != '',
                      Product.status == 'active')
              .distinct().order_by(Product.brand).all()]

    return render_template('shop.html',
                           products=pagination.items,
                           pagination=pagination,
                           categories=categories,
                           brands=brands,
                           current_q=q,
                           current_gender=gender,
                           current_category=category_slug,
                           current_brand=brand,
                           current_min_price=min_price,
                           current_max_price=max_price,
                           current_sort=sort)


@store_bp.route('/wishlist')
def wishlist():
    """Wishlist page — items live in the browser's localStorage (no account needed)."""
    return render_template('wishlist.html')


@store_bp.route('/api/products-by-ids')
def products_by_ids():
    """Return minimal product data for a list of IDs (wishlist + recently viewed)."""
    ids = [i for i in (request.args.get('ids') or '').split(',') if i]
    if not ids:
        return jsonify({'products': []})
    products = Product.query.filter(Product.id.in_(ids[:60]),
                                     Product.status == 'active').all()
    data = [{
        'id': p.id, 'slug': p.slug, 'name': p.name, 'brand': p.brand or '',
        'price': float(p.price),
        'compare_at_price': float(p.compare_at_price) if p.compare_at_price else None,
        'image': p.primary_image,
        'url': url_for('store.product_detail', slug=p.slug),
    } for p in products]
    return jsonify({'products': data})


@store_bp.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, status='active').first_or_404()
    related = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.status == 'active'
    ).limit(4).all()
    return render_template('product.html', product=product, related=related)


# ── Cart (session-based) ──────────────────────────────────────────────────────

@store_bp.route('/cart/add', methods=['POST'])
def cart_add():
    data = request.get_json()
    product_id = data.get('product_id')
    variant_id = data.get('variant_id')
    quantity = int(data.get('quantity', 1))

    product = Product.query.get_or_404(product_id)
    variant = ProductVariant.query.get(variant_id) if variant_id else None

    if variant and variant.quantity < quantity:
        return jsonify({'error': 'Not enough stock'}), 400

    cart = session.get('cart', [])

    key = f'{product_id}_{variant_id}'
    for item in cart:
        if item['key'] == key:
            item['quantity'] += quantity
            break
    else:
        cart.append({
            'key': key,
            'product_id': product_id,
            'variant_id': variant_id,
            'name': product.name,
            'image': product.primary_image,
            'size': variant.size if variant else None,
            'color': variant.color if variant else None,
            'price': float(variant.effective_price if variant else product.price),
            'quantity': quantity,
        })

    session['cart'] = cart
    session.modified = True
    cart_count = sum(i['quantity'] for i in cart)
    return jsonify({'success': True, 'cart_count': cart_count})


@store_bp.route('/cart/remove', methods=['POST'])
def cart_remove():
    key = request.get_json().get('key')
    cart = [i for i in session.get('cart', []) if i['key'] != key]
    session['cart'] = cart
    session.modified = True
    return jsonify({'success': True, 'cart_count': sum(i['quantity'] for i in cart)})


@store_bp.route('/cart/update', methods=['POST'])
def cart_update():
    data = request.get_json()
    key = data.get('key')
    quantity = int(data.get('quantity', 1))
    cart = session.get('cart', [])
    for item in cart:
        if item['key'] == key:
            if quantity < 1:
                cart.remove(item)
            else:
                item['quantity'] = quantity
            break
    session['cart'] = cart
    session.modified = True
    subtotal = sum(i['price'] * i['quantity'] for i in cart)
    return jsonify({'success': True, 'subtotal': subtotal,
                    'cart_count': sum(i['quantity'] for i in cart)})


@store_bp.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    subtotal = sum(i['price'] * i['quantity'] for i in cart_items)
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal)


@store_bp.route('/p/<slug>')
def static_page(slug):
    page = Page.query.filter_by(slug=slug, status='published').first_or_404()
    s = SiteSettings.get_all()
    return render_template('page.html', page=page, s=s)


@store_bp.route('/api/variant-stock')
def variant_stock():
    product_id = request.args.get('product_id')
    size = request.args.get('size', '')
    color = request.args.get('color', '')
    variant = ProductVariant.query.filter_by(
        product_id=product_id, size=size, color=color
    ).first()
    if variant:
        return jsonify({'variant_id': variant.id, 'quantity': variant.quantity,
                        'price': float(variant.effective_price)})
    return jsonify({'variant_id': None, 'quantity': 0, 'price': 0})