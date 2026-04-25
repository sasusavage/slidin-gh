import hmac
import hashlib
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import NotificationLog

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')
log = logging.getLogger(__name__)

def verify_vynfy_signature(payload_bytes, signature, secret):
    """
    Verify the HMAC-SHA256 signature from Vynfy.
    """
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode(), 
        payload_bytes, 
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)

@webhooks_bp.route('/sms', methods=['POST'])
def vynfy_sms_webhook():
    import os
    secret = os.environ.get('VYNFY_WEBHOOK_SECRET')
    signature = request.headers.get('X-Webhook-Signature')
    
    payload_bytes = request.get_data()
    payload = request.get_json(silent=True) or {}
    
    # Only verify if a secret is configured in .env
    if secret:
        if not signature or not verify_vynfy_signature(payload_bytes, signature, secret):
            log.warning("Invalid Vynfy webhook signature. Rejecting request.")
            return jsonify({'error': 'Invalid signature'}), 401
    else:
        # Secret not set, we process without verification
        log.debug("Vynfy webhook received (verification skipped - no secret set).")

    event = payload.get('event')
    data = payload.get('data', {})
    message_id = data.get('message_id')
    
    if not message_id:
        return jsonify({'ok': True}), 200

    log.info(f"Vynfy Webhook: {event} for message {message_id}")

    # Map Vynfy events to our internal status
    status_map = {
        'sent': 'sent',
        'delivered': 'delivered',
        'failed': 'failed',
        'expired': 'expired'
    }
    
    new_status = status_map.get(event)
    if new_status:
        entry = NotificationLog.query.filter_by(provider_message_id=message_id).first()
        if entry:
            entry.status = new_status
            if event == 'failed':
                entry.error = data.get('error_message')
            db.session.commit()
            log.info(f"NotificationLog {entry.id} updated to {new_status}")

    return jsonify({'ok': True}), 200
