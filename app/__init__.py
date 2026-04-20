import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name=None):
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config.get(config_name, config['default']))

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.store import store_bp
    from app.routes.orders import orders_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(store_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Start background scheduler (low-stock alerts + daily AI report)
    if not app.config.get('TESTING'):
        try:
            from app.scheduler import start_scheduler
            start_scheduler(app)
        except Exception:
            pass

    @app.template_filter('currency')
    def currency_filter(value):
        try:
            return f'GH₵{float(value):,.2f}'
        except (TypeError, ValueError):
            return 'GH₵0.00'

    @app.context_processor
    def inject_globals():
        from flask import session
        from app.models import SiteSettings, Banner
        cart = session.get('cart', [])
        cart_count = sum(item['quantity'] for item in cart)
        try:
            site = SiteSettings.get_all()
            banners = [b for b in Banner.query.filter_by(is_active=True)
                       .order_by(Banner.sort_order).all() if b.is_live]
        except Exception:
            site = SiteSettings.DEFAULTS.copy()
            banners = []
        return {'cart_count': cart_count, 'site': site, 'live_banners': banners}

    return app