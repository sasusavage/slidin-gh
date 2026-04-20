"""Groq AI business insights engine for Slidein GH admin."""
import json
from datetime import datetime, timedelta

_cache = {}
_CACHE_TTL = 600  # 10 minutes


def _build_context(app):
    from app import db
    from app.models import Order, OrderItem, Product, Customer, Expense, StockAdjustment
    from sqlalchemy import func

    now = datetime.utcnow()
    today = now.date()
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    def sales_agg(since):
        return db.session.query(
            func.count(Order.id).label('count'),
            func.coalesce(func.sum(Order.total), 0).label('revenue')
        ).filter(Order.created_at >= since,
                 Order.status != 'cancelled').first()

    t = db.session.query(
        func.count(Order.id),
        func.coalesce(func.sum(Order.total), 0)
    ).filter(func.date(Order.created_at) == today,
             Order.status != 'cancelled').first()

    w = sales_agg(d7)
    m = sales_agg(d30)

    top_products = db.session.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label('units'),
        func.sum(OrderItem.price * OrderItem.quantity).label('revenue')
    ).join(Order).filter(
        Order.created_at >= d30,
        Order.status != 'cancelled'
    ).group_by(OrderItem.product_name)\
     .order_by(func.sum(OrderItem.price * OrderItem.quantity).desc()).limit(5).all()

    low_stock = Product.query.filter(
        Product.status == 'active',
        Product.stock_quantity <= 5
    ).count()

    expenses_30 = db.session.query(func.sum(Expense.amount))\
        .filter(Expense.expense_date >= d30.date()).scalar() or 0

    adj_7 = StockAdjustment.query.filter(StockAdjustment.created_at >= d7).count()

    total_customers = Customer.query.count()

    return {
        'sales_today': {'count': int(t[0]), 'revenue': float(t[1])},
        'sales_7d': {'count': int(w.count), 'revenue': float(w.revenue)},
        'sales_30d': {'count': int(m.count), 'revenue': float(m.revenue)},
        'top_products': [{'name': p.product_name, 'units': int(p.units), 'revenue': float(p.revenue)} for p in top_products],
        'low_stock_count': low_stock,
        'expenses_30d': float(expenses_30),
        'stock_adjustments_7d': adj_7,
        'total_customers': total_customers,
    }


def get_context(app):
    import time
    now = time.time()
    if 'data' in _cache and now - _cache.get('ts', 0) < _CACHE_TTL:
        return _cache['data']
    with app.app_context():
        ctx = _build_context(app)
    _cache['data'] = ctx
    _cache['ts'] = now
    return ctx


def invalidate():
    _cache.clear()


def get_insights(app):
    import os
    ctx = get_context(app)
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return _fallback_insights(ctx)
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = (
            f"You are a business analyst AI for Slidein GH, a sneaker e-commerce store in Ghana.\n"
            f"Last 30 days: {ctx['sales_30d']['count']} orders, GH₵{ctx['sales_30d']['revenue']:,.2f} revenue.\n"
            f"Today: {ctx['sales_today']['count']} orders, GH₵{ctx['sales_today']['revenue']:,.2f}.\n"
            f"Expenses (30d): GH₵{ctx['expenses_30d']:,.2f}. Low stock products: {ctx['low_stock_count']}.\n"
            f"Top product: {ctx['top_products'][0]['name'] if ctx['top_products'] else 'N/A'}.\n\n"
            f"Respond ONLY with valid JSON:\n"
            f'{{"health_rating":"GREEN|AMBER|RED","health_summary":"one sentence","urgent_actions":["..."],"opportunities":["..."],"revenue_forecast_7d":1234.56}}'
        )
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3, max_tokens=400,
        )
        text = resp.choices[0].message.content.strip()
        start, end = text.find('{'), text.rfind('}') + 1
        data = json.loads(text[start:end])
        data['generated_at'] = datetime.utcnow().isoformat()
        return data
    except Exception:
        return _fallback_insights(ctx)


def _fallback_insights(ctx):
    rev = ctx['sales_30d']['revenue']
    rating = 'GREEN' if ctx['sales_30d']['count'] > 10 else ('AMBER' if ctx['sales_30d']['count'] > 2 else 'RED')
    actions = []
    if ctx['low_stock_count']:
        actions.append(f"Restock {ctx['low_stock_count']} low-stock product(s) urgently")
    if ctx['sales_today']['count'] == 0:
        actions.append("No sales today — check site and marketing channels")
    return {
        'health_rating': rating,
        'health_summary': f"GH₵{rev:,.2f} revenue in the last 30 days across {ctx['sales_30d']['count']} orders.",
        'urgent_actions': actions or ['Monitor stock levels and order pipeline'],
        'opportunities': ['Run a promotion on top-selling products', 'Follow up with customers who haven\'t ordered in 30+ days'],
        'revenue_forecast_7d': round(ctx['sales_7d']['revenue'], 2),
        'generated_at': datetime.utcnow().isoformat(),
    }


def chat(app, message):
    import os
    ctx = get_context(app)
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return 'AI is not configured. Add GROQ_API_KEY to your .env file.'
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        system = (
            f"You are a helpful business assistant for Slidein GH, a Ghana sneaker store. "
            f"30-day snapshot: revenue GH₵{ctx['sales_30d']['revenue']:,.2f}, "
            f"{ctx['sales_30d']['count']} orders, {ctx['low_stock_count']} low-stock items, "
            f"expenses GH₵{ctx['expenses_30d']:,.2f}. Be concise and practical."
        )
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': message}],
            temperature=0.5, max_tokens=600,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f'AI unavailable: {e}'


def get_health_report(app):
    import os
    ctx = get_context(app)
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return f"Slidein GH Report\nRevenue 30d: GH₵{ctx['sales_30d']['revenue']:,.2f}\nOrders: {ctx['sales_30d']['count']}"
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = (
            f"Write a short daily business report for Slidein GH (Ghana sneaker store).\n"
            f"Data: {json.dumps(ctx)}\n"
            f"Format: plain text with emoji. Max 250 words. Include: sales, top product, stock warnings, net position."
        )
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.4, max_tokens=400,
        )
        return resp.choices[0].message.content
    except Exception:
        return f"Slidein GH | Revenue 30d: GH₵{ctx['sales_30d']['revenue']:,.2f} | Orders: {ctx['sales_30d']['count']}"
