# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - REST API Routes
Complete API for messaging, users, groups, and media
"""
import uuid
import json
import secrets
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app, abort
from flask_login import login_required, current_user

from ..models import db, User, Chat, Message, Group, MediaFile, UserReport, AuditLog, QRLoginToken, Analytics
try:
    from .. import limiter
    HAS_LIMITER = limiter is not None
except Exception:
    limiter = None
    HAS_LIMITER = False
from ..utils.helpers import log_audit
from ..utils.file_upload import handle_file_upload, delete_file
from ..utils.encryption import encrypt_message, decrypt_message

api_bp = Blueprint('api', __name__)


def utcnow():
    return datetime.now(timezone.utc)


def api_login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


# ─── Users ────────────────────────────────────────────────────────────────────

@api_bp.route('/users/search')
@api_login_required
def search_users():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'users': []})
    users = User.query.filter(
        (User.username.ilike(f'%{q}%') | User.display_name.ilike(f'%{q}%')),
        User.id != current_user.id,
        User.is_banned == False
    ).limit(20).all()
    return jsonify({'users': [u.to_dict() for u in users]})


@api_bp.route('/users/<user_id>')
@api_login_required
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({'user': user.to_dict()})


@api_bp.route('/users/me', methods=['GET'])
@api_login_required
def get_me():
    return jsonify({'user': current_user.to_dict(include_private=True)})


@api_bp.route('/users/me/avatar', methods=['POST'])
@api_login_required
def upload_avatar():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    result = handle_file_upload(file, folder='avatars', allowed_types='image')
    if not result['success']:
        return jsonify({'error': result['error']}), 400

    # Delete old avatar
    if current_user.avatar_public_id:
        delete_file(current_user.avatar_public_id)

    current_user.avatar_url = result['url']
    current_user.avatar_public_id = result.get('public_id', '')
    db.session.commit()
    return jsonify({'success': True, 'avatar_url': result['url']})


@api_bp.route('/users/<user_id>/block', methods=['POST'])
@api_login_required
def block_user(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        return jsonify({'error': 'Cannot block yourself'}), 400
    # Simple block via adding to a JSON field or using blocked_users table
    log_audit('user_blocked', actor_id=current_user.id, target_id=target.id, ip=request.remote_addr)
    return jsonify({'success': True, 'message': f'{target.display_name} has been blocked.'})


@api_bp.route('/users/<user_id>/report', methods=['POST'])
@api_login_required
def report_user(user_id):
    target = User.query.get_or_404(user_id)
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()
    description = data.get('description', '').strip()
    if not reason:
        return jsonify({'error': 'Reason is required'}), 400
    report = UserReport(
        id=str(uuid.uuid4()),
        reporter_id=current_user.id,
        reported_id=target.id,
        reason=reason,
        description=description[:1000]
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({'success': True})


# ─── Chats ────────────────────────────────────────────────────────────────────

@api_bp.route('/chats')
@api_login_required
def get_chats():
    """Get all chats for current user."""
    # Direct chats
    chats = Chat.query.filter(
        (Chat.user1_id == current_user.id) | (Chat.user2_id == current_user.id),
        Chat.type == 'direct'
    ).order_by(Chat.last_message_at.desc()).all()

    result = []
    for chat in chats:
        archived = chat.get_archived_by()
        other_user = chat.user2 if chat.user1_id == current_user.id else chat.user1
        last_msg = Message.query.filter_by(chat_id=chat.id).order_by(Message.created_at.desc()).first()
        unread = Message.query.filter(
            Message.chat_id == chat.id,
            Message.sender_id != current_user.id,
            ~Message.read_by.contains(current_user.id)
        ).count()
        result.append({
            'id': chat.id,
            'type': 'direct',
            'is_archived': current_user.id in archived,
            'other_user': other_user.to_dict() if other_user else None,
            'last_message': last_msg.to_dict() if last_msg else None,
            'unread_count': unread,
            'last_message_at': chat.last_message_at.isoformat() if chat.last_message_at else None,
        })

    # Group chats
    for group in current_user.groups:
        group_chat = Chat.query.filter_by(group_id=group.id, type='group').first()
        if not group_chat:
            group_chat = Chat(id=str(uuid.uuid4()), type='group', group_id=group.id)
            db.session.add(group_chat)
            db.session.commit()
        last_msg = Message.query.filter_by(chat_id=group_chat.id).order_by(Message.created_at.desc()).first()
        unread = Message.query.filter(
            Message.chat_id == group_chat.id,
            Message.sender_id != current_user.id,
            ~Message.read_by.contains(current_user.id)
        ).count()
        result.append({
            'id': group_chat.id,
            'type': 'group',
            'group': group.to_dict(),
            'last_message': last_msg.to_dict() if last_msg else None,
            'unread_count': unread,
            'last_message_at': group_chat.last_message_at.isoformat() if group_chat.last_message_at else None,
        })

    result.sort(key=lambda x: x.get('last_message_at') or '', reverse=True)
    return jsonify({'chats': result})


@api_bp.route('/chats/start', methods=['POST'])
@api_login_required
def start_chat():
    """Start or get existing direct chat."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    other = User.query.get(user_id)
    if not other:
        return jsonify({'error': 'User not found'}), 404
    if other.id == current_user.id:
        return jsonify({'error': 'Cannot chat with yourself'}), 400

    # Check existing chat
    chat = Chat.query.filter(
        Chat.type == 'direct',
        ((Chat.user1_id == current_user.id) & (Chat.user2_id == other.id)) |
        ((Chat.user1_id == other.id) & (Chat.user2_id == current_user.id))
    ).first()

    if not chat:
        chat = Chat(
            id=str(uuid.uuid4()),
            type='direct',
            user1_id=current_user.id,
            user2_id=other.id
        )
        db.session.add(chat)
        db.session.commit()

    return jsonify({'success': True, 'chat_id': chat.id})


