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
from app.models import NotificationLog, SiteSettings

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
        elif provider == 'mnotify':
            _send_via_mnotify(phone, message)
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


# ── Provider stubs (implement when you pick one) ──────────────────────────────

def _send_via_hubtel(phone, message):
    raise NotImplementedError('Hubtel integration not wired — set SMS_PROVIDER= to leave in log mode.')


def _send_via_mnotify(phone, message):
    raise NotImplementedError('mNotify integration not wired — set SMS_PROVIDER= to leave in log mode.')


def _send_via_smtp(to, subject, body):
    raise NotImplementedError('SMTP email integration not wired.')


# ── Telegram alerts ───────────────────────────────────────────────────────────

import threading


def _send_telegram(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return
    try:
        import requests as _req
        _req.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'},
            timeout=8,
        )
    except Exception:
        pass


def send_telegram(message):
    """Fire-and-forget Telegram message in a daemon thread."""
    threading.Thread(target=_send_telegram, args=(message,), daemon=True).start()


def telegram_new_order(order):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return
    msg = (
        f'🛒 <b>New Order — Slidein GH</b>\n'
        f'#{order.order_number} · GH₵{float(order.total):,.2f}\n'
        f'{order.delivery_name} · {order.delivery_city}\n'
        f'Payment: {order.payment_method}'
    )
    send_telegram(msg)


def telegram_low_stock(products):
    if not products:
        return
    lines = ['⚠️ <b>Low Stock — Slidein GH</b>']
    for p in products[:10]:
        lines.append(f'• {p.name}: {p.stock_quantity} left')
    send_telegram('\n'.join(lines))


def telegram_daily_report(report_text):
    send_telegram(f'📊 <b>Daily Report — Slidein GH</b>\n\n{report_text[:3500]}')
