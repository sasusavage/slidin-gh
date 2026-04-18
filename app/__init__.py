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

    @app.template_filter('currency')
    def currency_filter(value):
        try:
            return f'GH₵{float(value):,.2f}'
        except (TypeError, ValueError):
            return 'GH₵0.00'

    @app.context_processor
    def inject_cart():
        from flask import session
        cart = session.get('cart', [])
        cart_count = sum(item['quantity'] for item in cart)
        return {'cart_count': cart_count}

    return app