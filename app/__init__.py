# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Application Factory
"""
import os
import logging
from flask import Flask, render_template, request, jsonify
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO

from .models import db, User, Admin

# Extensions
migrate = Migrate()
mail = Mail()
jwt = JWTManager()
login_manager = LoginManager()
socketio = SocketIO()

# Optional rate limiter
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
    HAS_LIMITER = True
except ImportError:
    limiter = None
    HAS_LIMITER = False


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # Load config
    from config import config
    app.config.from_object(config.get(config_name, config['default']))

    # Initialize extensions
    _init_extensions(app)

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register context processors
    _register_context_processors(app)

    # Security headers
    _configure_security(app)

    # Initialize database
    with app.app_context():
        db.create_all()
        _seed_defaults(app)

    return app


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    jwt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.login_message_category = 'info'

    if HAS_LIMITER and limiter:
        limiter.init_app(app)

    CORS(app, resources={
        r"/api/*": {"origins": "*"},
        r"/socket.io/*": {"origins": "*"}
    })

    async_mode = app.config.get('SOCKETIO_ASYNC_MODE', 'threading')
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode=async_mode,
        ping_timeout=app.config.get('SOCKETIO_PING_TIMEOUT', 60),
        ping_interval=app.config.get('SOCKETIO_PING_INTERVAL', 25),
        logger=False,
        engineio_logger=False,
    )

    # Optional Sentry
    sentry_dsn = app.config.get('SENTRY_DSN', '')
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(dsn=sentry_dsn, integrations=[FlaskIntegration()])
        except Exception:
            pass


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def _register_blueprints(app):
    from .routes.auth import auth_bp
    from .routes.chat import chat_bp
    from .routes.api import api_bp
    from .routes.admin import admin_bp
    from .routes.landing import landing_bp
    from .routes.sockets import register_socket_events

    app.register_blueprint(landing_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    register_socket_events(socketio)


def _register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Bad request'}), 400
        return render_template('errors/400.html'), 400

    @app.errorhandler(401)
    def unauthorized(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        return render_template('errors/401.html'), 401

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500


def _register_context_processors(app):
    from flask_login import current_user

    @app.context_processor
    def inject_globals():
        settings = {}
        try:
            from .models import SiteSettings, Announcement
            settings = {
                'app_name': SiteSettings.get('app_name', app.config.get('APP_NAME', 'Khandhars Chat')),
                'app_url': SiteSettings.get('app_url', app.config.get('APP_URL', '')),
                'support_email': SiteSettings.get('support_email', app.config.get('SUPPORT_EMAIL', '')),
                'support_phone': SiteSettings.get('support_phone', app.config.get('SUPPORT_PHONE', '')),
                'helpline_number': SiteSettings.get('helpline_number', app.config.get('HELPLINE_NUMBER', '')),
                'contact_gmail': SiteSettings.get('contact_gmail', ''),
                'primary_color': SiteSettings.get('primary_color', '#7C3AED'),
                'logo_url': SiteSettings.get('logo_url', ''),
                'favicon_url': SiteSettings.get('favicon_url', ''),
                'ga_tracking_id': SiteSettings.get('ga_tracking_id', ''),
                'footer_text': SiteSettings.get('footer_text', '(c) 2024 Khandhars Chat. All rights reserved.'),
                'announcement': None,
            }
            ann = Announcement.query.filter_by(is_active=True, type='banner').first()
            settings['announcement'] = ann
        except Exception:
            settings = {
                'app_name': 'Khandhars Chat',
                'primary_color': '#7C3AED',
                'announcement': None,
                'logo_url': '', 'favicon_url': '', 'ga_tracking_id': '',
                'support_email': '', 'support_phone': '', 'helpline_number': '',
                'contact_gmail': '', 'footer_text': '', 'app_url': '',
            }
        return dict(site=settings)

    @app.context_processor
    def inject_csrf():
        try:
            from flask_wtf.csrf import generate_csrf
            return dict(csrf_token=generate_csrf)
        except Exception:
            return dict(csrf_token=lambda: '')


def _configure_security(app):
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response


def _seed_defaults(app):
    """Seed default data on first run."""
    try:
        from .models import Admin, SiteSettings, CMSPage
        import uuid

        # Create default admin
        if Admin.query.count() == 0:
            admin = Admin(
                id=str(uuid.uuid4()),
                username=app.config.get('ADMIN_USERNAME', 'admin'),
                email=app.config.get('ADMIN_EMAIL', 'admin@khandharschat.com'),
                role='superadmin',
            )
            admin.set_password(app.config.get('ADMIN_PASSWORD', 'ChangeMe123!'))
            db.session.add(admin)

        # Seed default site settings
        defaults = [
            ('app_name', 'Khandhars Chat', 'string', 'general', 'Application Name'),
            ('app_url', app.config.get('APP_URL', ''), 'string', 'general', 'Application URL'),
            ('support_email', app.config.get('SUPPORT_EMAIL', 'support@khandharschat.com'), 'string', 'contact', 'Support Email'),
            ('support_phone', app.config.get('SUPPORT_PHONE', ''), 'string', 'contact', 'Support Phone'),
            ('helpline_number', app.config.get('HELPLINE_NUMBER', ''), 'string', 'contact', 'Helpline Number'),
            ('contact_gmail', '', 'string', 'contact', 'Contact Gmail'),
            ('contact_address', '', 'string', 'contact', 'Office Address'),
            ('contact_whatsapp', '', 'string', 'contact', 'WhatsApp Number'),
            ('primary_color', '#7C3AED', 'string', 'theme', 'Primary Color'),
            ('secondary_color', '#5B21B6', 'string', 'theme', 'Secondary Color'),
            ('logo_url', '', 'string', 'branding', 'Logo URL'),
            ('favicon_url', '', 'string', 'branding', 'Favicon URL'),
            ('hero_title', 'Connect Without Limits', 'string', 'landing', 'Hero Title'),
            ('hero_subtitle', 'Secure, fast, and beautiful messaging for everyone.', 'string', 'landing', 'Hero Subtitle'),
            ('features_title', 'Everything You Need', 'string', 'landing', 'Features Title'),
            ('footer_text', '(c) 2024 Khandhars Chat. All rights reserved.', 'string', 'footer', 'Footer Text'),
            ('facebook_url', '', 'string', 'social', 'Facebook URL'),
            ('twitter_url', '', 'string', 'social', 'Twitter URL'),
            ('instagram_url', '', 'string', 'social', 'Instagram URL'),
            ('ga_tracking_id', '', 'string', 'analytics', 'Google Analytics ID'),
            ('maintenance_mode', 'false', 'bool', 'general', 'Maintenance Mode'),
            ('registration_open', 'true', 'bool', 'general', 'Allow New Registrations'),
            ('smtp_server', app.config.get('MAIL_SERVER', ''), 'string', 'smtp', 'SMTP Server'),
            ('smtp_port', str(app.config.get('MAIL_PORT', 587)), 'int', 'smtp', 'SMTP Port'),
            ('smtp_username', app.config.get('MAIL_USERNAME', ''), 'string', 'smtp', 'SMTP Username'),

            # Chat customizations
            ('max_message_length', '5000', 'int', 'chat', 'Max Message Length (chars)'),
            ('max_file_size_mb', '50', 'int', 'chat', 'Max File Upload Size (MB)'),
            ('max_group_members', '256', 'int', 'chat', 'Max Group Members'),
            ('enable_voice_calls', 'true', 'bool', 'chat', 'Enable Voice Calls'),
            ('enable_video_calls', 'true', 'bool', 'chat', 'Enable Video Calls'),
            ('enable_voice_notes', 'true', 'bool', 'chat', 'Enable Voice Notes'),
            ('enable_file_sharing', 'true', 'bool', 'chat', 'Enable File Sharing'),
            ('enable_message_reactions', 'true', 'bool', 'chat', 'Enable Message Reactions'),
            ('enable_message_editing', 'true', 'bool', 'chat', 'Enable Message Editing'),
            ('enable_message_deletion', 'true', 'bool', 'chat', 'Enable Message Deletion'),
            ('enable_read_receipts', 'true', 'bool', 'chat', 'Enable Read Receipts Globally'),
            ('enable_typing_indicators', 'true', 'bool', 'chat', 'Enable Typing Indicators'),
            ('message_retention_days', '0', 'int', 'chat', 'Message Retention (0 = forever)'),
            ('default_chat_wallpaper', '', 'string', 'chat', 'Default Chat Wallpaper URL'),

            # User defaults
            ('default_theme', 'light', 'string', 'users', 'Default Theme for New Users'),
            ('default_font_size', 'medium', 'string', 'users', 'Default Font Size'),
            ('default_enter_to_send', 'true', 'bool', 'users', 'Default Enter-to-Send'),
            ('require_email_verification', 'false', 'bool', 'users', 'Require Email Verification'),
            ('allow_username_change', 'true', 'bool', 'users', 'Allow Username Changes'),
            ('allow_avatar_upload', 'true', 'bool', 'users', 'Allow Avatar Uploads'),
            ('min_username_length', '3', 'int', 'users', 'Minimum Username Length'),
            ('min_password_length', '8', 'int', 'users', 'Minimum Password Length'),

            # Branding extras
            ('app_description', 'Secure, fast messaging platform.', 'string', 'branding', 'App Description'),
            ('app_tagline', 'Connect Without Limits', 'string', 'branding', 'App Tagline'),
            ('login_background_url', '', 'string', 'branding', 'Login Page Background URL'),
        ]

        for key, value, vtype, category, label in defaults:
            if not SiteSettings.query.filter_by(key=key).first():
                s = SiteSettings(
                    key=key, value=str(value),
                    value_type=vtype, category=category, label=label
                )
                db.session.add(s)

        # Seed default CMS pages
        pages = [
            ('Home', 'home', True),
            ('About', 'about', True),
            ('Privacy Policy', 'privacy-policy', True),
            ('Terms of Service', 'terms-of-service', True),
            ('Contact', 'contact', True),
        ]
        for title, slug, is_system in pages:
            if not CMSPage.query.filter_by(slug=slug).first():
                p = CMSPage(
                    id=str(uuid.uuid4()),
                    title=title, slug=slug,
                    is_system=is_system,
                    content='<h1>{}</h1><p>Content coming soon.</p>'.format(title)
                )
                db.session.add(p)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        logging.warning('Seed warning (normal on first run): {}'.format(str(e)))
