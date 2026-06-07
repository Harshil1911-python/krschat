# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Admin Panel Routes
Full-featured admin dashboard with CMS, user management, and settings
"""
import json
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session, current_app
from flask_login import current_user

from ..models import db, User, Admin, Chat, Message, Group, MediaFile, SiteSettings, CMSPage, Announcement, Advertisement, Analytics, AuditLog, UserReport
from ..utils.helpers import log_audit

admin_bp = Blueprint('admin', __name__)


def utcnow():
    return datetime.now(timezone.utc)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin.admin_login'))
        admin = Admin.query.get(session['admin_id'])
        if not admin or not admin.is_active:
            session.pop('admin_id', None)
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated


def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin.admin_login'))
        admin = Admin.query.get(session['admin_id'])
        if not admin or admin.role != 'superadmin':
            flash('Super admin access required.', 'error')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


def get_current_admin():
    admin_id = session.get('admin_id')
    return Admin.query.get(admin_id) if admin_id else None


# ─── Auth ──────────────────────────────────────────────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_id'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        data = request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')

        admin = (Admin.query.filter_by(username=username).first()
                 or Admin.query.filter_by(email=username).first())

        if admin and admin.check_password(password) and admin.is_active:
            session['admin_id'] = admin.id
            session.permanent = True
            admin.last_login = utcnow()
            db.session.commit()
            log_audit('admin_login', actor_id=admin.id, actor_type='admin', ip=request.remote_addr)
            return redirect(url_for('admin.dashboard'))

        flash('Invalid credentials.', 'error')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
def admin_logout():
    admin_id = session.pop('admin_id', None)
    if admin_id:
        log_audit('admin_logout', actor_id=admin_id, actor_type='admin', ip=request.remote_addr)
    flash('Logged out from admin panel.', 'info')
    return redirect(url_for('admin.admin_login'))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    admin = get_current_admin()
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter(User.last_seen >= now - timedelta(days=7)).count(),
        'online_users': User.query.filter_by(is_online=True).count(),
        'new_users_today': User.query.filter(User.created_at >= today_start).count(),
        'total_messages': Message.query.count(),
        'messages_today': Message.query.filter(Message.created_at >= today_start).count(),
        'total_groups': Group.query.count(),
        'total_media': MediaFile.query.count(),
        'total_views': Analytics.query.filter_by(event_type='pageview').count(),
        'views_today': Analytics.query.filter(Analytics.created_at >= today_start, Analytics.event_type == 'pageview').count(),
        'pending_reports': UserReport.query.filter_by(status='pending').count(),
        'banned_users': User.query.filter_by(is_banned=True).count(),
    }

    # Recent activity
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_reports = UserReport.query.filter_by(status='pending').order_by(UserReport.created_at.desc()).limit(5).all()
    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           admin=admin, stats=stats,
                           recent_users=recent_users,
                           recent_reports=recent_reports,
                           recent_audit=recent_audit)


# ─── User Management ──────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    admin = get_current_admin()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')

    q = User.query
    if search:
        q = q.filter(
            User.username.ilike(f'%{search}%') |
            User.display_name.ilike(f'%{search}%') |
            User.email.ilike(f'%{search}%') |
            User.phone.ilike(f'%{search}%')
        )
    if status == 'banned':
        q = q.filter_by(is_banned=True)
    elif status == 'online':
        q = q.filter_by(is_online=True)
    elif status == 'verified':
        q = q.filter_by(is_verified=True)

    users = q.order_by(User.created_at.desc()).paginate(page=page, per_page=25)
    return render_template('admin/users.html', admin=admin, users=users, search=search, status=status)


@admin_bp.route('/users/<user_id>')
@admin_required
def user_detail(user_id):
    admin = get_current_admin()
    user = User.query.get_or_404(user_id)
    sessions = user.sessions.order_by('created_at').limit(10).all()
    reports = UserReport.query.filter_by(reported_id=user_id).order_by(UserReport.created_at.desc()).limit(20).all()
    return render_template('admin/user_detail.html', admin=admin, user=user, sessions=sessions, reports=reports)


@admin_bp.route('/users/<user_id>/ban', methods=['POST'])
@admin_required
def ban_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json() if request.is_json else request.form
    reason = data.get('reason', 'Violation of terms of service')
    user.is_banned = True
    user.ban_reason = reason[:500]
    user.is_online = False
    db.session.commit()
    log_audit('user_banned', actor_id=session.get('admin_id'), actor_type='admin',
              target_id=user_id, details=reason, ip=request.remote_addr)
    if request.is_json:
        return jsonify({'success': True})
    flash(f'User {user.username} has been banned.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<user_id>/unban', methods=['POST'])
@admin_required
def unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    user.ban_reason = None
    db.session.commit()
    log_audit('user_unbanned', actor_id=session.get('admin_id'), actor_type='admin',
              target_id=user_id, ip=request.remote_addr)
    if request.is_json:
        return jsonify({'success': True})
    flash(f'User {user.username} has been unbanned.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json() if request.is_json else request.form
    days = int(data.get('days', 7))
    user.is_suspended = True
    user.suspension_until = utcnow() + timedelta(days=days)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash(f'User suspended for {days} days.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<user_id>/verify', methods=['POST'])
@admin_required
def verify_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'is_verified': user.is_verified})
    flash(f'User verification status updated.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<user_id>/delete', methods=['POST'])
@superadmin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    log_audit('user_deleted', actor_id=session.get('admin_id'), actor_type='admin',
              target_id=user_id, ip=request.remote_addr)
    flash(f'User {username} deleted.', 'success')
    return redirect(url_for('admin.users'))


# ─── Reports ──────────────────────────────────────────────────────────────────

@admin_bp.route('/reports')
@admin_required
def reports():
    admin = get_current_admin()
    status = request.args.get('status', 'pending')
    reports = UserReport.query.filter_by(status=status).order_by(UserReport.created_at.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=25)
    return render_template('admin/reports.html', admin=admin, reports=reports, status=status)


@admin_bp.route('/reports/<report_id>/resolve', methods=['POST'])
@admin_required
def resolve_report(report_id):
    report = UserReport.query.get_or_404(report_id)
    data = request.get_json() if request.is_json else request.form
    action = data.get('action', 'resolved')
    report.status = action
    report.reviewed_by = session.get('admin_id')
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash('Report updated.', 'success')
    return redirect(url_for('admin.reports'))


# ─── Settings ────────────────────────────────────────────────────────────────

@admin_bp.route('/settings')
@admin_required
def settings():
    admin = get_current_admin()
    categories = {}
    all_settings = SiteSettings.query.order_by(SiteSettings.category, SiteSettings.key).all()
    for s in all_settings:
        if s.category not in categories:
            categories[s.category] = []
        categories[s.category].append(s)
    return render_template('admin/settings.html', admin=admin, categories=categories)


@admin_bp.route('/settings/update', methods=['POST'])
@admin_required
def update_settings():
    data = request.get_json() if request.is_json else request.form
    admin_id = session.get('admin_id')
    updated = []

    for key, value in data.items():
        if key.startswith('_'):
            continue
        existing = SiteSettings.query.filter_by(key=key).first()
        if existing:
            existing.value = str(value) if value is not None else ''
            existing.updated_by = admin_id
            updated.append(key)

    db.session.commit()
    log_audit('settings_updated', actor_id=admin_id, actor_type='admin',
              details=f'Updated: {", ".join(updated)}', ip=request.remote_addr)

    if request.is_json:
        return jsonify({'success': True, 'updated': updated})
    flash(f'{len(updated)} settings updated.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/settings/contact', methods=['POST'])
@admin_required
def update_contact_settings():
    """Update helpline, email, phone, and other contact details."""
    data = request.get_json() if request.is_json else request.form
    admin_id = session.get('admin_id')

    contact_keys = [
        'helpline_number', 'support_email', 'support_phone',
        'contact_gmail', 'contact_address', 'contact_whatsapp',
        'facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url',
        'youtube_url', 'tiktok_url'
    ]

    for key in contact_keys:
        if key in data:
            SiteSettings.set(key, data[key], category='contact',
                             label=key.replace('_', ' ').title(),
                             updated_by=admin_id)

    log_audit('contact_settings_updated', actor_id=admin_id, actor_type='admin', ip=request.remote_addr)
    if request.is_json:
        return jsonify({'success': True})
    flash('Contact settings updated.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/settings/smtp', methods=['POST'])
@admin_required
def update_smtp_settings():
    """Update SMTP / email settings."""
    data = request.get_json() if request.is_json else request.form
    admin_id = session.get('admin_id')

    smtp_keys = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password',
                 'smtp_use_tls', 'mail_default_sender', 'contact_gmail']

    for key in smtp_keys:
        if key in data:
            SiteSettings.set(key, data[key], category='smtp', label=key.replace('_', ' ').title(), updated_by=admin_id)

    log_audit('smtp_settings_updated', actor_id=admin_id, actor_type='admin', ip=request.remote_addr)
    if request.is_json:
        return jsonify({'success': True})
    flash('SMTP settings updated.', 'success')
    return redirect(url_for('admin.settings'))


# ─── Theme / Branding ─────────────────────────────────────────────────────────

@admin_bp.route('/settings/theme', methods=['POST'])
@admin_required
def update_theme():
    data = request.get_json() if request.is_json else request.form
    admin_id = session.get('admin_id')

    theme_keys = ['primary_color', 'secondary_color', 'accent_color',
                  'background_color', 'font_family', 'logo_url', 'favicon_url']

    for key in theme_keys:
        if key in data:
            SiteSettings.set(key, data[key], category='theme', label=key.replace('_', ' ').title(), updated_by=admin_id)

    if request.is_json:
        return jsonify({'success': True})
    flash('Theme updated.', 'success')
    return redirect(url_for('admin.settings'))


# ─── CMS Pages ───────────────────────────────────────────────────────────────

@admin_bp.route('/pages')
@admin_required
def pages():
    admin = get_current_admin()
    pages = CMSPage.query.order_by(CMSPage.title).all()
    return render_template('admin/pages.html', admin=admin, pages=pages)


@admin_bp.route('/pages/new', methods=['GET', 'POST'])
@admin_required
def new_page():
    admin = get_current_admin()
    if request.method == 'POST':
        data = request.form
        title = data.get('title', '').strip()
        slug = data.get('slug', '').strip().lower().replace(' ', '-')
        content = data.get('content', '')
        meta_title = data.get('meta_title', '').strip()
        meta_description = data.get('meta_description', '').strip()
        is_published = data.get('is_published') == 'on'

        if not title or not slug:
            flash('Title and slug are required.', 'error')
            return render_template('admin/page_editor.html', admin=admin, page=None)

        if CMSPage.query.filter_by(slug=slug).first():
            flash('Slug already exists.', 'error')
            return render_template('admin/page_editor.html', admin=admin, page=None)

        page = CMSPage(
            id=str(uuid.uuid4()),
            title=title,
            slug=slug,
            content=content,
            meta_title=meta_title,
            meta_description=meta_description,
            is_published=is_published,
            created_by=session.get('admin_id')
        )
        db.session.add(page)
        db.session.commit()
        flash(f'Page "{title}" created.', 'success')
        return redirect(url_for('admin.pages'))

    return render_template('admin/page_editor.html', admin=admin, page=None)


@admin_bp.route('/pages/<page_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_page(page_id):
    admin = get_current_admin()
    page = CMSPage.query.get_or_404(page_id)

    if request.method == 'POST':
        data = request.form
        page.title = data.get('title', page.title).strip()
        if not page.is_system:
            new_slug = data.get('slug', page.slug).strip().lower().replace(' ', '-')
            if new_slug != page.slug and CMSPage.query.filter_by(slug=new_slug).first():
                flash('Slug already exists.', 'error')
                return render_template('admin/page_editor.html', admin=admin, page=page)
            page.slug = new_slug
        page.content = data.get('content', page.content)
        page.meta_title = data.get('meta_title', '').strip()
        page.meta_description = data.get('meta_description', '').strip()
        page.meta_keywords = data.get('meta_keywords', '').strip()
        page.is_published = data.get('is_published') == 'on'
        page.updated_by = session.get('admin_id')
        db.session.commit()
        flash(f'Page "{page.title}" updated.', 'success')
        return redirect(url_for('admin.pages'))

    return render_template('admin/page_editor.html', admin=admin, page=page)


@admin_bp.route('/pages/<page_id>/delete', methods=['POST'])
@admin_required
def delete_page(page_id):
    page = CMSPage.query.get_or_404(page_id)
    if page.is_system:
        flash('Cannot delete system pages.', 'error')
        return redirect(url_for('admin.pages'))
    db.session.delete(page)
    db.session.commit()
    flash('Page deleted.', 'success')
    return redirect(url_for('admin.pages'))


# ─── Announcements ────────────────────────────────────────────────────────────

@admin_bp.route('/announcements')
@admin_required
def announcements():
    admin = get_current_admin()
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/announcements.html', admin=admin, announcements=announcements)


@admin_bp.route('/announcements/new', methods=['POST'])
@admin_required
def create_announcement():
    data = request.get_json() if request.is_json else request.form
    ann = Announcement(
        id=str(uuid.uuid4()),
        title=data.get('title', '').strip(),
        content=data.get('content', '').strip(),
        type=data.get('type', 'banner'),
        color=data.get('color', 'purple'),
        is_active=True,
        target=data.get('target', 'all'),
        created_by=session.get('admin_id')
    )
    db.session.add(ann)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'id': ann.id})
    flash('Announcement created.', 'success')
    return redirect(url_for('admin.announcements'))


@admin_bp.route('/announcements/<ann_id>/toggle', methods=['POST'])
@admin_required
def toggle_announcement(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    ann.is_active = not ann.is_active
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'is_active': ann.is_active})
    flash('Announcement updated.', 'success')
    return redirect(url_for('admin.announcements'))


@admin_bp.route('/announcements/<ann_id>/delete', methods=['POST'])
@admin_required
def delete_announcement(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    db.session.delete(ann)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash('Announcement deleted.', 'success')
    return redirect(url_for('admin.announcements'))


# ─── Advertisements ──────────────────────────────────────────────────────────

@admin_bp.route('/ads')
@admin_required
def ads():
    admin = get_current_admin()
    ads = Advertisement.query.order_by(Advertisement.created_at.desc()).all()
    return render_template('admin/ads.html', admin=admin, ads=ads)


@admin_bp.route('/ads/new', methods=['POST'])
@admin_required
def create_ad():
    data = request.get_json() if request.is_json else request.form
    ad = Advertisement(
        id=str(uuid.uuid4()),
        name=data.get('name', ''),
        type=data.get('type', 'banner'),
        image_url=data.get('image_url', ''),
        link_url=data.get('link_url', ''),
        html_content=data.get('html_content', ''),
        placement=data.get('placement', 'landing'),
        is_active=True,
    )
    db.session.add(ad)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'id': ad.id})
    flash('Ad created.', 'success')
    return redirect(url_for('admin.ads'))


# ─── Analytics ────────────────────────────────────────────────────────────────

@admin_bp.route('/analytics')
@admin_required
def analytics():
    admin = get_current_admin()
    now = utcnow()

    # Views per day (last 30 days)
    from sqlalchemy import func
    daily_views = db.session.query(
        func.date(Analytics.created_at).label('date'),
        func.count().label('count')
    ).filter(
        Analytics.created_at >= now - timedelta(days=30),
        Analytics.event_type == 'pageview'
    ).group_by(func.date(Analytics.created_at)).order_by('date').all()

    device_stats = db.session.query(
        Analytics.device_type, func.count().label('count')
    ).filter(Analytics.device_type.isnot(None)).group_by(Analytics.device_type).all()

    return render_template('admin/analytics.html',
                           admin=admin,
                           daily_views=daily_views,
                           device_stats=device_stats)


# ─── Audit Logs ───────────────────────────────────────────────────────────────

@admin_bp.route('/audit')
@admin_required
def audit_logs():
    admin = get_current_admin()
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('admin/audit.html', admin=admin, logs=logs)


# ─── Landing Page Editor ──────────────────────────────────────────────────────

@admin_bp.route('/landing')
@admin_required
def landing_editor():
    admin = get_current_admin()
    landing_settings = SiteSettings.query.filter_by(category='landing').all()
    settings = {s.key: s.value for s in landing_settings}
    return render_template('admin/landing_editor.html', admin=admin, settings=settings)


@admin_bp.route('/landing/update', methods=['POST'])
@admin_required
def update_landing():
    data = request.get_json() if request.is_json else request.form
    admin_id = session.get('admin_id')

    landing_keys = ['hero_title', 'hero_subtitle', 'hero_bg_color', 'hero_button_text',
                    'features_title', 'features_subtitle', 'footer_text',
                    'app_tagline', 'download_text']

    for key in landing_keys:
        if key in data:
            SiteSettings.set(key, data[key], category='landing', label=key.replace('_', ' ').title(), updated_by=admin_id)

    if request.is_json:
        return jsonify({'success': True})
    flash('Landing page updated.', 'success')
    return redirect(url_for('admin.landing_editor'))


# ─── Admin Management ─────────────────────────────────────────────────────────

@admin_bp.route('/admins')
@superadmin_required
def admins():
    current_admin = get_current_admin()
    all_admins = Admin.query.order_by(Admin.created_at.desc()).all()
    return render_template('admin/admins.html', admin=current_admin, admins=all_admins)


@admin_bp.route('/admins/new', methods=['POST'])
@superadmin_required
def create_admin():
    data = request.get_json() if request.is_json else request.form
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'admin')

    if Admin.query.filter_by(username=username).first():
        msg = 'Username already exists.'
        if request.is_json:
            return jsonify({'error': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('admin.admins'))

    new_admin = Admin(id=str(uuid.uuid4()), username=username, email=email, role=role)
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash(f'Admin {username} created.', 'success')
    return redirect(url_for('admin.admins'))


# ─── DataVault ────────────────────────────────────────────────────────────────

@admin_bp.route('/datavault')
@admin_required
def datavault():
    from ..models import DataVault
    admin = get_current_admin()
    vaults = DataVault.query.order_by(DataVault.created_at.desc()).all()
    return render_template('admin/datavault.html', admin=admin, vaults=vaults)


@admin_bp.route('/datavault/new', methods=['POST'])
@admin_required
def create_vault():
    from ..models import DataVault
    data = request.get_json() if request.is_json else request.form
    vault = DataVault(
        id=str(uuid.uuid4()),
        name=data.get('name', '').strip(),
        description=data.get('description', '').strip(),
        vault_type=data.get('vault_type', 'general'),
        data=data.get('data', ''),
        is_encrypted=data.get('is_encrypted', False) in (True, 'true', '1', 'on'),
        is_public=data.get('is_public', False) in (True, 'true', '1', 'on'),
        tags=data.get('tags', '').strip(),
        created_by=session.get('admin_id'),
    )
    db.session.add(vault)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'id': vault.id})
    flash('Vault entry created.', 'success')
    return redirect(url_for('admin.datavault'))


@admin_bp.route('/datavault/<vault_id>', methods=['GET'])
@admin_required
def view_vault(vault_id):
    from ..models import DataVault
    admin = get_current_admin()
    vault = DataVault.query.get_or_404(vault_id)
    return render_template('admin/datavault_detail.html', admin=admin, vault=vault)


@admin_bp.route('/datavault/<vault_id>/delete', methods=['POST'])
@admin_required
def delete_vault(vault_id):
    from ..models import DataVault
    vault = DataVault.query.get_or_404(vault_id)
    db.session.delete(vault)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash('Vault entry deleted.', 'success')
    return redirect(url_for('admin.datavault'))


@admin_bp.route('/datavault/export-users', methods=['POST'])
@admin_required
def export_users_vault():
    """Export all user data to DataVault."""
    from ..models import DataVault
    import json as json_lib
    users = User.query.all()
    data = [{
        'id': u.id, 'username': u.username, 'email': u.email,
        'phone': u.phone, 'display_name': u.display_name,
        'is_banned': u.is_banned, 'is_verified': u.is_verified,
        'created_at': u.created_at.isoformat(),
    } for u in users]
    vault = DataVault(
        id=str(uuid.uuid4()),
        name='User Export - {}'.format(utcnow().strftime('%Y-%m-%d %H:%M')),
        description='Full user data export',
        vault_type='export',
        data=json_lib.dumps(data),
        created_by=session.get('admin_id'),
    )
    db.session.add(vault)
    db.session.commit()
    return jsonify({'success': True, 'id': vault.id, 'count': len(data)})
