"""Groq AI business insights engine for Slidein GH admin."""
import json
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

_cache = {}
_CACHE_TTL = 600  # 10 minutes


def _get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "send_sms_message",
                "description": "Send an SMS message to one or more customers. Use this to send receipts, confirmations, or marketing messages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "The text of the SMS message."},
                        "recipients": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of phone numbers. If empty/null, it will send to ALL customers (bulk)."
                        }
                    },
                    "required": ["message"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_coupon",
                "description": "Generate a new discount coupon code in the system.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "The coupon code (e.g. SLIDE10)."},
                        "discount_type": {"type": "string", "enum": ["percentage", "fixed"], "description": "Type of discount."},
                        "discount_value": {"type": "number", "description": "The value of the discount (e.g. 10 for 10% or 50 for GH₵50)."},
                        "min_spend": {"type": "number", "description": "Minimum spend required to use the coupon."},
                        "expiry_days": {"type": "integer", "description": "Number of days from now until the coupon expires."}
                    },
                    "required": ["code", "discount_type", "discount_value"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_customer_info",
                "description": "Search for customer details by name or phone number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Name or phone number to search for."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_detailed_inventory",
                "description": "Check stock levels for specific products or all low-stock items including sizes and colors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string", "description": "Optional product name to filter by."}
                    }
                }
            }
        }
    ]


def _execute_tool(app, func_name, args):
    from app import db
    from app.models import Customer, Product, ProductVariant, CouponCode
    from app.notifications import send_sms, bulk_send_sms
    
    try:
        if func_name == "send_sms_message":
            msg = args.get("message")
            recs = args.get("recipients")
            if not recs:
                count = bulk_send_sms(msg)
                return f"Bulk SMS sent to {count} customers."
            else:
                for r in recs:
                    send_sms(r, msg)
                return f"SMS sent to {len(recs)} recipients."
                
        elif func_name == "create_coupon":
            code = args.get("code").upper()
            dtype = args.get("discount_type")
            val = args.get("discount_value")
            min_s = args.get("min_spend", 0)
            exp = args.get("expiry_days", 30)
            
            existing = CouponCode.query.filter_by(code=code).first()
            if existing:
                return f"Coupon {code} already exists."
                
            c = CouponCode(
                code=code,
                discount_type=dtype,
                discount_value=val,
                min_order_amount=min_s,
                end_date=datetime.utcnow() + timedelta(days=exp),
                is_active=True
            )
            db.session.add(c)
            db.session.commit()
            return f"Coupon {code} ({val} {dtype}) created successfully, expires in {exp} days."
            
        elif func_name == "get_customer_info":
            q = args.get("query")
            from sqlalchemy import or_
            custs = Customer.query.filter(or_(
                Customer.name.ilike(f"%{q}%"),
                Customer.phone.ilike(f"%{q}%")
            )).limit(5).all()
            if not custs:
                return "No customers found matching that query."
            res = []
            for c in custs:
                res.append(f"Name: {c.name}, Phone: {c.phone}, Orders: {c.order_count}, Total Spent: GH₵{float(c.total_spent):,.2f}")
            return "\n".join(res)
            
        elif func_name == "check_detailed_inventory":
            pname = args.get("product_name")
            query = ProductVariant.query.join(Product)
            if pname:
                query = query.filter(Product.name.ilike(f"%{pname}%"))
            else:
                query = query.filter(ProductVariant.quantity <= 5)
            
            variants = query.limit(20).all()
            if not variants:
                return "No matching inventory issues found."
            lines = []
            for v in variants:
                lines.append(f"{v.product.name} ({v.size or 'N/A'}/{v.color or 'N/A'}): {v.quantity} in stock")
            return "\n".join(lines)
            
    except Exception as e:
        log.error(f"Tool execution error ({func_name}): {e}")
        return f"Error executing tool: {str(e)}"
    
    return "Unknown tool"


