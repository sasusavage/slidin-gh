"""
Pluggable SMS + email sender. Also includes Telegram push notifications.

To wire up a real provider later:
  - set SMS_PROVIDER env var ("hubtel" or "mnotify")
  - set HUBTEL_* / MNOTIFY_* creds in env
  - implement _send_via_hubtel / _send_via_mnotify below

Until then, messages are recorded in the notification_logs table with
status='logged' so you can see exactly what would have been sent.
"""
import os
import logging
from app import db
from app.models import NotificationLog, SiteSettings, Customer
import requests

log = logging.getLogger(__name__)


def _normalize_ghana_phone(phone):
    """Normalize to international E.164 format for GH: +233XXXXXXXXX."""
    if not phone:
        return phone
    p = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
    if p.startswith('+'):
        return p
    if p.startswith('233'):
        return '+' + p
    if p.startswith('0') and len(p) == 10:
        return '+233' + p[1:]
    return p


def send_sms(phone, message, order_id=None):
    phone = _normalize_ghana_phone(phone)
    provider = os.environ.get('SMS_PROVIDER', '').lower()
    entry = NotificationLog(
        channel='sms', recipient=phone, message=message,
        order_id=order_id, provider=provider or 'stub', status='queued',
    )
    db.session.add(entry)
    try:
        if provider == 'hubtel':
            _send_via_hubtel(phone, message)
            entry.status = 'sent'
        elif provider == 'vynfy':
            result = _send_via_vynfy(phone, message)
            # Vynfy returns job_id in data
            if isinstance(result, dict) and 'data' in result:
                entry.provider_message_id = result['data'].get('job_id')
            entry.status = 'sent'
        else:
            log.info(f'[SMS stub] → {phone}: {message}')
            entry.status = 'logged'
    except Exception as e:
        entry.status = 'failed'
        entry.error = str(e)[:500]
        log.exception('SMS send failed')
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return entry


def send_email(to, subject, message, order_id=None):
    provider = os.environ.get('EMAIL_PROVIDER', '').lower()
    entry = NotificationLog(
        channel='email', recipient=to, subject=subject, message=message,
        order_id=order_id, provider=provider or 'stub', status='queued',
    )
    db.session.add(entry)
    try:
        if provider == 'smtp':
            _send_via_smtp(to, subject, message)
            entry.status = 'sent'
        else:
            log.info(f'[EMAIL stub] → {to}: {subject}\n{message}')
            entry.status = 'logged'
    except Exception as e:
        entry.status = 'failed'
        entry.error = str(e)[:500]
        log.exception('Email send failed')
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return entry


# ── High-level helpers ────────────────────────────────────────────────────────

def _site_name():
    try:
        return SiteSettings.get('site_name') or 'Slidein GH'
    except Exception:
        return 'Slidein GH'


def _site_url():
    return os.environ.get('SITE_URL', '').rstrip('/')


def bulk_send_sms(message, recipients=None):
    """
    Send SMS to all customers or a specific list.
    recipients: list of phone numbers. If None, sends to ALL customers.
    """
    from app import db
    if recipients is None:
        # Get all customers with valid phone numbers
        customers = Customer.query.filter(Customer.phone != None).all()
        recipients = [c.phone for c in customers]
    
    if not recipients:
        return 0
        
    for phone in recipients:
        send_sms(phone, message)
    return len(recipients)


def send_order_confirmation(order):
    """Called right after an order is placed."""
    name = _site_name()
    base = _site_url()
    track = f'{base}/order/track' if base else '/order/track'
    sms = (
        f'{name}: Order {order.order_number} confirmed. '
        f'Total GHS{order.total}. We will call to confirm delivery. '
        f'Track: {track}'
    )
    send_sms(order.delivery_phone, sms, order_id=order.id)
    if order.delivery_email:
        body = (
            f'Hi {order.delivery_name},\n\n'
            f'Thanks for shopping with {name}! Your order {order.order_number} is confirmed.\n\n'
            f'Subtotal: GHS{order.subtotal}\n'
            f'Delivery: GHS{order.delivery_fee}\n'
            f'Total: GHS{order.total}\n\n'
            f'Payment: Cash on delivery\n'
            f'Delivery to: {order.delivery_address}, {order.delivery_city}\n\n'
            f'Track your order anytime at {track}\n\n'
            f'— {name}'
        )
        send_email(order.delivery_email,
                   f'Order {order.order_number} confirmed — {name}',
                   body, order_id=order.id)


