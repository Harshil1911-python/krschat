# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Database Models
Complete SQLAlchemy models for all entities
"""
from datetime import datetime, timezone
import uuid
import json
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

db = SQLAlchemy()
ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def utcnow():
    return datetime.now(timezone.utc)


def gen_uuid():
    return str(uuid.uuid4())


# ─── Association Tables ────────────────────────────────────────────────────────

group_members = db.Table('group_members',
    db.Column('user_id', db.String(36), db.ForeignKey('users.id'), primary_key=True),
    db.Column('group_id', db.String(36), db.ForeignKey('groups.id'), primary_key=True),
    db.Column('role', db.String(20), default='member'),
    db.Column('joined_at', db.DateTime(timezone=True), default=utcnow),
    db.Column('is_muted', db.Boolean, default=False),
)

blocked_users = db.Table('blocked_users',
    db.Column('blocker_id', db.String(36), db.ForeignKey('users.id'), primary_key=True),
    db.Column('blocked_id', db.String(36), db.ForeignKey('users.id'), primary_key=True),
    db.Column('blocked_at', db.DateTime(timezone=True), default=utcnow),
)


# ─── User ──────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(500), default='')
    avatar_url = db.Column(db.String(500), default='')
    avatar_public_id = db.Column(db.String(255), default='')

    # Status
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime(timezone=True), default=utcnow)
    is_verified = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_suspended = db.Column(db.Boolean, default=False)
    suspension_until = db.Column(db.DateTime(timezone=True), nullable=True)
    ban_reason = db.Column(db.String(500), nullable=True)

    # Email verification
    email_verified = db.Column(db.Boolean, default=False)
    email_verify_token = db.Column(db.String(128), nullable=True)

    # Password reset
    reset_token = db.Column(db.String(128), nullable=True)
    reset_token_expires = db.Column(db.DateTime(timezone=True), nullable=True)

    # Security
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(64), nullable=True)

    # Privacy
    show_last_seen = db.Column(db.Boolean, default=True)
    show_online_status = db.Column(db.Boolean, default=True)
    show_read_receipts = db.Column(db.Boolean, default=True)
    profile_visibility = db.Column(db.String(20), default='everyone')

    # Theme
    theme = db.Column(db.String(10), default='dark')

    # Push notifications
    push_token = db.Column(db.String(255), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # E2EE public key
    public_key = db.Column(db.Text, nullable=True)

    # Relationships
    sessions = db.relationship('UserSession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    media_files = db.relationship('MediaFile', backref='uploader', lazy='dynamic')
    reports_made = db.relationship('UserReport', foreign_keys='UserReport.reporter_id', backref='reporter', lazy='dynamic')
    reports_received = db.relationship('UserReport', foreign_keys='UserReport.reported_id', backref='reported', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = ph.hash(password)

    def check_password(self, password):
        try:
            return ph.verify(self.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self):
        return ph.check_needs_rehash(self.password_hash)

    def to_dict(self, include_private=False):
        data = {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'bio': self.bio,
            'avatar_url': self.avatar_url or '/static/images/default-avatar.png',
            'is_online': self.is_online,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_verified': self.is_verified,
            'theme': self.theme,
            'created_at': self.created_at.isoformat(),
        }
        if include_private:
            data.update({
                'email': self.email,
                'phone': self.phone,
                'show_last_seen': self.show_last_seen,
                'show_online_status': self.show_online_status,
                'show_read_receipts': self.show_read_receipts,
                'notifications_enabled': self.notifications_enabled,
                'two_factor_enabled': self.two_factor_enabled,
            })
        return data

    def __repr__(self):
        return f'<User {self.username}>'


# ─── User Session ──────────────────────────────────────────────────────────────

class UserSession(db.Model):
    __tablename__ = 'user_sessions'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    token_jti = db.Column(db.String(128), unique=True, nullable=False)
    refresh_token_jti = db.Column(db.String(128), nullable=True)
    device_name = db.Column(db.String(100), nullable=True)
    device_type = db.Column(db.String(50), nullable=True)
    browser = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    last_active = db.Column(db.DateTime(timezone=True), default=utcnow)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)


# ─── Chat ─────────────────────────────────────────────────────────────────────

class Chat(db.Model):
    __tablename__ = 'chats'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    type = db.Column(db.String(20), default='direct')  # direct, group
    user1_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    user2_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    group_id = db.Column(db.String(36), db.ForeignKey('groups.id'), nullable=True)
    last_message_id = db.Column(db.String(36), nullable=True)
    last_message_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    is_archived_by = db.Column(db.Text, default='[]')  # JSON list of user IDs
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])
    messages = db.relationship('Message', backref='chat', lazy='dynamic', cascade='all, delete-orphan')

    def get_archived_by(self):
        try:
            return json.loads(self.is_archived_by or '[]')
        except Exception:
            return []

    def archive_for(self, user_id):
        archived = self.get_archived_by()
        if user_id not in archived:
            archived.append(user_id)
        self.is_archived_by = json.dumps(archived)

    def unarchive_for(self, user_id):
        archived = self.get_archived_by()
        if user_id in archived:
            archived.remove(user_id)
        self.is_archived_by = json.dumps(archived)


# ─── Message ──────────────────────────────────────────────────────────────────

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    chat_id = db.Column(db.String(36), db.ForeignKey('chats.id'), nullable=False, index=True)
    sender_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=True)
    content_encrypted = db.Column(db.Text, nullable=True)  # E2EE encrypted content
    message_type = db.Column(db.String(20), default='text')  # text, image, video, audio, document, voice, system
    media_url = db.Column(db.String(500), nullable=True)
    media_public_id = db.Column(db.String(255), nullable=True)
    media_type = db.Column(db.String(50), nullable=True)
    media_size = db.Column(db.Integer, nullable=True)
    media_name = db.Column(db.String(255), nullable=True)
    media_duration = db.Column(db.Float, nullable=True)  # for audio/video
    thumbnail_url = db.Column(db.String(500), nullable=True)

    # Reply
    reply_to_id = db.Column(db.String(36), db.ForeignKey('messages.id'), nullable=True)

    # Status
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_for = db.Column(db.Text, default='[]')  # JSON list of user IDs
    is_pinned = db.Column(db.Boolean, default=False)
    is_forwarded = db.Column(db.Boolean, default=False)

    # Delivery
    delivered_at = db.Column(db.DateTime(timezone=True), nullable=True)
    read_by = db.Column(db.Text, default='[]')  # JSON list of {user_id, read_at}

    # Reactions
    reactions = db.Column(db.Text, default='{}')  # JSON {emoji: [user_ids]}

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    reply_to = db.relationship('Message', remote_side=[id])

    def get_read_by(self):
        try:
            return json.loads(self.read_by or '[]')
        except Exception:
            return []

    def mark_read_by(self, user_id):
        read = self.get_read_by()
        if not any(r['user_id'] == user_id for r in read):
            read.append({'user_id': user_id, 'read_at': utcnow().isoformat()})
            self.read_by = json.dumps(read)

    def get_reactions(self):
        try:
            return json.loads(self.reactions or '{}')
        except Exception:
            return {}

    def add_reaction(self, emoji, user_id):
        reactions = self.get_reactions()
        if emoji not in reactions:
            reactions[emoji] = []
        if user_id not in reactions[emoji]:
            reactions[emoji].append(user_id)
        self.reactions = json.dumps(reactions)

    def remove_reaction(self, emoji, user_id):
        reactions = self.get_reactions()
        if emoji in reactions and user_id in reactions[emoji]:
            reactions[emoji].remove(user_id)
            if not reactions[emoji]:
                del reactions[emoji]
        self.reactions = json.dumps(reactions)

    def to_dict(self):
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'sender_id': self.sender_id,
            'content': self.content if not self.is_deleted else None,
            'message_type': self.message_type,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'media_name': self.media_name,
            'media_size': self.media_size,
            'thumbnail_url': self.thumbnail_url,
            'reply_to_id': self.reply_to_id,
            'is_edited': self.is_edited,
            'is_deleted': self.is_deleted,
            'is_pinned': self.is_pinned,
            'is_forwarded': self.is_forwarded,
            'reactions': self.get_reactions(),
            'read_by': self.get_read_by(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


# ─── Group ─────────────────────────────────────────────────────────────────────

class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), default='')
    avatar_url = db.Column(db.String(500), nullable=True)
    avatar_public_id = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    invite_link = db.Column(db.String(64), unique=True, nullable=True)
    is_public = db.Column(db.Boolean, default=False)
    max_members = db.Column(db.Integer, default=256)

    # Permissions
    only_admins_can_send = db.Column(db.Boolean, default=False)
    only_admins_can_add_members = db.Column(db.Boolean, default=False)
    only_admins_can_edit_info = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])
    members = db.relationship('User', secondary=group_members, lazy='subquery',
                               backref=db.backref('groups', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'avatar_url': self.avatar_url or '/static/images/default-group.png',
            'created_by': self.created_by,
            'invite_link': self.invite_link,
            'is_public': self.is_public,
            'member_count': len(self.members),
            'created_at': self.created_at.isoformat(),
        }


# ─── Media File ────────────────────────────────────────────────────────────────

class MediaFile(db.Model):
    __tablename__ = 'media_files'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    uploader_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=False)
    url = db.Column(db.String(500), nullable=False)
    public_id = db.Column(db.String(255), nullable=True)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    is_malware_checked = db.Column(db.Boolean, default=False)
    is_safe = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


# ─── Admin ─────────────────────────────────────────────────────────────────────

class Admin(db.Model):
    __tablename__ = 'admins'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='admin')  # superadmin, admin, moderator
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def set_password(self, password):
        self.password_hash = ph.hash(password)

    def check_password(self, password):
        try:
            return ph.verify(self.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


# ─── Site Settings ─────────────────────────────────────────────────────────────

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    value_type = db.Column(db.String(20), default='string')  # string, json, bool, int
    category = db.Column(db.String(50), default='general')
    label = db.Column(db.String(200), nullable=True)
    description = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by = db.Column(db.String(36), nullable=True)

    @classmethod
    def get(cls, key, default=None):
        setting = cls.query.filter_by(key=key).first()
        if setting is None:
            return default
        if setting.value_type == 'bool':
            return setting.value.lower() in ('true', '1', 'yes') if setting.value else False
        if setting.value_type == 'int':
            return int(setting.value) if setting.value else default
        if setting.value_type == 'json':
            try:
                return json.loads(setting.value)
            except Exception:
                return default
        return setting.value if setting.value is not None else default

    @classmethod
    def set(cls, key, value, category='general', label=None, value_type='string', updated_by=None):
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            setting = cls(key=key, category=category, label=label or key, value_type=value_type)
            db.session.add(setting)
        if value_type == 'json':
            setting.value = json.dumps(value)
        else:
            setting.value = str(value) if value is not None else None
        setting.value_type = value_type
        if updated_by:
            setting.updated_by = updated_by
        db.session.commit()
        return setting


# ─── CMS Page ─────────────────────────────────────────────────────────────────

class CMSPage(db.Model):
    __tablename__ = 'cms_pages'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=True)
    meta_title = db.Column(db.String(200), nullable=True)
    meta_description = db.Column(db.String(500), nullable=True)
    meta_keywords = db.Column(db.String(500), nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)  # can't delete system pages
    template = db.Column(db.String(50), default='default')
    created_by = db.Column(db.String(36), nullable=True)
    updated_by = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ─── Announcement ─────────────────────────────────────────────────────────────

class Announcement(db.Model):
    __tablename__ = 'announcements'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='banner')  # banner, popup, push
    color = db.Column(db.String(20), default='purple')
    is_active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    target = db.Column(db.String(20), default='all')  # all, users, guests
    created_by = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


# ─── Advertisement ─────────────────────────────────────────────────────────────

class Advertisement(db.Model):
    __tablename__ = 'advertisements'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), default='banner')
    image_url = db.Column(db.String(500), nullable=True)
    link_url = db.Column(db.String(500), nullable=True)
    html_content = db.Column(db.Text, nullable=True)
    placement = db.Column(db.String(50), default='landing')
    impressions = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


# ─── Analytics ─────────────────────────────────────────────────────────────────

class Analytics(db.Model):
    __tablename__ = 'analytics'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    user_id = db.Column(db.String(36), nullable=True, index=True)
    session_id = db.Column(db.String(128), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    device_type = db.Column(db.String(50), nullable=True)
    browser = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)
    path = db.Column(db.String(500), nullable=True)
    extra_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)


# ─── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    actor_id = db.Column(db.String(36), nullable=True)
    actor_type = db.Column(db.String(20), default='user')  # user, admin, system
    action = db.Column(db.String(100), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.String(36), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)


# ─── User Report ───────────────────────────────────────────────────────────────

class UserReport(db.Model):
    __tablename__ = 'user_reports'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    reporter_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    reported_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, resolved, dismissed
    reviewed_by = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ─── QR Login Token ───────────────────────────────────────────────────────────

class QRLoginToken(db.Model):
    __tablename__ = 'qr_login_tokens'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.String(36), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, scanned, confirmed, expired
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


# ─── DataVault ─────────────────────────────────────────────────────────────────

class DataVault(db.Model):
    __tablename__ = 'data_vault'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    vault_type = db.Column(db.String(50), default='general')  # general, backup, export, import
    data = db.Column(db.Text, nullable=True)  # JSON data
    file_url = db.Column(db.String(500), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False)
    encryption_key_hint = db.Column(db.String(100), nullable=True)
    created_by = db.Column(db.String(36), nullable=True)
    is_public = db.Column(db.Boolean, default=False)
    tags = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'vault_type': self.vault_type,
            'file_url': self.file_url,
            'file_size': self.file_size,
            'is_encrypted': self.is_encrypted,
            'is_public': self.is_public,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
        }
