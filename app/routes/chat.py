"""
KHANDHARS CHAT - Chat Routes
Main chat interface
"""
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, abort
from flask_login import login_required, current_user

from ..models import db, User, Chat, Message, Group, SiteSettings

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/')
@chat_bp.route('/index')
@login_required
def index():
    """Main chat interface."""
    if current_user.is_banned:
        return render_template('errors/banned.html', reason=current_user.ban_reason)
    return render_template('chat/index.html', user=current_user)


@chat_bp.route('/c/<chat_id>')
@login_required
def open_chat(chat_id):
    """Open a specific chat."""
    chat = Chat.query.get_or_404(chat_id)
    if chat.type == 'direct':
        if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
            abort(403)
    return render_template('chat/index.html', user=current_user, active_chat_id=chat_id)


@chat_bp.route('/g/<group_id>')
@login_required
def open_group(group_id):
    """Open a group chat."""
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        abort(403)
    return render_template('chat/index.html', user=current_user, active_group_id=group_id)