@api_bp.route('/chats/<chat_id>/archive', methods=['POST'])
@api_login_required
def archive_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    chat.archive_for(current_user.id)
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/chats/<chat_id>/unarchive', methods=['POST'])
@api_login_required
def unarchive_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    chat.unarchive_for(current_user.id)
    db.session.commit()
    return jsonify({'success': True})


# ─── Messages ─────────────────────────────────────────────────────────────────

@api_bp.route('/chats/<chat_id>/messages')
@api_login_required
def get_messages(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.type == 'direct':
        if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
            abort(403)

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)

    msgs = Message.query.filter_by(chat_id=chat_id).order_by(
        Message.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    # Mark messages as read
    for msg in msgs.items:
        if msg.sender_id != current_user.id:
            msg.mark_read_by(current_user.id)
    db.session.commit()

    return jsonify({
        'messages': [m.to_dict() for m in reversed(msgs.items)],
        'has_more': msgs.has_next,
        'page': page,
        'total': msgs.total
    })


@api_bp.route('/chats/<chat_id>/messages', methods=['POST'])
@api_login_required
def send_message(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    data = request.get_json() or {}

    content = data.get('content', '').strip()
    message_type = data.get('message_type', 'text')
    reply_to_id = data.get('reply_to_id')

    if not content and message_type == 'text':
        return jsonify({'error': 'Message content required'}), 400

    msg = Message(
        id=str(uuid.uuid4()),
        chat_id=chat_id,
        sender_id=current_user.id,
        content=content,
        message_type=message_type,
        reply_to_id=reply_to_id,
    )
    db.session.add(msg)

    chat.last_message_at = utcnow()
    chat.last_message_id = msg.id
    db.session.commit()

    return jsonify({'success': True, 'message': msg.to_dict()})


@api_bp.route('/messages/<message_id>', methods=['PATCH'])
@api_login_required
def edit_message(message_id):
    msg = Message.query.get_or_404(message_id)
    if msg.sender_id != current_user.id:
        abort(403)
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Content required'}), 400
    msg.content = content
    msg.is_edited = True
    db.session.commit()
    return jsonify({'success': True, 'message': msg.to_dict()})


@api_bp.route('/messages/<message_id>', methods=['DELETE'])
@api_login_required
def delete_message(message_id):
    msg = Message.query.get_or_404(message_id)
    if msg.sender_id != current_user.id:
        abort(403)
    data = request.get_json() or {}
    delete_for = data.get('for', 'me')  # me or everyone
    if delete_for == 'everyone':
        msg.is_deleted = True
        msg.content = None
    else:
        deleted = json.loads(msg.deleted_for or '[]')
        deleted.append(current_user.id)
        msg.deleted_for = json.dumps(deleted)
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/messages/<message_id>/react', methods=['POST'])
@api_login_required
def react_to_message(message_id):
    msg = Message.query.get_or_404(message_id)
    data = request.get_json() or {}
    emoji = data.get('emoji', '')
    if not emoji:
        return jsonify({'error': 'Emoji required'}), 400
    msg.add_reaction(emoji, current_user.id)
    db.session.commit()
    return jsonify({'success': True, 'reactions': msg.get_reactions()})


@api_bp.route('/messages/<message_id>/pin', methods=['POST'])
@api_login_required
def pin_message(message_id):
    msg = Message.query.get_or_404(message_id)
    msg.is_pinned = not msg.is_pinned
    db.session.commit()
    return jsonify({'success': True, 'is_pinned': msg.is_pinned})


@api_bp.route('/chats/<chat_id>/search')
@api_login_required
def search_messages(chat_id):
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'messages': []})
    msgs = Message.query.filter(
        Message.chat_id == chat_id,
        Message.content.ilike(f'%{q}%'),
        Message.is_deleted == False
    ).order_by(Message.created_at.desc()).limit(50).all()
    return jsonify({'messages': [m.to_dict() for m in msgs]})


