import os
import logging
import threading
from app import create_app, db

log = logging.getLogger(__name__)

app = create_app(os.environ.get('FLASK_ENV', 'production'))

# Auto-create tables on first boot if they don't exist
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"[wsgi] db.create_all() skipped: {e}")
        db.session.rollback()
    from app.models import SiteSettings
    try:
        SiteSettings.seed_defaults()
    except Exception:
        db.session.rollback()


def _register_telegram_webhook():
    """Auto-register Telegram webhook on startup if SITE_URL is set."""
    import time
    import random
    # Add jitter to avoid multiple workers hitting Telegram API at once
    time.sleep(random.uniform(1, 5))
    site_url = os.environ.get('SITE_URL', '').rstrip('/')
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not site_url or not token:
        log.info('[wsgi] Telegram webhook skipped — SITE_URL or TELEGRAM_BOT_TOKEN not set')
        return
    webhook_url = f'{site_url}/admin/telegram/webhook'
    try:
        import requests
        r = requests.post(
            f'https://api.telegram.org/bot{token}/setWebhook',
            json={'url': webhook_url, 'allowed_updates': ['message']},
            timeout=10,
        )
        data = r.json()
        if data.get('ok'):
            log.info(f'[wsgi] Telegram webhook registered: {webhook_url}')
            print(f'[wsgi] Telegram webhook registered: {webhook_url}')
        else:
            log.warning(f'[wsgi] Telegram webhook failed: {data.get("description", data)}')
            print(f'[wsgi] Telegram webhook failed: {data.get("description", data)}')
    except Exception as e:
        log.warning(f'[wsgi] Telegram webhook error: {e}')
        print(f'[wsgi] Telegram webhook error: {e}')


# Register webhook in a background thread so it doesn't block startup
threading.Thread(target=_register_telegram_webhook, daemon=True).start()
