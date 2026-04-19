from flask import (Blueprint, render_template, request, session, jsonify,
                   url_for, Response)
from app.models import (Product, Category, ProductVariant, SiteSettings,
                         Page, ProductReview, StockNotification, NewsletterSignup,
                         Order)
from app import db
from datetime import datetime
from sqlalchemy import func

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
    size = request.args.get('size', '').strip()
    color = request.args.get('color', '').strip()
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
    if size:
        query = query.join(ProductVariant).filter(ProductVariant.size == size,
                                                   ProductVariant.quantity > 0).distinct()
    if color:
        query = query.join(ProductVariant).filter(ProductVariant.color.ilike(color)).distinct()
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
    all_sizes = sorted({v.size for v in ProductVariant.query
                        .filter(ProductVariant.size.isnot(None),
                                ProductVariant.size != '').all()})
    all_colors = sorted({v.color for v in ProductVariant.query
                         .filter(ProductVariant.color.isnot(None),
                                 ProductVariant.color != '').all()})

    return render_template('shop.html',
                           products=pagination.items,
                           pagination=pagination,
                           categories=categories,
                           brands=brands,
                           all_sizes=all_sizes,
                           all_colors=all_colors,
                           current_q=q,
                           current_gender=gender,
                           current_category=category_slug,
                           current_brand=brand,
                           current_size=size,
                           current_color=color,
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
    reviews = ProductReview.query.filter_by(
        product_id=product.id, status='approved'
    ).order_by(ProductReview.created_at.desc()).limit(20).all()
    avg = db.session.query(func.avg(ProductReview.rating)).filter_by(
        product_id=product.id, status='approved').scalar()
    review_stats = {
        'count': len(reviews),
        'avg': round(float(avg), 1) if avg else 0,
    }
    return render_template('product.html', product=product, related=related,
                           reviews=reviews, review_stats=review_stats)


@store_bp.route('/product/<product_id>/review', methods=['POST'])
def submit_review(product_id):
    product = Product.query.get_or_404(product_id)
    name = (request.form.get('name') or '').strip()
    rating = request.form.get('rating', type=int)
    title = (request.form.get('title') or '').strip()
    content = (request.form.get('content') or '').strip()
    email = (request.form.get('email') or '').strip()
    if not name or not rating or rating < 1 or rating > 5:
        return jsonify({'success': False, 'error': 'Name and rating required.'}), 400
    review = ProductReview(
        product_id=product.id,
        reviewer_name=name,
        reviewer_email=email,
        rating=rating,
        title=title,
        content=content,
        status='pending',
    )
    db.session.add(review)
    db.session.commit()
    return jsonify({'success': True,
                    'message': 'Thanks! Your review is pending approval.'})


@store_bp.route('/api/quick-view/<product_id>')
def quick_view(product_id):
    """Return minimal product data for the quick-view modal."""
    p = Product.query.filter_by(id=product_id, status='active').first_or_404()
    return jsonify({
        'id': p.id,
        'name': p.name,
        'slug': p.slug,
        'brand': p.brand or '',
        'description': p.description or '',
        'price': float(p.price),
        'compare_at_price': float(p.compare_at_price) if p.compare_at_price else None,
        'image': p.primary_image,
        'images': p.all_images[:5],
        'sizes': p.sizes,
        'colors': p.colors,
        'in_stock': p.in_stock,
        'url': url_for('store.product_detail', slug=p.slug),
    })


@store_bp.route('/api/notify-stock', methods=['POST'])
def notify_stock():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    variant_id = data.get('variant_id')
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()
    if not product_id or (not phone and not email):
        return jsonify({'success': False, 'error': 'Phone or email required.'}), 400
    existing = StockNotification.query.filter_by(
        product_id=product_id, variant_id=variant_id,
        phone=phone or None, email=email or None,
        notified_at=None,
    ).first()
    if existing:
        return jsonify({'success': True, 'message': 'Already on the list.'})
    db.session.add(StockNotification(
        product_id=product_id, variant_id=variant_id,
        phone=phone or None, email=email or None,
    ))
    db.session.commit()
    return jsonify({'success': True,
                    'message': 'We will notify you when it is back in stock.'})


@store_bp.route('/api/newsletter-signup', methods=['POST'])
def newsletter_signup():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Valid email required.'}), 400
    existing = NewsletterSignup.query.filter_by(email=email).first()
    if existing:
        return jsonify({'success': True, 'message': 'You\'re already subscribed.'})
    db.session.add(NewsletterSignup(email=email,
                                     source=data.get('source', 'footer')))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Subscribed — new drops coming.'})


@store_bp.route('/api/live-sales')
def live_sales():
    """Last few orders (anonymised) for the social-proof popup."""
    recent = Order.query.filter(Order.status != 'cancelled').order_by(
        Order.created_at.desc()).limit(10).all()
    out = []
    for o in recent:
        first_item = o.items.first()
        city = o.delivery_city or 'Ghana'
        name = (o.delivery_name or 'Someone').split()[0]
        out.append({
            'name': name,
            'city': city,
            'item': first_item.product_name if first_item else 'a sneaker',
            'minutes_ago': max(1, int((datetime.utcnow() - o.created_at)
                                       .total_seconds() / 60)),
        })
    return jsonify({'recent': out})


@store_bp.route('/robots.txt')
def robots_txt():
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /checkout',
        'Disallow: /cart',
        f'Sitemap: {request.host_url.rstrip("/")}/sitemap.xml',
    ]
    return Response('\n'.join(lines), mimetype='text/plain')


@store_bp.route('/sitemap.xml')
def sitemap_xml():
    urls = [request.host_url.rstrip('/') + url_for('store.home'),
            request.host_url.rstrip('/') + url_for('store.shop'),
            request.host_url.rstrip('/') + url_for('orders.track_order')]
    for p in Product.query.filter_by(status='active').all():
        urls.append(request.host_url.rstrip('/') +
                    url_for('store.product_detail', slug=p.slug))
    for pg in Page.query.filter_by(status='published').all():
        urls.append(request.host_url.rstrip('/') +
                    url_for('store.static_page', slug=pg.slug))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml.append(f'<url><loc>{u}</loc></url>')
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')


@store_bp.route('/manifest.webmanifest')
def webmanifest():
    return jsonify({
        'name': 'Slidein GH',
        'short_name': 'Slidein',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#000000',
        'description': 'Premium sneakers in Ghana.',
        'icons': [
            {'src': '/static/img/icon-192.png', 'sizes': '192x192',
             'type': 'image/png'},
            {'src': '/static/img/icon-512.png', 'sizes': '512x512',
             'type': 'image/png'},
        ],
    })


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