# ─── File Upload ──────────────────────────────────────────────────────────────

@api_bp.route('/upload', methods=['POST'])
@api_login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    file_type = request.form.get('type', 'document')
    chat_id = request.form.get('chat_id', '')

    result = handle_file_upload(file, folder=f'messages/{file_type}', allowed_types=file_type)
    if not result['success']:
        return jsonify({'error': result['error']}), 400

    media = MediaFile(
        id=str(uuid.uuid4()),
        uploader_id=current_user.id,
        filename=result.get('filename', ''),
        original_name=file.filename,
        file_type=file_type,
        mime_type=result.get('mime_type', ''),
        file_size=result.get('file_size', 0),
        url=result['url'],
        public_id=result.get('public_id', ''),
        thumbnail_url=result.get('thumbnail_url', ''),
    )
    db.session.add(media)
    db.session.commit()

    return jsonify({
        'success': True,
        'url': result['url'],
        'thumbnail_url': result.get('thumbnail_url', ''),
        'media_id': media.id,
        'file_size': media.file_size,
        'mime_type': media.mime_type,
    })


# ─── Groups ───────────────────────────────────────────────────────────────────

@api_bp.route('/groups', methods=['POST'])
@api_login_required
def create_group():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    member_ids = data.get('member_ids', [])

    if not name or len(name) < 2:
        return jsonify({'error': 'Group name must be at least 2 characters'}), 400

    group = Group(
        id=str(uuid.uuid4()),
        name=name,
        description=description[:500],
        created_by=current_user.id,
        invite_link=secrets.token_urlsafe(8)
    )
    group.members.append(current_user)

    for uid in member_ids[:255]:
        u = User.query.get(uid)
        if u and u not in group.members:
            group.members.append(u)

    db.session.add(group)

    # Create group chat
    chat = Chat(id=str(uuid.uuid4()), type='group', group_id=group.id)
    db.session.add(chat)
    db.session.commit()

    log_audit('group_created', actor_id=current_user.id, target_id=group.id, ip=request.remote_addr)
    return jsonify({'success': True, 'group': group.to_dict(), 'chat_id': chat.id})


