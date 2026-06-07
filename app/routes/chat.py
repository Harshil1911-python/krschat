# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Chat Routes
WhatsApp-style chat interface
"""
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user

from ..models import db, User, Chat, Message, Group, SiteSettings

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/')
@chat_bp.route('/index')
@login_required
def index():
    if current_user.is_banned:
        return render_template('errors/banned.html', reason=current_user.ban_reason)
    prefs = current_user.get_preferences()
    return render_template('chat/index.html', user=current_user, prefs=prefs)


@chat_bp.route('/c/<chat_id>')
@login_required
def open_chat(chat_id):
    if current_user.is_banned:
        return render_template('errors/banned.html', reason=current_user.ban_reason)
    prefs = current_user.get_preferences()
    return render_template('chat/index.html', user=current_user,
                           active_chat_id=chat_id, prefs=prefs)


@chat_bp.route('/g/<group_id>')
@login_required
def open_group(group_id):
    if current_user.is_banned:
        return render_template('errors/banned.html', reason=current_user.ban_reason)
    prefs = current_user.get_preferences()
    return render_template('chat/index.html', user=current_user,
                           active_group_id=group_id, prefs=prefs)
