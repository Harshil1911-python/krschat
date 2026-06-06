"""
KHANDHARS CHAT - Utility Helpers
"""
import uuid
from datetime import datetime, timezone
from flask import current_app, request
from flask_mail import Message as MailMessage

from ..models import db, AuditLog


def utcnow():
    return datetime.now(timezone.utc)


def get_client_info():
    """Extract device/browser info from request."""
    ua_string = request.headers.get('User-Agent', '')
    info = {
        'device': 'Unknown',
        'device_type': 'desktop',
        'browser': 'Unknown',
        'os': 'Unknown',
    }
    try:
        from user_agents import parse
        ua = parse(ua_string)
        info['device'] = ua.device.family
        info['device_type'] = 'mobile' if ua.is_mobile else 'tablet' if ua.is_tablet else 'desktop'
        info['browser'] = f'{ua.browser.family} {ua.browser.version_string}'
        info['os'] = f'{ua.os.family} {ua.os.version_string}'
    except Exception:
        pass
    return info


def log_audit(action, actor_id=None, actor_type='user', target_type=None,
              target_id=None, details=None, ip=None):
    """Log an audit entry."""
    try:
        log = AuditLog(
            id=str(uuid.uuid4()),
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip or request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass


def send_email(to, subject, template, **kwargs):
    """Send an HTML email."""
    try:
        from .. import mail
        from flask import render_template
        html_body = render_template(f'{template}.html', **kwargs)
        msg = MailMessage(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            html=html_body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Email send error: {e}')
        return False


def sanitize_html(content, allowed_tags=None):
    """Sanitize HTML content to prevent XSS."""
    try:
        import bleach
        tags = allowed_tags or ['b', 'i', 'u', 'em', 'strong', 'a', 'br']
        attrs = {'a': ['href', 'title']}
        return bleach.clean(content, tags=tags, attributes=attrs)
    except Exception:
        return content


def format_file_size(size_bytes):
    """Format file size to human readable."""
    if size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.1f} KB'
    elif size_bytes < 1024 * 1024 * 1024:
        return f'{size_bytes / (1024*1024):.1f} MB'
    return f'{size_bytes / (1024*1024*1024):.1f} GB'