def _build_context(app):
    from app import db
    from app.models import Order, OrderItem, Product, ProductVariant, Customer, Expense, StockAdjustment
    from sqlalchemy import func

    now = datetime.utcnow()
    today = now.date()
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    def sales_agg(since):
        return db.session.query(
            func.count(Order.id).label('count'),
            func.coalesce(func.sum(Order.total), 0).label('revenue'),
            func.coalesce(func.avg(Order.total), 0).label('avg_order'),
        ).filter(Order.created_at >= since, Order.status != 'cancelled').first()

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

    # Low stock via variants (accurate) + product.stock_quantity (tracked)
    low_stock_variants = db.session.query(func.count(ProductVariant.id)).join(Product).filter(
        Product.status == 'active',
        ProductVariant.quantity > 0,
        ProductVariant.quantity <= 5,
    ).scalar() or 0

    out_of_stock = db.session.query(func.count(ProductVariant.id)).join(Product).filter(
        Product.status == 'active',
        ProductVariant.quantity == 0,
    ).scalar() or 0

    expenses_30 = db.session.query(func.sum(Expense.amount))\
        .filter(Expense.expense_date >= d30.date()).scalar() or 0

    adj_7 = StockAdjustment.query.filter(StockAdjustment.created_at >= d7).count()

    total_customers = Customer.query.count()
    repeat_customers = sum(1 for c in Customer.query.all() if c.order_count > 1)

    # Pending orders needing attention
    pending_count = Order.query.filter(Order.status.in_(['confirmed', 'processing'])).count()

    profit_estimate = float(m.revenue) - float(expenses_30)

    return {
        'sales_today': {'count': int(t[0]), 'revenue': float(t[1])},
        'sales_7d': {'count': int(w.count), 'revenue': float(w.revenue), 'avg_order': float(w.avg_order)},
        'sales_30d': {'count': int(m.count), 'revenue': float(m.revenue), 'avg_order': float(m.avg_order)},
        'top_products': [{'name': p.product_name, 'units': int(p.units), 'revenue': float(p.revenue)} for p in top_products],
        'low_stock_variants': int(low_stock_variants),
        'out_of_stock_variants': int(out_of_stock),
        'expenses_30d': float(expenses_30),
        'profit_estimate_30d': profit_estimate,
        'stock_adjustments_7d': adj_7,
        'total_customers': total_customers,
        'repeat_customers': repeat_customers,
        'pending_orders': pending_count,
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



def _groq_client():
    import os
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return None, None
    try:
        from groq import Groq
        return Groq(api_key=api_key), api_key
    except Exception:
        return None, None


def get_insights(app):
    ctx = get_context(app)
    client, _ = _groq_client()
    if not client:
        return _fallback_insights(ctx)
    try:
        profit_str = f"GH₵{ctx['profit_estimate_30d']:,.2f}" if ctx['profit_estimate_30d'] >= 0 else f"-GH₵{abs(ctx['profit_estimate_30d']):,.2f}"
        prompt = (
            f"You are a senior business analyst for Slidein GH, a premium sneaker e-commerce store in Ghana.\n\n"
            f"BUSINESS DATA (last 30 days):\n"
            f"- Revenue: GH₵{ctx['sales_30d']['revenue']:,.2f} from {ctx['sales_30d']['count']} orders\n"
            f"- Average order value: GH₵{ctx['sales_30d']['avg_order']:,.2f}\n"
            f"- Expenses: GH₵{ctx['expenses_30d']:,.2f} | Estimated profit: {profit_str}\n"
            f"- Today: {ctx['sales_today']['count']} orders, GH₵{ctx['sales_today']['revenue']:,.2f}\n"
            f"- Pending orders: {ctx['pending_orders']}\n"
            f"- Customers: {ctx['total_customers']} total, {ctx['repeat_customers']} repeat buyers\n"
            f"- Stock: {ctx['low_stock_variants']} low-stock variants, {ctx['out_of_stock_variants']} out of stock\n"
            f"- Top product: {ctx['top_products'][0]['name'] if ctx['top_products'] else 'N/A'}\n\n"
            f"Respond ONLY with valid JSON (no markdown, no explanation):\n"
            f'{{"health_rating":"GREEN|AMBER|RED","health_summary":"one sentence max 20 words",'
            f'"urgent_actions":["action1","action2"],"opportunities":["opp1","opp2"],'
            f'"revenue_forecast_7d":1234.56,"key_metric":"one standout metric worth highlighting"}}'
        )
        for attempt in range(2):
            try:
                resp = client.chat.completions.create(
                    model='llama-3.3-70b-versatile',
                    messages=[{'role': 'user', 'content': prompt}],
                    temperature=0.2,
                    max_tokens=500,
                )
                text = resp.choices[0].message.content.strip()
                start, end = text.find('{'), text.rfind('}') + 1
                if start == -1:
                    raise ValueError('No JSON in response')
                data = json.loads(text[start:end])
                data['context'] = ctx
                data['generated_at'] = datetime.utcnow().isoformat()
                return data
            except Exception as e:
                if attempt == 1:
                    raise e
    except Exception as e:
        log.warning(f'AI insights fallback: {e}')
    return _fallback_insights(ctx)


def _fallback_insights(ctx):
    rev = ctx['sales_30d']['revenue']
    cnt = ctx['sales_30d']['count']
    if cnt > 20:
        rating = 'GREEN'
    elif cnt > 5:
        rating = 'AMBER'
    else:
        rating = 'RED'

    actions = []
    if ctx['out_of_stock_variants']:
        actions.append(f"{ctx['out_of_stock_variants']} variant(s) are out of stock — create a purchase order")
    if ctx['low_stock_variants']:
        actions.append(f"{ctx['low_stock_variants']} variant(s) are running low (≤5 units)")
    if ctx['sales_today']['count'] == 0:
        actions.append("No sales today — check site is live and share on WhatsApp/Instagram")
    if ctx['pending_orders'] > 5:
        actions.append(f"{ctx['pending_orders']} orders pending — process them to avoid delays")

    profit = ctx['profit_estimate_30d']
    profit_str = f"GH₵{profit:,.2f}" if profit >= 0 else f"-GH₵{abs(profit):,.2f}"

    return {
        'health_rating': rating,
        'health_summary': f"GH₵{rev:,.2f} revenue from {cnt} orders in 30 days. Estimated profit: {profit_str}.",
        'urgent_actions': actions or ['All systems look good — keep monitoring stock levels'],
        'opportunities': [
            'Feature your top-selling product on Instagram Stories',
            'Offer a bundle deal or loyalty discount for repeat buyers',
            f"{ctx['repeat_customers']} repeat customers — consider a VIP WhatsApp group",
        ],
        'revenue_forecast_7d': round(ctx['sales_7d']['revenue'], 2),
        'key_metric': f"Avg order: GH₵{ctx['sales_30d']['avg_order']:,.2f}",
        'context': ctx,
        'generated_at': datetime.utcnow().isoformat(),
    }


def chat(app, message, history=None):
    """
    history: list of {'role': 'user'|'assistant', 'content': str}
    Returns the AI reply string.
    """
    ctx = get_context(app)
    client, _ = _groq_client()
    if not client:
        return 'AI is not configured. Add your GROQ_API_KEY to the .env file to enable this feature.'

    profit_str = f"GH₵{ctx['profit_estimate_30d']:,.2f}" if ctx['profit_estimate_30d'] >= 0 else f"-GH₵{abs(ctx['profit_estimate_30d']):,.2f}"
    system = (
        f"You are a practical business assistant for Slidein GH, a premium sneaker store in Ghana. "
        f"You have access to real-time business data:\n"
        f"- Last 30 days: GH₵{ctx['sales_30d']['revenue']:,.2f} revenue, {ctx['sales_30d']['count']} orders, avg GH₵{ctx['sales_30d']['avg_order']:,.2f}/order\n"
        f"- Today: {ctx['sales_today']['count']} orders, GH₵{ctx['sales_today']['revenue']:,.2f}\n"
        f"- Profit estimate (30d): {profit_str} (revenue minus expenses)\n"
        f"- Customers: {ctx['total_customers']} total, {ctx['repeat_customers']} repeat\n"
        f"- Stock issues: {ctx['low_stock_variants']} low, {ctx['out_of_stock_variants']} out of stock\n"
        f"- Pending orders: {ctx['pending_orders']}\n\n"
        f"Be concise, practical, and Ghana-market aware. Use GH₵ for currency. "
        f"Give specific, actionable advice. Keep replies under 200 words unless asked for detail."
    )

    messages = [{'role': 'system', 'content': system}]
    if history:
        messages.extend(history[-10:])  # last 5 exchanges
    messages.append({'role': 'user', 'content': message})

    tools = _get_tools()

    try:
        # First turn: model decides whether to call a tool
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.4,
            max_tokens=800,
        )
        
        msg_obj = resp.choices[0].message
        
        # Check if model wants to call tools
        if msg_obj.tool_calls:
            messages.append(msg_obj)
            
            for tool_call in msg_obj.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                log.info(f"AI Tool Call: {func_name}({func_args})")
                tool_result = _execute_tool(app, func_name, func_args)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": tool_result,
                })
            
            # Second turn: model responds with the tool results
            final_resp = client.chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=messages,
                temperature=0.4,
            )
            return final_resp.choices[0].message.content
        
        return msg_obj.content
    except Exception as e:
        log.exception(f'AI chat error: {e}')
        return f'AI is temporarily unavailable. Please try again in a moment.'


