"""
KHANDHARS CHAT - WebSocket / SocketIO Events
Real-time messaging, typing indicators, online status, and more
"""
import uuid
from datetime import datetime, timezone
from flask import request
from flask_socketio import emit, join_room, leave_room, disconnect
from flask_login import current_user

from ..models import db, User, Chat, Message, Group


def utcnow():
    return datetime.now(timezone.utc)


def register_socket_events(socketio):

    @socketio.on('connect')
    def on_connect(auth=None):
        if not current_user.is_authenticated:
            disconnect()
            return False

        current_user.is_online = True
        current_user.last_seen = utcnow()
        db.session.commit()

        # Join personal room
        join_room(f'user_{current_user.id}')

        # Join group rooms
        for group in current_user.groups:
            join_room(f'group_{group.id}')

        # Notify contacts user is online
        emit('user_online', {
            'user_id': current_user.id,
            'is_online': True,
            'timestamp': utcnow().isoformat()
        }, broadcast=True, include_self=False)

        emit('connected', {'status': 'connected', 'user_id': current_user.id})

    @socketio.on('disconnect')
    def on_disconnect():
        if current_user.is_authenticated:
            current_user.is_online = False
            current_user.last_seen = utcnow()
            db.session.commit()

            emit('user_offline', {
                'user_id': current_user.id,
                'last_seen': utcnow().isoformat()
            }, broadcast=True, include_self=False)

    @socketio.on('join_chat')
    def on_join_chat(data):
        if not current_user.is_authenticated:
            return
        chat_id = data.get('chat_id')
        if chat_id:
            join_room(f'chat_{chat_id}')

    @socketio.on('leave_chat')
    def on_leave_chat(data):
        if not current_user.is_authenticated:
            return
        chat_id = data.get('chat_id')
        if chat_id:
            leave_room(f'chat_{chat_id}')

    @socketio.on('send_message')
    def on_send_message(data):
        if not current_user.is_authenticated:
            return

        chat_id = data.get('chat_id')
        content = data.get('content', '').strip()
        message_type = data.get('type', 'text')
        reply_to_id = data.get('reply_to_id')
        media_url = data.get('media_url')
        media_type = data.get('media_type')
        media_name = data.get('media_name')
        media_size = data.get('media_size')

        if not chat_id:
            return

        chat = Chat.query.get(chat_id)
        if not chat:
            return

        # Validate access
        if chat.type == 'direct':
            if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
                return
        elif chat.type == 'group':
            group = Group.query.get(chat.group_id)
            if not group or current_user not in group.members:
                return
            if group.only_admins_can_send:
                # Check if user is admin
                pass

        msg = Message(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            sender_id=current_user.id,
            content=content if message_type == 'text' else None,
            message_type=message_type,
            media_url=media_url,
            media_type=media_type,
            media_name=media_name,
            media_size=media_size,
            reply_to_id=reply_to_id,
        )
        db.session.add(msg)
        chat.last_message_at = utcnow()
        chat.last_message_id = msg.id
        db.session.commit()

        msg_data = msg.to_dict()
        msg_data['sender'] = current_user.to_dict()

        # Emit to chat room
        emit('new_message', msg_data, room=f'chat_{chat_id}')

        # Notify offline users via personal room
        if chat.type == 'direct':
            other_id = chat.user2_id if chat.user1_id == current_user.id else chat.user1_id
            emit('chat_notification', {
                'chat_id': chat_id,
                'message': msg_data,
                'sender': current_user.to_dict()
            }, room=f'user_{other_id}')
        elif chat.type == 'group':
            group = Group.query.get(chat.group_id)
            if group:
                for member in group.members:
                    if member.id != current_user.id:
                        emit('chat_notification', {
                            'chat_id': chat_id,
                            'group_id': chat.group_id,
                            'message': msg_data,
                            'sender': current_user.to_dict()
                        }, room=f'user_{member.id}')

    @socketio.on('typing_start')
    def on_typing_start(data):
        if not current_user.is_authenticated:
            return
        chat_id = data.get('chat_id')
        if chat_id:
            emit('user_typing', {
                'chat_id': chat_id,
                'user_id': current_user.id,
                'display_name': current_user.display_name,
                'is_typing': True
            }, room=f'chat_{chat_id}', include_self=False)

    @socketio.on('typing_stop')
    def on_typing_stop(data):
        if not current_user.is_authenticated:
            return
        chat_id = data.get('chat_id')
        if chat_id:
            emit('user_typing', {
                'chat_id': chat_id,
                'user_id': current_user.id,
                'is_typing': False
            }, room=f'chat_{chat_id}', include_self=False)

    @socketio.on('message_read')
    def on_message_read(data):
        if not current_user.is_authenticated:
            return
        message_id = data.get('message_id')
        chat_id = data.get('chat_id')
        if message_id:
            msg = Message.query.get(message_id)
            if msg and msg.sender_id != current_user.id:
                msg.mark_read_by(current_user.id)
                db.session.commit()
                emit('message_read_receipt', {
                    'message_id': message_id,
                    'chat_id': chat_id,
                    'read_by': current_user.id,
                    'read_at': utcnow().isoformat()
                }, room=f'user_{msg.sender_id}')

    @socketio.on('message_react')
    def on_message_react(data):
        if not current_user.is_authenticated:
            return
        message_id = data.get('message_id')
        emoji = data.get('emoji', '')
        chat_id = data.get('chat_id')

        if not message_id or not emoji:
            return

        msg = Message.query.get(message_id)
        if not msg:
            return

        # Toggle reaction
        reactions = msg.get_reactions()
        if emoji in reactions and current_user.id in reactions[emoji]:
            msg.remove_reaction(emoji, current_user.id)
        else:
            msg.add_reaction(emoji, current_user.id)
        db.session.commit()

        emit('message_reaction_update', {
            'message_id': message_id,
            'chat_id': chat_id,
            'reactions': msg.get_reactions()
        }, room=f'chat_{chat_id}')

    @socketio.on('message_delete')
    def on_message_delete(data):
        if not current_user.is_authenticated:
            return
        message_id = data.get('message_id')
        chat_id = data.get('chat_id')
        delete_for = data.get('for', 'everyone')

        msg = Message.query.get(message_id)
        if not msg or msg.sender_id != current_user.id:
            return

        if delete_for == 'everyone':
            msg.is_deleted = True
            msg.content = None
        db.session.commit()

        emit('message_deleted', {
            'message_id': message_id,
            'chat_id': chat_id,
            'deleted_for_everyone': delete_for == 'everyone'
        }, room=f'chat_{chat_id}')

    @socketio.on('message_edit')
    def on_message_edit(data):
        if not current_user.is_authenticated:
            return
        message_id = data.get('message_id')
        new_content = data.get('content', '').strip()
        chat_id = data.get('chat_id')

        if not message_id or not new_content:
            return

        msg = Message.query.get(message_id)
        if not msg or msg.sender_id != current_user.id:
            return

        msg.content = new_content
        msg.is_edited = True
        db.session.commit()

        emit('message_edited', {
            'message_id': message_id,
            'chat_id': chat_id,
            'content': new_content,
            'edited_at': utcnow().isoformat()
        }, room=f'chat_{chat_id}')

    @socketio.on('voice_call_offer')
    def on_voice_call_offer(data):
        """Voice call architecture - forward WebRTC offer."""
        if not current_user.is_authenticated:
            return
        target_user_id = data.get('target_user_id')
        offer = data.get('offer')
        if target_user_id and offer:
            emit('incoming_voice_call', {
                'caller_id': current_user.id,
                'caller': current_user.to_dict(),
                'offer': offer,
                'call_id': data.get('call_id', str(uuid.uuid4()))
            }, room=f'user_{target_user_id}')

    @socketio.on('voice_call_answer')
    def on_voice_call_answer(data):
        if not current_user.is_authenticated:
            return
        caller_id = data.get('caller_id')
        answer = data.get('answer')
        if caller_id and answer:
            emit('voice_call_answered', {
                'answerer_id': current_user.id,
                'answer': answer,
                'call_id': data.get('call_id')
            }, room=f'user_{caller_id}')

    @socketio.on('voice_call_reject')
    def on_voice_call_reject(data):
        if not current_user.is_authenticated:
            return
        caller_id = data.get('caller_id')
        if caller_id:
            emit('voice_call_rejected', {
                'rejected_by': current_user.id,
                'call_id': data.get('call_id')
            }, room=f'user_{caller_id}')

    @socketio.on('ice_candidate')
    def on_ice_candidate(data):
        """Forward WebRTC ICE candidate."""
        if not current_user.is_authenticated:
            return
        target_id = data.get('target_id')
        candidate = data.get('candidate')
        if target_id and candidate:
            emit('ice_candidate', {
                'from_id': current_user.id,
                'candidate': candidate,
                'call_id': data.get('call_id')
            }, room=f'user_{target_id}')

    @socketio.on('video_call_offer')
    def on_video_call_offer(data):
        """Video call architecture."""
        if not current_user.is_authenticated:
            return
        target_user_id = data.get('target_user_id')
        offer = data.get('offer')
        if target_user_id and offer:
            emit('incoming_video_call', {
                'caller_id': current_user.id,
                'caller': current_user.to_dict(),
                'offer': offer,
                'call_id': data.get('call_id', str(uuid.uuid4()))
            }, room=f'user_{target_user_id}')

    return socketio
