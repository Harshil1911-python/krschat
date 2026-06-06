# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Application Configuration
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Core
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    APP_NAME = os.environ.get('APP_NAME', 'Khandhars Chat')
    APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')

    # Database - supports both PostgreSQL and SQLite
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///khandhars_dev.db')
    # Fix Render's postgres:// -> postgresql://
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Redis (optional)
    REDIS_URL = os.environ.get('REDIS_URL', '')

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', '1') == '1'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get(
        'MAIL_DEFAULT_SENDER', 'noreply@khandharschat.com'
    )

    # File Upload
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    # Cloudinary (optional)
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

    # Security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', 5))
    LOCKOUT_DURATION = int(os.environ.get('LOCKOUT_DURATION', 900))

    # Rate Limiting - use memory if no Redis
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')

    # SocketIO
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_PING_TIMEOUT = 60
    SOCKETIO_PING_INTERVAL = 25

    # Sentry
    SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

    # Analytics
    GA_TRACKING_ID = os.environ.get('GA_TRACKING_ID', '')

    # Contact
    SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'support@khandharschat.com')
    SUPPORT_PHONE = os.environ.get('SUPPORT_PHONE', '')
    HELPLINE_NUMBER = os.environ.get('HELPLINE_NUMBER', '')

    # Admin
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@khandharschat.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ChangeMe123!')
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')

    # Push Notifications
    FCM_SERVER_KEY = os.environ.get('FCM_SERVER_KEY', '')

    # Encryption
    E2EE_MASTER_KEY = os.environ.get('E2EE_MASTER_KEY', SECRET_KEY)


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False  # Easier for dev
    SOCKETIO_ASYNC_MODE = 'threading'


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = 'https'
    WTF_CSRF_ENABLED = True
    SOCKETIO_ASYNC_MODE = 'threading'


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