def get_health_report(app):
    ctx = get_context(app)
    client, _ = _groq_client()

    profit = ctx['profit_estimate_30d']
    profit_str = f"GH₵{profit:,.2f}" if profit >= 0 else f"−GH₵{abs(profit):,.2f} (loss)"

    if not client:
        lines = [
            "📊 Slidein GH — Daily Report",
            f"📦 Orders (30d): {ctx['sales_30d']['count']} | Today: {ctx['sales_today']['count']}",
            f"💰 Revenue (30d): GH₵{ctx['sales_30d']['revenue']:,.2f}",
            f"💸 Expenses (30d): GH₵{ctx['expenses_30d']:,.2f}",
            f"📈 Est. Profit: {profit_str}",
            f"👥 Customers: {ctx['total_customers']} ({ctx['repeat_customers']} repeat)",
            f"⚠️ Low stock variants: {ctx['low_stock_variants']} | Out of stock: {ctx['out_of_stock_variants']}",
        ]
        if ctx['top_products']:
            lines.append(f"🏆 Top product: {ctx['top_products'][0]['name']} ({ctx['top_products'][0]['units']} units)")
        return '\n'.join(lines)

    try:
        prompt = (
            f"Write a concise daily business report for Slidein GH (Ghana sneaker store) in a Telegram message style.\n"
            f"Data: {json.dumps(ctx)}\n"
            f"Rules: use emojis, plain text only, max 200 words. "
            f"Include: sales summary, profit/loss, stock warnings, top seller, one key action for today."
        )
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.4,
            max_tokens=400,
        )
        return resp.choices[0].message.content
    except Exception:
        return f"📊 Slidein GH | Revenue 30d: GH₵{ctx['sales_30d']['revenue']:,.2f} | Orders: {ctx['sales_30d']['count']} | Profit: {profit_str}"
