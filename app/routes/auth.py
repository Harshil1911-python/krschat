# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Authentication Routes
Secure login, registration, password reset, and session management
"""
from datetime import datetime, timezone, timedelta
import secrets
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt

from ..models import db, User, UserSession, AuditLog, SiteSettings
try:
    from .. import limiter
    HAS_LIMITER = limiter is not None
except Exception:
    limiter = None
    HAS_LIMITER = False
from ..utils.helpers import get_client_info, log_audit, send_email

auth_bp = Blueprint('auth', __name__)


def utcnow():
    return datetime.now(timezone.utc)


# ─── Register ─────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('chat.index'))

    if not SiteSettings.get('registration_open', True):
        flash('Registration is currently closed.', 'error')
        return render_template('auth/register.html')

    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form

        username = data.get('username', '').strip().lower()
        display_name = data.get('display_name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')

        errors = []

        # Validation
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not username.replace('_', '').replace('.', '').isalnum():
            errors.append('Username can only contain letters, numbers, underscores, and dots.')
        if not display_name or len(display_name) < 2:
            errors.append('Display name must be at least 2 characters.')
        if not phone and not email:
            errors.append('Phone number or email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if not errors:
            if User.query.filter_by(username=username).first():
                errors.append('Username already taken.')
            if phone and User.query.filter_by(phone=phone).first():
                errors.append('Phone number already registered.')
            if email and User.query.filter_by(email=email).first():
                errors.append('Email already registered.')

        if errors:
            if request.is_json:
                return jsonify({'success': False, 'errors': errors}), 400
            for e in errors:
                flash(e, 'error')
            return render_template('auth/register.html')

        # Create user
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            display_name=display_name,
            phone=phone or None,
            email=email or None,
            email_verify_token=secrets.token_urlsafe(32) if email else None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        log_audit('user_registered', actor_id=user.id, target_id=user.id, ip=request.remote_addr)

        if email:
            try:
                send_email(
                    to=email,
                    subject='Verify your email - Khandhars Chat',
                    template='emails/verify_email',
                    user=user,
                    token=user.email_verify_token
                )
            except Exception:
                pass

        login_user(user, remember=True)
        _create_session(user)

        if request.is_json:
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            return jsonify({
                'success': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user.to_dict(include_private=True)
            })

        flash('Welcome to Khandhars Chat!', 'success')
        return redirect(url_for('chat.index'))

    return render_template('auth/register.html')


# ─── Login ────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat.index'))

    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form

        identifier = data.get('identifier', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)

        if isinstance(remember, str):
            remember = remember.lower() in ('true', '1', 'on', 'yes')

        if not identifier or not password:
            msg = 'Phone/email and password are required.'
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'error')
            return render_template('auth/login.html')

        # Find user
        user = (User.query.filter_by(phone=identifier).first()
                or User.query.filter_by(email=identifier).first()
                or User.query.filter_by(username=identifier).first())

        if not user:
            log_audit('login_failed', details=f'identifier={identifier}', ip=request.remote_addr)
            msg = 'Invalid credentials.'
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 401
            flash(msg, 'error')
            return render_template('auth/login.html')

        # Check lockout
        if user.locked_until and user.locked_until > utcnow():
            remaining = int((user.locked_until - utcnow()).total_seconds() / 60)
            msg = f'Account locked. Try again in {remaining} minutes.'
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 429
            flash(msg, 'error')
            return render_template('auth/login.html')

        # Check ban
        if user.is_banned:
            msg = f'Account banned: {user.ban_reason or "Contact support."}'
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 403
            flash(msg, 'error')
            return render_template('auth/login.html')

        # Verify password
        if not user.check_password(password):
            user.login_attempts += 1
            max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
            if user.login_attempts >= max_attempts:
                user.locked_until = utcnow() + timedelta(seconds=current_app.config.get('LOCKOUT_DURATION', 900))
                user.login_attempts = 0
                msg = 'Too many failed attempts. Account locked for 15 minutes.'
            else:
                msg = f'Invalid credentials. {max_attempts - user.login_attempts} attempts remaining.'
            db.session.commit()
            log_audit('login_failed', actor_id=user.id, ip=request.remote_addr)
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 401
            flash(msg, 'error')
            return render_template('auth/login.html')

        # Successful login
        user.login_attempts = 0
        user.locked_until = None
        user.is_online = True
        user.last_seen = utcnow()
        db.session.commit()

        login_user(user, remember=remember)
        _create_session(user)
        log_audit('login_success', actor_id=user.id, ip=request.remote_addr)

        if request.is_json:
            jti = str(uuid.uuid4())
            access_token = create_access_token(identity=user.id, additional_claims={'jti': jti})
            refresh_token = create_refresh_token(identity=user.id)
            return jsonify({
                'success': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user.to_dict(include_private=True)
            })

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('chat.index'))

    return render_template('auth/login.html')


# ─── Logout ───────────────────────────────────────────────────────────────────

@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_seen = utcnow()
        db.session.commit()
        log_audit('logout', actor_id=current_user.id, ip=request.remote_addr)
    logout_user()
    if request.is_json:
        return jsonify({'success': True})
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing.index'))


# ─── Password Reset ───────────────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        identifier = data.get('identifier', '').strip()

        user = (User.query.filter_by(email=identifier).first()
                or User.query.filter_by(phone=identifier).first())

        # Always return success (don't leak whether user exists)
        msg = 'If an account with that identifier exists, a reset link has been sent.'

        if user and user.email:
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires = utcnow() + timedelta(hours=1)
            db.session.commit()
            try:
                send_email(
                    to=user.email,
                    subject='Reset your password - Khandhars Chat',
                    template='emails/reset_password',
                    user=user,
                    token=user.reset_token
                )
            except Exception:
                pass

        if request.is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < utcnow():
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        password = data.get('password', '')
        confirm = data.get('confirm_password', '')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('auth/reset_password.html', token=token)
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        log_audit('password_reset', actor_id=user.id, ip=request.remote_addr)
        flash('Password reset successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ─── Email Verification ───────────────────────────────────────────────────────

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(email_verify_token=token).first()
    if not user:
        flash('Invalid verification link.', 'error')
        return redirect(url_for('landing.index'))
    user.email_verified = True
    user.email_verify_token = None
    db.session.commit()
    flash('Email verified successfully!', 'success')
    return redirect(url_for('chat.index'))


# ─── API: Refresh Token ───────────────────────────────────────────────────────

@auth_bp.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({'access_token': access_token})


# ─── Profile ──────────────────────────────────────────────────────────────────

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form

        display_name = data.get('display_name', '').strip()
        bio = data.get('bio', '').strip()
        username = data.get('username', '').strip().lower()

        errors = []
        if display_name and len(display_name) < 2:
            errors.append('Display name too short.')
        if username and username != current_user.username:
            if User.query.filter_by(username=username).first():
                errors.append('Username taken.')
            elif len(username) < 3:
                errors.append('Username too short.')

        if errors:
            if request.is_json:
                return jsonify({'success': False, 'errors': errors}), 400
            for e in errors:
                flash(e, 'error')
            return render_template('auth/profile.html')

        if display_name:
            current_user.display_name = display_name
        if bio is not None:
            current_user.bio = bio[:500]
        if username and username != current_user.username:
            current_user.username = username

        # Theme
        theme = data.get('theme')
        if theme in ('dark', 'light'):
            current_user.theme = theme

        # Privacy
        current_user.show_last_seen = data.get('show_last_seen', 'true') in (True, 'true', '1', 'on')
        current_user.show_online_status = data.get('show_online_status', 'true') in (True, 'true', '1', 'on')
        current_user.show_read_receipts = data.get('show_read_receipts', 'true') in (True, 'true', '1', 'on')

        db.session.commit()
        log_audit('profile_updated', actor_id=current_user.id, ip=request.remote_addr)

        if request.is_json:
            return jsonify({'success': True, 'user': current_user.to_dict(include_private=True)})
        flash('Profile updated.', 'success')
        return render_template('auth/profile.html')

    return render_template('auth/profile.html')


# ─── Helper ───────────────────────────────────────────────────────────────────

def _create_session(user):
    """Create a user session record."""
    try:
        info = get_client_info()
        sess = UserSession(
            user_id=user.id,
            token_jti=secrets.token_urlsafe(32),
            device_name=info.get('device'),
            device_type=info.get('device_type'),
            browser=info.get('browser'),
            os=info.get('os'),
            ip_address=request.remote_addr,
        )
        db.session.add(sess)
        db.session.commit()
    except Exception:
        pass