def send_status_update(order):
    """Called when admin changes an order's status."""
    name = _site_name()
    sms = f'{name}: Order {order.order_number} is now {order.status_label}.'
    send_sms(order.delivery_phone, sms, order_id=order.id)
    if order.delivery_email:
        send_email(order.delivery_email,
                   f'Order {order.order_number} — {order.status_label}',
                   f'Hi {order.delivery_name},\n\nYour order {order.order_number} '
                   f'is now {order.status_label}.\n\n— {name}',
                   order_id=order.id)


def schedule_sms(phone, message, schedule_time, order_id=None):
    """
    schedule_time: string "YYYY-MM-DD HH:MM"
    """
    phone = _normalize_ghana_phone(phone)
    provider = os.environ.get('SMS_PROVIDER', '').lower()
    entry = NotificationLog(
        channel='sms', recipient=phone, message=message,
        order_id=order_id, provider=provider or 'stub', status='scheduled',
    )
    db.session.add(entry)
    try:
        if provider == 'vynfy':
            result = _send_scheduled_vynfy(phone, message, schedule_time)
            if isinstance(result, dict) and 'data' in result:
                entry.provider_message_id = result['data'].get('job_id')
            entry.status = 'scheduled'
        else:
            log.info(f'[SMS Schedule stub] → {phone} at {schedule_time}: {message}')
            entry.status = 'logged'
    except Exception as e:
        entry.status = 'failed'
        entry.error = str(e)[:500]
        log.exception('SMS scheduling failed')
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return entry


