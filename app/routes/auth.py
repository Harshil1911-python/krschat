# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Authentication Routes
Fast, WhatsApp-style auth with persistent login via device fingerprint
"""
from datetime import datetime, timezone, timedelta
import secrets, uuid, json
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, make_response, current_app)
from flask_login import login_user, logout_user, login_required, current_user

from ..models import db, User, UserSession, AuditLog, SiteSettings
from ..utils.helpers import log_audit, send_email

auth_bp = Blueprint('auth', __name__)

def utcnow():
    return datetime.now(timezone.utc)

REMEMBER_DAYS = 90  # Stay logged in for 90 days

# ─── Register ─────────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('chat.index'))

    if not SiteSettings.get('registration_open', True):
        if request.is_json:
            return jsonify({'success': False, 'error': 'Registration is currently closed.'}), 403
        flash('Registration is currently closed.', 'error')
        return render_template('auth/register.html')

    if request.method == 'POST':
        # Accept both JSON and form
        data = request.get_json(silent=True) or request.form

        username     = (data.get('username') or '').strip().lower()
        display_name = (data.get('display_name') or '').strip()
        phone        = (data.get('phone') or '').strip()
        email        = (data.get('email') or '').strip().lower()
        password     = (data.get('password') or '')
        confirm      = (data.get('confirm_password') or '')
        device_id    = (data.get('device_id') or request.cookies.get('kc_device') or '')

        errors = []

        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not display_name or len(display_name) < 2:
            errors.append('Display name must be at least 2 characters.')
        if not phone and not email:
            errors.append('Phone number or email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
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

        # Create user — fast path, no blocking operations
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            display_name=display_name,
            phone=phone or None,
            email=email or None,
            email_verify_token=secrets.token_urlsafe(24) if email else None,
        )
        user.set_password(password)
        if device_id:
            user.device_fingerprints = json.dumps([device_id])
        db.session.add(user)
        db.session.commit()

        # Log in immediately
        login_user(user, remember=True, duration=timedelta(days=REMEMBER_DAYS))
        _set_device_cookie_and_session(user, device_id)

        # Send verification email async-style (don't block response)
        if email:
            try:
                send_email(to=email, subject='Verify your email',
                           template='emails/verify_email', user=user,
                           token=user.email_verify_token)
            except Exception:
                pass

        if request.is_json:
            from flask_jwt_extended import create_access_token
            return jsonify({
                'success': True,
                'redirect': url_for('chat.index'),
                'access_token': create_access_token(identity=user.id),
                'user': user.to_dict(include_private=True)
            })

        return redirect(url_for('chat.index'))

    return render_template('auth/register.html')


# ─── Login ────────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat.index'))

    # Check device fingerprint for instant login
    device_id = request.cookies.get('kc_device', '')
    if device_id:
        user = _find_user_by_device(device_id)
        if user and not user.is_banned:
            login_user(user, remember=True, duration=timedelta(days=REMEMBER_DAYS))
            user.is_online = True
            user.last_seen = utcnow()
            db.session.commit()
            return redirect(url_for('chat.index'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form

        identifier = (data.get('identifier') or '').strip()
        password   = (data.get('password') or '')
        remember   = data.get('remember', True)
        device_id  = (data.get('device_id') or request.cookies.get('kc_device') or '')

        if isinstance(remember, str):
            remember = remember.lower() not in ('false', '0', 'no')

        if not identifier or not password:
            msg = 'Credentials required.'
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'error')
            return render_template('auth/login.html')

        user = (User.query.filter_by(phone=identifier).first()
                or User.query.filter_by(email=identifier).first()
                or User.query.filter_by(username=identifier).first())

        if not user:
            msg = 'Invalid credentials.'
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 401
            flash(msg, 'error')
            return render_template('auth/login.html')

        if user.is_banned:
            msg = 'Account banned: {}'.format(user.ban_reason or 'Contact support.')
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 403
            flash(msg, 'error')
            return render_template('auth/login.html')

        # Lockout check
        if user.locked_until and user.locked_until > utcnow():
            remaining = int((user.locked_until - utcnow()).total_seconds() / 60)
            msg = 'Account locked. Try again in {} min.'.format(remaining)
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 429
            flash(msg, 'error')
            return render_template('auth/login.html')

        if not user.check_password(password):
            user.login_attempts = (user.login_attempts or 0) + 1
            max_att = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
            if user.login_attempts >= max_att:
                user.locked_until = utcnow() + timedelta(seconds=current_app.config.get('LOCKOUT_DURATION', 900))
                user.login_attempts = 0
                msg = 'Too many attempts. Account locked 15 min.'
            else:
                msg = 'Invalid credentials. {} attempts left.'.format(max_att - user.login_attempts)
            db.session.commit()
            if request.is_json:
                return jsonify({'success': False, 'error': msg}), 401
            flash(msg, 'error')
            return render_template('auth/login.html')

        # Success
        user.login_attempts = 0
        user.locked_until = None
        user.is_online = True
        user.last_seen = utcnow()
        db.session.commit()

        login_user(user, remember=True, duration=timedelta(days=REMEMBER_DAYS))
        resp = _set_device_cookie_and_session(user, device_id, make_resp=True)

        if request.is_json:
            from flask_jwt_extended import create_access_token
            data_out = {
                'success': True,
                'redirect': url_for('chat.index'),
                'access_token': create_access_token(identity=user.id),
                'user': user.to_dict(include_private=True)
            }
            resp = make_response(jsonify(data_out))
            _attach_device_cookie(resp, user, device_id)
            return resp

        next_page = request.args.get('next', '')
        target = next_page if next_page and next_page.startswith('/') else url_for('chat.index')
        r = make_response(redirect(target))
        _attach_device_cookie(r, user, device_id)
        return r

    return render_template('auth/login.html')


# ─── Logout ───────────────────────────────────────────────────────────────────
@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_seen = utcnow()
        db.session.commit()
    logout_user()
    resp = make_response(redirect(url_for('landing.index')))
    # Clear device cookie on logout
    resp.delete_cookie('kc_device')
    flash('Signed out successfully.', 'info')
    return resp


# ─── Forgot / Reset Password ──────────────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        identifier = (data.get('identifier') or '').strip()
        user = (User.query.filter_by(email=identifier).first()
                or User.query.filter_by(phone=identifier).first())
        if user and user.email:
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires = utcnow() + timedelta(hours=1)
            db.session.commit()
            try:
                send_email(to=user.email, subject='Reset your password',
                           template='emails/reset_password', user=user, token=user.reset_token)
            except Exception:
                pass
        msg = 'If that account exists, a reset link was sent.'
        if request.is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < utcnow():
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        pw = data.get('password', '')
        if len(pw) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('auth/reset_password.html', token=token)
        user.set_password(pw)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Password reset. Please sign in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(email_verify_token=token).first()
    if not user:
        flash('Invalid verification link.', 'error')
        return redirect(url_for('landing.index'))
    user.email_verified = True
    user.email_verify_token = None
    db.session.commit()
    flash('Email verified!', 'success')
    return redirect(url_for('chat.index'))


# ─── Profile ──────────────────────────────────────────────────────────────────
@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form

        display_name   = (data.get('display_name') or '').strip()
        bio            = (data.get('bio') or '').strip()
        username       = (data.get('username') or '').strip().lower()
        theme          = data.get('theme', '')
        notification_sound = data.get('notification_sound', '')
        chat_wallpaper = data.get('chat_wallpaper', '')
        font_size      = data.get('font_size', '')
        message_preview = data.get('message_preview', '')
        enter_to_send  = data.get('enter_to_send', '')

        errors = []
        if display_name and len(display_name) < 2:
            errors.append('Display name too short.')
        if username and username != current_user.username:
            if len(username) < 3:
                errors.append('Username too short.')
            elif User.query.filter_by(username=username).first():
                errors.append('Username taken.')

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
        if theme in ('dark', 'light'):
            current_user.theme = theme

        # Extended preferences stored as JSON
        prefs = current_user.get_preferences()
        if notification_sound:
            prefs['notification_sound'] = notification_sound
        if chat_wallpaper is not None:
            prefs['chat_wallpaper'] = chat_wallpaper
        if font_size in ('small', 'medium', 'large'):
            prefs['font_size'] = font_size
        if message_preview in ('true', 'false', True, False):
            prefs['message_preview'] = str(message_preview) in ('true', 'True')
        if enter_to_send in ('true', 'false', True, False):
            prefs['enter_to_send'] = str(enter_to_send) in ('true', 'True')

        # Privacy
        for key in ('show_last_seen', 'show_online_status', 'show_read_receipts'):
            val = data.get(key)
            if val is not None:
                setattr(current_user, key, str(val) in ('true', 'True', '1', 'on'))

        current_user.set_preferences(prefs)
        db.session.commit()

        if request.is_json:
            return jsonify({'success': True, 'user': current_user.to_dict(include_private=True)})
        flash('Profile updated.', 'success')

    return render_template('auth/profile.html')


# ─── Change Password ──────────────────────────────────────────────────────────
@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json(silent=True) or request.form
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    confirm = data.get('confirm_password', '')

    if not current_user.check_password(current_pw):
        if request.is_json:
            return jsonify({'success': False, 'error': 'Current password incorrect'}), 400
        flash('Current password incorrect.', 'error')
        return redirect(url_for('auth.profile'))

    if len(new_pw) < 8:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Password too short'}), 400
        flash('New password too short.', 'error')
        return redirect(url_for('auth.profile'))

    if new_pw != confirm:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400
        flash('Passwords do not match.', 'error')
        return redirect(url_for('auth.profile'))

    current_user.set_password(new_pw)
    db.session.commit()

    if request.is_json:
        return jsonify({'success': True})
    flash('Password changed successfully.', 'success')
    return redirect(url_for('auth.profile'))


# ─── Device Sessions ──────────────────────────────────────────────────────────
@auth_bp.route('/sessions', methods=['GET'])
@login_required
def sessions():
    user_sessions = current_user.sessions.order_by(UserSession.last_active.desc()).limit(10).all()
    if request.is_json:
        return jsonify({'sessions': [{'id': s.id, 'device': s.device_name,
                                       'browser': s.browser, 'os': s.os,
                                       'ip': s.ip_address, 'last_active': s.last_active.isoformat() if s.last_active else None,
                                       'is_active': s.is_active} for s in user_sessions]})
    return render_template('auth/profile.html', user_sessions=user_sessions)


@auth_bp.route('/sessions/<session_id>/revoke', methods=['POST'])
@login_required
def revoke_session(session_id):
    sess = UserSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if sess:
        sess.is_active = False
        db.session.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash('Session revoked.', 'success')
    return redirect(url_for('auth.profile'))


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _find_user_by_device(device_id):
    """Find user by stored device fingerprint."""
    try:
        users = User.query.filter(
            User.device_fingerprints.isnot(None),
            User.device_fingerprints != '[]'
        ).all()
        for u in users:
            fps = u.get_device_fingerprints()
            if device_id in fps:
                return u
    except Exception:
        pass
    return None


def _set_device_cookie_and_session(user, device_id, make_resp=False):
    """Store device fingerprint and create session record."""
    if not device_id:
        device_id = secrets.token_urlsafe(24)

    # Store fingerprint on user
    fps = user.get_device_fingerprints()
    if device_id not in fps:
        fps.append(device_id)
        if len(fps) > 10:
            fps = fps[-10:]
        user.device_fingerprints = json.dumps(fps)
        db.session.commit()

    # Create session record
    try:
        from ..utils.helpers import get_client_info
        info = get_client_info()
        sess = UserSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_jti=secrets.token_urlsafe(24),
            device_name=info.get('device', 'Unknown'),
            device_type=info.get('device_type', 'desktop'),
            browser=info.get('browser', ''),
            os=info.get('os', ''),
            ip_address=request.remote_addr,
            is_active=True,
            last_active=utcnow(),
        )
        db.session.add(sess)
        db.session.commit()
    except Exception:
        pass

    return device_id


def _attach_device_cookie(response, user, device_id):
    """Attach a persistent device cookie to the response."""
    if not device_id:
        device_id = secrets.token_urlsafe(24)
    response.set_cookie(
        'kc_device', device_id,
        max_age=60 * 60 * 24 * 90,  # 90 days
        httponly=True,
        samesite='Lax',
        secure=not current_app.debug,
    )
