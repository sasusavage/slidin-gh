import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    # SQLAlchemy 2.x requires postgresql:// not postgres://
    _db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/slidin_store')
    SQLALCHEMY_DATABASE_URI = _db_url.replace('postgres://', 'postgresql://', 1) if _db_url.startswith('postgres://') else _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Always resolve to absolute path so it works both locally and in Docker
    _upload_rel = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    UPLOAD_FOLDER = _upload_rel if os.path.isabs(_upload_rel) else os.path.join(os.path.dirname(os.path.abspath(__file__)), _upload_rel)
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'avif'}

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}