def _send_via_vynfy(phone, message):
    key = os.environ.get('VYNFY_API_KEY')
    sender = os.environ.get('VYNFY_SENDER_ID', 'SlideinGH')[:11]
    if not key:
        raise ValueError('VYNFY_API_KEY not set')
    
    # Vynfy needs 233... without +
    clean_phone = phone.replace('+', '')
    if clean_phone.startswith('0'):
        clean_phone = '233' + clean_phone[1:]
    elif not clean_phone.startswith('233'):
        clean_phone = '233' + clean_phone

    url = "https://sms.vynfy.com/api/v1/send"
    headers = {
        "X-API-Key": key,
        "Content-Type": "application/json"
    }
    payload = {
        "message": message,
        "recipients": [clean_phone],
        "sender": sender
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    if not resp.ok:
        raise Exception(f'Vynfy error: {resp.text}')
    return resp.json()


def _send_scheduled_vynfy(phone, message, schedule_time):
    key = os.environ.get('VYNFY_API_KEY')
    sender = os.environ.get('VYNFY_SENDER_ID', 'SlideinGH')[:11]
    if not key:
        raise ValueError('VYNFY_API_KEY not set')
    
    clean_phone = phone.replace('+', '')
    if clean_phone.startswith('0'):
        clean_phone = '233' + clean_phone[1:]
    elif not clean_phone.startswith('233'):
        clean_phone = '233' + clean_phone

    url = "https://sms.vynfy.com/schedule/v1/send"
    headers = {
        "X-API-Key": key,
        "Content-Type": "application/json"
    }
    payload = {
        "message": message,
        "recipients": [clean_phone],
        "schedule_time": schedule_time,
        "sender": sender
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    if not resp.ok:
        raise Exception(f'Vynfy scheduling error: {resp.text}')
    return resp.json()


def _send_via_hubtel(phone, message):
    raise NotImplementedError('Hubtel integration not wired.')


def _send_via_mnotify(phone, message):
    raise NotImplementedError('mNotify integration not wired.')


def _send_via_smtp(to, subject, body):
    raise NotImplementedError('SMTP email integration not wired.')


# ── Telegram alerts ───────────────────────────────────────────────────────────

def send_chat_action(action='typing'):
    """Sends a chat action (typing, upload_photo, etc) to indicate the bot is working."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendChatAction',
            json={'chat_id': chat_id, 'action': action},
            timeout=5,
        )
    except Exception:
        pass

import threading


def _send_telegram(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        log.debug('Telegram not configured — skipping alert')
        return
    try:
        import requests as _req
        resp = _req.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'},
            timeout=10,
        )
        if not resp.ok:
            log.warning(f'Telegram API error: {resp.status_code} {resp.text[:200]}')
    except Exception as e:
        log.warning(f'Telegram send failed: {e}')


def send_telegram(message):
    """Fire-and-forget Telegram message in a daemon thread."""
    threading.Thread(target=_send_telegram, args=(message,), daemon=True).start()


def telegram_new_order(order):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return
    # Collect item names
    try:
        items = order.items.all()
        item_lines = '\n'.join(
            f'  • {i.product_name}'
            + (f' (Size {i.size})' if i.size else '')
            + f' × {i.quantity}'
            for i in items[:5]
        )
        if len(items) > 5:
            item_lines += f'\n  …and {len(items)-5} more'
    except Exception:
        item_lines = '  • (items unavailable)'

    site_url = os.environ.get('SITE_URL', '').rstrip('/')
    admin_link = f'{site_url}/admin/orders' if site_url else '/admin/orders'

    msg = (
        f'🛒 <b>New Order — Slidein GH</b>\n'
        f'────────────────\n'
        f'📋 <b>{order.order_number}</b>\n'
        f'👤 {order.delivery_name} · 📍 {order.delivery_city}\n'
        f'📦 Items:\n{item_lines}\n'
        f'💰 Total: <b>GH₵{float(order.total):,.2f}</b>\n'
        f'💳 Payment: {order.payment_method.replace("_", " ").title()}\n'
        f'🔗 <a href="{admin_link}">View in Admin</a>'
    )
    send_telegram(msg)


def telegram_order_status(order):
    """Alert when an order status changes to shipped or delivered."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return
    icons = {'shipped': '🚚', 'delivered': '✅', 'cancelled': '❌', 'processing': '⚙️'}
    icon = icons.get(order.status, '📦')
    msg = (
        f'{icon} <b>Order {order.status_label} — Slidein GH</b>\n'
        f'#{order.order_number} · {order.delivery_name} · GH₵{float(order.total):,.2f}\n'
        f'📍 {order.delivery_city}'
    )
    send_telegram(msg)


def telegram_low_stock(products):
    """products: list of Product objects with low stock_quantity, or dicts with name/qty."""
    if not products:
        return
    lines = ['⚠️ <b>Low Stock Alert — Slidein GH</b>', '────────────────']
    for p in products[:15]:
        if hasattr(p, 'name'):
            qty = p.stock_quantity if hasattr(p, 'stock_quantity') else p.total_stock
            lines.append(f'• {p.name}: <b>{qty}</b> left')
        else:
            lines.append(f'• {p}')
    if len(products) > 15:
        lines.append(f'…and {len(products)-15} more products')
    lines.append('\n🔗 Check <b>Admin → Inventory</b> to restock.')
    send_telegram('\n'.join(lines))


def telegram_low_stock_variants(variants):
    """variants: list of ProductVariant objects."""
    if not variants:
        return
    lines = ['⚠️ <b>Low Stock — Slidein GH</b>', '────────────────']
    for v in variants[:15]:
        label = v.product.name if v.product else 'Unknown'
        detail = []
        if v.size:
            detail.append(f'Size {v.size}')
        if v.color:
            detail.append(v.color)
        lines.append(f'• {label} ({", ".join(detail)}): <b>{v.quantity}</b> left')
    if len(variants) > 15:
        lines.append(f'…and {len(variants)-15} more variants')
    send_telegram('\n'.join(lines))


def telegram_daily_report(report_text):
    send_telegram(f'📊 <b>Daily Report — Slidein GH</b>\n\n{report_text[:3800]}')
