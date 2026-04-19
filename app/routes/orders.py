from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from app.models import Order, OrderItem, Customer, Product, ProductVariant
from app import db
from app.notifications import send_order_confirmation
from datetime import datetime
import random, string

orders_bp = Blueprint('orders', __name__)


def generate_order_number():
    prefix = 'SL'
    date_part = datetime.utcnow().strftime('%y%m%d')
    rand_part = ''.join(random.choices(string.digits, k=4))
    return f'{prefix}{date_part}{rand_part}'


@orders_bp.route('/checkout')
def checkout():
    cart_items = session.get('cart', [])
    if not cart_items:
        return redirect(url_for('store.shop'))
    subtotal = sum(i['price'] * i['quantity'] for i in cart_items)
    delivery_fee = 0 if subtotal >= 500 else 30
    total = subtotal + delivery_fee
    return render_template('checkout.html',
                           cart_items=cart_items,
                           subtotal=subtotal,
                           delivery_fee=delivery_fee,
                           total=total)


@orders_bp.route('/checkout/place', methods=['POST'])
def place_order():
    cart_items = session.get('cart', [])
    if not cart_items:
        return redirect(url_for('store.shop'))

    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    city = request.form.get('city', '').strip()
    region = request.form.get('region', '').strip()
    notes = request.form.get('notes', '').strip()

    if not full_name or not phone or not address or not city:
        cart_items = session.get('cart', [])
        subtotal = sum(i['price'] * i['quantity'] for i in cart_items)
        delivery_fee = 0 if subtotal >= 500 else 30
        return render_template('checkout.html',
                               cart_items=cart_items,
                               subtotal=subtotal,
                               delivery_fee=delivery_fee,
                               total=subtotal + delivery_fee,
                               error='Please fill in all required fields.',
                               form=request.form)

    # Find or create customer by phone
    customer = Customer.query.filter_by(phone=phone).first()
    if customer:
        customer.full_name = full_name
        customer.email = email or customer.email
        customer.address_line1 = address
        customer.city = city
        customer.region = region
    else:
        customer = Customer(
            full_name=full_name,
            phone=phone,
            email=email,
            address_line1=address,
            city=city,
            region=region,
        )
        db.session.add(customer)
        db.session.flush()

    subtotal = sum(i['price'] * i['quantity'] for i in cart_items)
    delivery_fee = 0 if subtotal >= 500 else 30
    total = subtotal + delivery_fee

    order = Order(
        order_number=generate_order_number(),
        customer_id=customer.id,
        delivery_name=full_name,
        delivery_phone=phone,
        delivery_email=email,
        delivery_address=address,
        delivery_city=city,
        delivery_region=region,
        delivery_notes=notes,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total,
        status='confirmed',
        payment_method='cash_on_delivery',
        payment_status='pending',
    )
    db.session.add(order)
    db.session.flush()

    for item in cart_items:
        # Deduct stock
        if item.get('variant_id'):
            variant = ProductVariant.query.get(item['variant_id'])
            if variant and variant.quantity >= item['quantity']:
                variant.quantity -= item['quantity']

        order_item = OrderItem(
            order_id=order.id,
            product_id=item['product_id'],
            variant_id=item.get('variant_id'),
            product_name=item['name'],
            product_image=item.get('image'),
            size=item.get('size'),
            color=item.get('color'),
            price=item['price'],
            quantity=item['quantity'],
        )
        db.session.add(order_item)

    db.session.commit()
    session.pop('cart', None)
    session.modified = True

    # Fire SMS + email confirmation (non-blocking: logs on failure, won't break checkout)
    try:
        send_order_confirmation(order)
    except Exception:
        pass

    return redirect(url_for('orders.order_success', order_number=order.order_number))


@orders_bp.route('/api/customer-lookup')
def customer_lookup():
    """Returning-customer auto-fill at checkout. Look up by phone."""
    phone = (request.args.get('phone') or '').strip()
    if not phone or len(phone) < 7:
        return jsonify({'found': False})
    customer = Customer.query.filter_by(phone=phone).first()
    if not customer:
        return jsonify({'found': False})
    return jsonify({
        'found': True,
        'full_name': customer.full_name,
        'email': customer.email or '',
        'address': customer.address_line1 or '',
        'city': customer.city or '',
        'region': customer.region or '',
    })


@orders_bp.route('/order/success/<order_number>')
def order_success(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('order_success.html', order=order)


@orders_bp.route('/order/track', methods=['GET', 'POST'])
def track_order():
    order = None
    error = None
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        order_number = request.form.get('order_number', '').strip()
        if phone or order_number:
            q = Order.query
            if order_number:
                q = q.filter_by(order_number=order_number)
            if phone:
                customer = Customer.query.filter_by(phone=phone).first()
                if customer:
                    q = q.filter_by(customer_id=customer.id)
                else:
                    error = 'No orders found for that phone number.'
                    q = None
            if q is not None:
                order = q.order_by(Order.created_at.desc()).first()
                if not order:
                    error = 'Order not found. Check your details and try again.'
        else:
            error = 'Please enter your phone number or order number.'
    return render_template('track_order.html', order=order, error=error)