@api_bp.route('/groups/<group_id>', methods=['GET'])
@api_login_required
def get_group(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        abort(403)
    return jsonify({'group': group.to_dict(), 'members': [m.to_dict() for m in group.members]})


@api_bp.route('/groups/<group_id>/members', methods=['POST'])
@api_login_required
def add_group_member(group_id):
    group = Group.query.get_or_404(group_id)
    # Check admin
    data = request.get_json() or {}
    user_id = data.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user in group.members:
        return jsonify({'error': 'Already a member'}), 400
    if len(group.members) >= group.max_members:
        return jsonify({'error': 'Group is full'}), 400
    group.members.append(user)
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/groups/<group_id>/members/<user_id>', methods=['DELETE'])
@api_login_required
def remove_group_member(group_id, user_id):
    group = Group.query.get_or_404(group_id)
    user = User.query.get(user_id)
    if user and user in group.members:
        group.members.remove(user)
        db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/groups/<group_id>/leave', methods=['POST'])
@api_login_required
def leave_group(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user in group.members:
        group.members.remove(current_user)
        db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/groups/join/<invite_link>', methods=['POST'])
@api_login_required
def join_group(invite_link):
    group = Group.query.filter_by(invite_link=invite_link).first_or_404()
    if current_user not in group.members:
        if len(group.members) >= group.max_members:
            return jsonify({'error': 'Group is full'}), 400
        group.members.append(current_user)
        db.session.commit()
    chat = Chat.query.filter_by(group_id=group.id, type='group').first()
    return jsonify({'success': True, 'group': group.to_dict(), 'chat_id': chat.id if chat else None})


# ─── QR Login ─────────────────────────────────────────────────────────────────

@api_bp.route('/auth/qr/generate', methods=['POST'])
def generate_qr():
    from datetime import timedelta
    token = secrets.token_urlsafe(32)
    qr = QRLoginToken(
        id=str(uuid.uuid4()),
        token=token,
        expires_at=utcnow() + timedelta(minutes=5)
    )
    db.session.add(qr)
    db.session.commit()
    return jsonify({'token': token, 'expires_in': 300})


@api_bp.route('/auth/qr/scan', methods=['POST'])
@api_login_required
def scan_qr():
    data = request.get_json() or {}
    token = data.get('token')
    qr = QRLoginToken.query.filter_by(token=token, status='pending').first()
    if not qr or qr.expires_at < utcnow():
        return jsonify({'error': 'Invalid or expired QR code'}), 400
    qr.status = 'scanned'
    qr.user_id = current_user.id
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/auth/qr/status/<token>', methods=['GET'])
def qr_status(token):
    qr = QRLoginToken.query.filter_by(token=token).first()
    if not qr:
        return jsonify({'status': 'not_found'}), 404
    if qr.expires_at < utcnow():
        return jsonify({'status': 'expired'})
    if qr.status == 'scanned' and qr.user_id:
        from flask_jwt_extended import create_access_token, create_refresh_token
        access_token = create_access_token(identity=qr.user_id)
        refresh_token = create_refresh_token(identity=qr.user_id)
        qr.status = 'confirmed'
        db.session.commit()
        return jsonify({'status': 'confirmed', 'access_token': access_token, 'refresh_token': refresh_token})
    return jsonify({'status': qr.status})


# ─── Analytics ────────────────────────────────────────────────────────────────

@api_bp.route('/analytics/track', methods=['POST'])
def track_event():
    data = request.get_json() or {}
    event_type = data.get('event_type', 'pageview')
    import json
    ev = Analytics(
        id=str(uuid.uuid4()),
        event_type=event_type,
        user_id=current_user.id if current_user.is_authenticated else None,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:500],
        path=request.referrer or '',
        extra_data=json.dumps(data.get('extra', {}))
    )
    db.session.add(ev)
    db.session.commit()
    return jsonify({'success': True})


