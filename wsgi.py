import os
from app import create_app, db

app = create_app(os.environ.get('FLASK_ENV', 'production'))

# Auto-create tables on first boot if they don't exist
with app.app_context():
    db.create_all()
    from app.models import SiteSettings
    SiteSettings.seed_defaults()
