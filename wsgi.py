import os
from app import create_app, db

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
