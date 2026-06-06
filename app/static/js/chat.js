/**
 * KHANDHARS CHAT - Chat JavaScript
 * Full-featured real-time chat client
 */

'use strict';

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  socket: null,
  currentChatId: null,
  currentChatType: null,
  currentChatData: null,
  chats: [],
  messages: {},
  typingTimers: {},
  isTyping: false,
  replyTo: null,
  selectedGroupMembers: [],
  contextMenuTarget: null,
  mediaRecorder: null,
  recordingInterval: null,
  recordingSeconds: 0,
  activePage: 'all',
  unreadCounts: {},
};

// ─── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSocket();
  loadChats();
  if (window.OPEN_CHAT_ID) openChat(window.OPEN_CHAT_ID);

  // Close dropdowns on outside click
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown')) closeAllDropdowns();
    if (!e.target.closest('#contextMenu') && !e.target.closest('.message-bubble')) {
      document.getElementById('contextMenu').classList.remove('open');
    }
    if (!e.target.closest('#emojiPanel') && !e.target.closest('.emoji-picker-btn')) {
      document.getElementById('emojiPanel').classList.add('hidden');
    }
    if (!e.target.closest('#attachMenu') && !e.target.closest('.attach-btn')) {
      document.getElementById('attachMenu').classList.add('hidden');
    }
  });
});

// ─── Socket ────────────────────────────────────────────────────────────────────
function initSocket() {
  state.socket = io({ transports: ['websocket', 'polling'] });

  state.socket.on('connect', () => {
    console.log('🔌 Connected');
  });

  state.socket.on('new_message', (msg) => {
    if (msg.chat_id === state.currentChatId) {
      appendMessage(msg);
      scrollToBottom();
      markRead(msg.id, msg.chat_id);
    }
    updateChatListPreview(msg);
  });

  state.socket.on('user_typing', (data) => {
    if (data.chat_id === state.currentChatId) {
      if (data.user_id !== CURRENT_USER.id) {
        if (data.is_typing) {
          showTyping(data.display_name || 'Someone');
        } else {
          hideTyping();
        }
      }
    }
  });

  state.socket.on('user_online', (data) => {
    updateUserOnlineStatus(data.user_id, true);
  });

  state.socket.on('user_offline', (data) => {
    updateUserOnlineStatus(data.user_id, false, data.last_seen);
  });

  state.socket.on('message_read_receipt', (data) => {
    updateReadReceipt(data.message_id, data.read_by, data.read_at);
  });

  state.socket.on('message_reaction_update', (data) => {
    if (data.chat_id === state.currentChatId) {
      updateMessageReactions(data.message_id, data.reactions);
    }
  });

  state.socket.on('message_deleted', (data) => {
    if (data.chat_id === state.currentChatId) {
      markMessageDeleted(data.message_id, data.deleted_for_everyone);
    }
  });

  state.socket.on('message_edited', (data) => {
    if (data.chat_id === state.currentChatId) {
      updateMessageContent(data.message_id, data.content);
    }
  });

  state.socket.on('incoming_voice_call', showIncomingCall);
  state.socket.on('voice_call_answered', handleCallAnswered);
  state.socket.on('voice_call_rejected', handleCallRejected);
  state.socket.on('ice_candidate', handleIceCandidate);

  state.socket.on('chat_notification', (data) => {
    if (data.chat_id !== state.currentChatId) {
      showNotification(data);
      incrementUnread(data.chat_id);
    }
  });

  state.socket.on('disconnect', () => {
    console.log('🔌 Disconnected');
  });
}

// ─── Load Chats ────────────────────────────────────────────────────────────────
async function loadChats() {
  try {
    const res = await api('GET', '/api/v1/chats');
    state.chats = res.chats || [];
    renderChatList(state.chats);
    // Join socket rooms
    state.chats.forEach(c => {
      state.socket.emit('join_chat', { chat_id: c.id });
    });
  } catch (e) {
    console.error('Load chats error:', e);
  }
}

function renderChatList(chats) {
  const container = document.getElementById('chatList');
  const tab = state.activePage;

  let filtered = chats.filter(c => {
    if (tab === 'groups') return c.type === 'group';
    if (tab === 'archived') return c.is_archived;
    return !c.is_archived;
  });

  const search = document.getElementById('searchInput').value.toLowerCase();
  if (search) {
    filtered = filtered.filter(c => {
      const name = c.type === 'group' ? c.group?.name : c.other_user?.display_name;
      return name?.toLowerCase().includes(search);
    });
  }

  if (filtered.length === 0) {
    container.innerHTML = `<div style="padding:24px;text-align:center;color:var(--text-3);font-size:0.88rem;">
      ${tab === 'archived' ? '📥 No archived chats' : tab === 'groups' ? '👥 No groups yet' : '💬 No conversations yet'}
    </div>`;
    return;
  }

  container.innerHTML = filtered.map(chat => renderChatItem(chat)).join('');
}

function renderChatItem(chat) {
  const isGroup = chat.type === 'group';
  const name = isGroup ? chat.group?.name : chat.other_user?.display_name;
  const avatar = isGroup ? (chat.group?.avatar_url || '/static/images/default-group.png') : (chat.other_user?.avatar_url || '/static/images/default-avatar.png');
  const lastMsg = chat.last_message;
  const preview = lastMsg ? (lastMsg.is_deleted ? '🗑️ Deleted message' : (lastMsg.message_type !== 'text' ? `📎 ${lastMsg.message_type}` : lastMsg.content || '')) : 'No messages yet';
  const time = lastMsg ? formatTime(lastMsg.created_at) : '';
  const unread = chat.unread_count || 0;
  const isOnline = !isGroup && chat.other_user?.is_online;
  const isActive = chat.id === state.currentChatId;

  return `<div class="chat-item ${isActive ? 'active' : ''}" onclick="openChat('${chat.id}')" id="chatItem_${chat.id}">
    <div class="avatar-wrap">
      <img src="${escapeHtml(avatar)}" class="avatar avatar-md" />
      ${isOnline ? '<div class="online-dot"></div>' : ''}
    </div>
    <div class="chat-item-info">
      <div class="chat-item-top">
        <div class="chat-item-name truncate">${escapeHtml(name || 'Unknown')}</div>
        <div class="chat-item-time">${time}</div>
      </div>
      <div class="chat-item-bottom">
        <div class="chat-item-preview ${unread > 0 ? 'unread' : ''} truncate">${escapeHtml(preview)}</div>
        ${unread > 0 ? `<div class="badge-count">${unread > 99 ? '99+' : unread}</div>` : ''}
      </div>
    </div>
  </div>`;
}

function updateChatListPreview(msg) {
  const chatItem = document.getElementById(`chatItem_${msg.chat_id}`);
  if (chatItem) {
    const preview = chatItem.querySelector('.chat-item-preview');
    const time = chatItem.querySelector('.chat-item-time');
    if (preview) preview.textContent = msg.content || `📎 ${msg.message_type}`;
    if (time) time.textContent = formatTime(msg.created_at);
  }
  // Move chat to top
  const chat = state.chats.find(c => c.id === msg.chat_id);
  if (chat) {
    state.chats = [chat, ...state.chats.filter(c => c.id !== msg.chat_id)];
    renderChatList(state.chats);
  }
}

// ─── Open Chat ─────────────────────────────────────────────────────────────────
async function openChat(chatId) {
  if (!chatId) return;

  state.currentChatId = chatId;
  const chat = state.chats.find(c => c.id === chatId);
  state.currentChatData = chat;

  // Update active state
  document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
  const activeItem = document.getElementById(`chatItem_${chatId}`);
  if (activeItem) activeItem.classList.add('active');

  // Show chat window
  document.getElementById('welcomeScreen').classList.add('hidden');
  const chatWindow = document.getElementById('chatWindow');
  chatWindow.classList.remove('hidden');
  chatWindow.style.display = 'flex';

  // Update header
  if (chat) {
    const isGroup = chat.type === 'group';
    const name = isGroup ? chat.group?.name : chat.other_user?.display_name;
    const avatar = isGroup ? (chat.group?.avatar_url || '/static/images/default-group.png') : (chat.other_user?.avatar_url || '/static/images/default-avatar.png');
    const isOnline = !isGroup && chat.other_user?.is_online;

    document.getElementById('headerAvatar').src = avatar;
    document.getElementById('chatHeaderName').textContent = name || 'Chat';
    document.getElementById('chatHeaderStatus').textContent = isGroup ? `${chat.group?.member_count || 0} members` : (isOnline ? '● Online' : 'Offline');
    document.getElementById('chatHeaderStatus').className = `chat-header-status ${isOnline ? '' : 'offline'}`;

    const onlineDot = document.getElementById('headerOnlineDot');
    onlineDot.style.display = isOnline ? 'block' : 'none';

    // Update info panel
    document.getElementById('infoPanelAvatar').src = avatar;
    document.getElementById('infoPanelName').textContent = name || '';
    document.getElementById('infoPanelStatus').textContent = isOnline ? '● Online' : 'Last seen recently';

    state.currentChatType = isGroup ? 'group' : 'direct';
  }

  // Join chat room
  state.socket.emit('join_chat', { chat_id: chatId });

  // Mobile: show main, back btn
  if (window.innerWidth <= 768) {
    document.getElementById('chatSidebar').classList.remove('open');
    document.getElementById('backBtn').style.display = 'flex';
  }

  // Clear unread
  clearUnread(chatId);

  // Load messages
  await loadMessages(chatId);
}

// ─── Load Messages ─────────────────────────────────────────────────────────────
async function loadMessages(chatId, page = 1) {
  const container = document.getElementById('messagesContainer');
  if (page === 1) {
    container.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-3);">
      <div class="spinner" style="margin:0 auto 10px;"></div>Loading...
    </div>`;
  }

  try {
    const res = await api('GET', `/api/v1/chats/${chatId}/messages?page=${page}&per_page=50`);
    const messages = res.messages || [];

    if (page === 1) {
      container.innerHTML = '';
      if (messages.length === 0) {
        container.innerHTML = `<div class="chat-empty"><div class="chat-empty-icon">💬</div><h3>No messages yet</h3><p>Say hello to start the conversation!</p></div>`;
        return;
      }
    }

    // Add load more button
    if (res.has_more && page === 1) {
      container.innerHTML = `<div style="text-align:center;padding:10px;">
        <button class="btn btn-ghost btn-sm" onclick="loadMessages('${chatId}', ${page + 1})">Load earlier messages</button>
      </div>`;
    }

    // Group messages by sender
    let lastSenderId = null;
    messages.forEach((msg, i) => {
      const showAvatar = msg.sender_id !== lastSenderId;
      appendMessage(msg, false, !showAvatar);
      lastSenderId = msg.sender_id;
    });

    scrollToBottom(page === 1 ? 'instant' : 'smooth');
    state.messages[chatId] = messages;
  } catch (e) {
    console.error('Load messages error:', e);
    container.innerHTML = `<div style="text-align:center;padding:20px;color:var(--danger);">Failed to load messages. <button class="btn btn-ghost btn-sm" onclick="loadMessages('${chatId}')">Retry</button></div>`;
  }
}

// ─── Render Message ────────────────────────────────────────────────────────────
function appendMessage(msg, animate = true, hideAvatar = false) {
  const container = document.getElementById('messagesContainer');
  const isOwn = msg.sender_id === CURRENT_USER.id;
  const sender = msg.sender || {};
  const reactions = typeof msg.reactions === 'object' ? msg.reactions : {};

  let content = '';
  if (msg.is_deleted) {
    content = `<div class="message-deleted">🗑️ This message was deleted</div>`;
  } else if (msg.message_type === 'text') {
    content = `<div>${escapeHtml(msg.content || '')}</div>`;
  } else if (msg.message_type === 'image') {
    content = `<div class="message-media"><img src="${escapeHtml(msg.media_url || '')}" onclick="openMedia('${escapeHtml(msg.media_url || '')}', 'image')" loading="lazy" /></div>`;
  } else if (msg.message_type === 'video') {
    content = `<div class="message-media"><video src="${escapeHtml(msg.media_url || '')}" controls preload="metadata"></video></div>`;
  } else if (msg.message_type === 'audio' || msg.message_type === 'voice') {
    content = `<div class="message-media"><audio src="${escapeHtml(msg.media_url || '')}" controls style="max-width:250px;"></audio></div>`;
  } else if (msg.message_type === 'document') {
    content = `<div class="message-media"><div class="doc-preview">
      <span style="font-size:1.5rem;">📄</span>
      <div><div style="font-size:0.85rem;font-weight:600;">${escapeHtml(msg.media_name || 'Document')}</div>
      <div style="font-size:0.75rem;color:var(--text-3);">${msg.media_size ? formatBytes(msg.media_size) : ''}</div></div>
      <a href="${escapeHtml(msg.media_url || '')}" download class="btn btn-ghost btn-sm" style="margin-left:auto;">⬇️</a>
    </div></div>`;
  }

  // Reply preview
  let replyHtml = '';
  if (msg.reply_to_id) {
    replyHtml = `<div class="message-reply-preview">↩️ Replying to a message</div>`;
  }

  // Reactions
  let reactionsHtml = '';
  const reactionEntries = Object.entries(reactions);
  if (reactionEntries.length > 0) {
    reactionsHtml = `<div class="message-reactions">
      ${reactionEntries.map(([emoji, users]) =>
        `<button class="reaction-chip ${users.includes(CURRENT_USER.id) ? 'mine' : ''}" onclick="toggleReaction('${msg.id}','${emoji}')" title="${users.length} reaction(s)">
          ${emoji} <span>${users.length}</span>
        </button>`
      ).join('')}
    </div>`;
  }

  const el = document.createElement('div');
  el.className = `message-row ${isOwn ? 'own' : ''} ${animate ? 'animate-slideIn' : ''}`;
  el.id = `msg_${msg.id}`;
  el.setAttribute('data-msg-id', msg.id);
  el.setAttribute('data-sender-id', msg.sender_id);

  el.innerHTML = `
    ${!isOwn && !hideAvatar ? `<div class="avatar-wrap"><img src="${escapeHtml(sender.avatar_url || '/static/images/default-avatar.png')}" class="avatar avatar-sm" /></div>` : (!isOwn ? '<div style="width:36px;flex-shrink:0;"></div>' : '')}
    <div style="display:flex;flex-direction:column;${isOwn ? 'align-items:flex-end;' : ''}">
      ${!isOwn && !hideAvatar ? `<div style="font-size:0.75rem;font-weight:600;color:var(--primary-light);margin-bottom:2px;">${escapeHtml(sender.display_name || '')}</div>` : ''}
      ${replyHtml}
      <div class="message-bubble" oncontextmenu="showContextMenu(event,'${msg.id}',${isOwn})">
        ${content}
        ${msg.is_edited ? '<span class="message-edited">(edited)</span>' : ''}
      </div>
      ${reactionsHtml}
      <div class="message-time">
        ${formatTime(msg.created_at)}
        ${isOwn ? `<svg class="read-icon" viewBox="0 0 24 24" fill="none" stroke="${msg.read_by && msg.read_by.length > 0 ? 'var(--primary-light)' : 'var(--text-muted)'}" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>` : ''}
      </div>
    </div>
  `;

  // Remove empty state if present
  const empty = container.querySelector('.chat-empty');
  if (empty) empty.remove();

  container.appendChild(el);
}

// ─── Send Message ──────────────────────────────────────────────────────────────
function sendMessage() {
  const input = document.getElementById('messageInput');
  const content = input.value.trim();
  if (!content || !state.currentChatId) return;

  const msg = {
    chat_id: state.currentChatId,
    content: content,
    type: 'text',
    reply_to_id: state.replyTo?.id || null,
  };

  state.socket.emit('send_message', msg);
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('sendBtn').disabled = true;
  cancelReply();
  stopTyping();
}

// ─── Input Handling ────────────────────────────────────────────────────────────
function handleInputKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function handleInputChange(el) {
  // Auto-resize
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';

  // Enable/disable send button
  document.getElementById('sendBtn').disabled = !el.value.trim();

  // Typing indicator
  if (!state.isTyping && el.value.trim()) {
    state.isTyping = true;
    state.socket.emit('typing_start', { chat_id: state.currentChatId });
  }

  clearTimeout(state.typingTimer);
  state.typingTimer = setTimeout(stopTyping, 2000);
}

function stopTyping() {
  if (state.isTyping) {
    state.isTyping = false;
    state.socket.emit('typing_stop', { chat_id: state.currentChatId });
  }
}

// ─── Typing Indicator ─────────────────────────────────────────────────────────
function showTyping(name) {
  document.getElementById('typingName').textContent = `${name} is typing`;
  document.getElementById('typingIndicator').classList.remove('hidden');
  clearTimeout(state.typingHideTimer);
  state.typingHideTimer = setTimeout(hideTyping, 3000);
}

function hideTyping() {
  document.getElementById('typingIndicator').classList.add('hidden');
}

// ─── Reply ─────────────────────────────────────────────────────────────────────
function replyTo(msgId, authorName, content) {
  state.replyTo = { id: msgId, author: authorName, content };
  document.getElementById('replyAuthor').textContent = authorName;
  document.getElementById('replyContent').textContent = content;
  document.getElementById('replyPreview').classList.remove('hidden');
  document.getElementById('messageInput').focus();
}

function cancelReply() {
  state.replyTo = null;
  document.getElementById('replyPreview').classList.add('hidden');
}

// ─── Context Menu ──────────────────────────────────────────────────────────────
let contextMsgId = null;
let contextIsOwn = false;

function showContextMenu(e, msgId, isOwn) {
  e.preventDefault();
  contextMsgId = msgId;
  contextIsOwn = isOwn;

  const menu = document.getElementById('contextMenu');
  menu.classList.add('open');
  menu.style.left = Math.min(e.clientX, window.innerWidth - 180) + 'px';
  menu.style.top = Math.min(e.clientY, window.innerHeight - 250) + 'px';

  document.getElementById('editMessageBtn').style.display = isOwn ? 'flex' : 'none';
}

function replyToMessage() {
  if (!contextMsgId) return;
  const msgEl = document.getElementById(`msg_${contextMsgId}`);
  if (msgEl) {
    const content = msgEl.querySelector('.message-bubble')?.innerText?.trim() || '';
    const senderId = msgEl.getAttribute('data-sender-id');
    const authorName = senderId === CURRENT_USER.id ? 'You' : 'Someone';
    replyTo(contextMsgId, authorName, content);
  }
  document.getElementById('contextMenu').classList.remove('open');
}

function copyMessage() {
  const msgEl = document.getElementById(`msg_${contextMsgId}`);
  if (msgEl) {
    const content = msgEl.querySelector('.message-bubble')?.innerText?.trim() || '';
    navigator.clipboard.writeText(content);
    showToast('Copied to clipboard', 'success');
  }
  document.getElementById('contextMenu').classList.remove('open');
}

function deleteMessage() {
  if (!contextMsgId) return;
  if (!confirm('Delete this message?')) return;
  state.socket.emit('message_delete', {
    message_id: contextMsgId,
    chat_id: state.currentChatId,
    for: contextIsOwn ? 'everyone' : 'me'
  });
  document.getElementById('contextMenu').classList.remove('open');
}

function editMessage() {
  if (!contextMsgId || !contextIsOwn) return;
  const msgEl = document.getElementById(`msg_${contextMsgId}`);
  if (msgEl) {
    const bubble = msgEl.querySelector('.message-bubble div');
    const content = bubble?.textContent?.trim() || '';
    const input = document.getElementById('messageInput');
    input.value = content;
    input.focus();
    document.getElementById('sendBtn').disabled = false;
    // Switch send to update
    document.getElementById('sendBtn').setAttribute('data-edit-id', contextMsgId);
    document.getElementById('sendBtn').onclick = () => submitEdit(contextMsgId);
  }
  document.getElementById('contextMenu').classList.remove('open');
}

function submitEdit(msgId) {
  const input = document.getElementById('messageInput');
  const content = input.value.trim();
  if (!content) return;
  state.socket.emit('message_edit', {
    message_id: msgId,
    content: content,
    chat_id: state.currentChatId,
  });
  input.value = '';
  document.getElementById('sendBtn').onclick = sendMessage;
  document.getElementById('sendBtn').removeAttribute('data-edit-id');
  document.getElementById('sendBtn').disabled = true;
}

function pinMessage() {
  if (!contextMsgId) return;
  api('POST', `/api/v1/messages/${contextMsgId}/pin`);
  showToast('Message pinned', 'success');
  document.getElementById('contextMenu').classList.remove('open');
}

function reactToMessage() {
  document.getElementById('contextMenu').classList.remove('open');
  const emojis = ['❤️','😂','😮','😢','😡','👍','👎','🎉','🔥','💯'];
  const picker = document.createElement('div');
  picker.style.cssText = 'position:fixed;z-index:300;background:var(--surface-2);border:1px solid var(--border-2);border-radius:12px;padding:8px;display:flex;gap:4px;box-shadow:var(--shadow-lg);';
  picker.style.left = '50%';
  picker.style.top = '50%';
  picker.style.transform = 'translate(-50%,-50%)';
  picker.innerHTML = emojis.map(e => `<button onclick="doReact('${contextMsgId}','${e}');this.parentElement.remove();" style="font-size:1.4rem;background:none;border:none;cursor:pointer;padding:6px;border-radius:8px;" onmouseover="this.style.background='var(--surface-3)'" onmouseout="this.style.background='none'">${e}</button>`).join('');
  document.body.appendChild(picker);
  setTimeout(() => picker.remove(), 5000);
}

function doReact(msgId, emoji) {
  state.socket.emit('message_react', {
    message_id: msgId,
    emoji: emoji,
    chat_id: state.currentChatId,
  });
}

function toggleReaction(msgId, emoji) {
  doReact(msgId, emoji);
}

function forwardMessage() {
  showToast('Forward feature coming soon!', 'info');
  document.getElementById('contextMenu').classList.remove('open');
}

// ─── Read Receipts ────────────────────────────────────────────────────────────
function markRead(messageId, chatId) {
  state.socket.emit('message_read', { message_id: messageId, chat_id: chatId });
}

function updateReadReceipt(messageId, userId, readAt) {
  const msgEl = document.getElementById(`msg_${messageId}`);
  if (msgEl) {
    const icon = msgEl.querySelector('.read-icon');
    if (icon) icon.setAttribute('stroke', 'var(--primary-light)');
  }
}

function updateMessageReactions(messageId, reactions) {
  const msgEl = document.getElementById(`msg_${messageId}`);
  if (!msgEl) return;
  const existing = msgEl.querySelector('.message-reactions');
  const entries = Object.entries(reactions);
  const html = entries.length > 0 ? `<div class="message-reactions">
    ${entries.map(([emoji, users]) =>
      `<button class="reaction-chip ${users.includes(CURRENT_USER.id) ? 'mine' : ''}" onclick="toggleReaction('${messageId}','${emoji}')">
        ${emoji} <span>${users.length}</span>
      </button>`
    ).join('')}
  </div>` : '';
  if (existing) existing.outerHTML = html;
  else msgEl.querySelector('div:last-child')?.insertAdjacentHTML('afterend', html);
}

function updateMessageContent(messageId, content) {
  const msgEl = document.getElementById(`msg_${messageId}`);
  if (msgEl) {
    const bubble = msgEl.querySelector('.message-bubble div');
    if (bubble) bubble.textContent = content;
    // Add edited label
    const bubbleEl = msgEl.querySelector('.message-bubble');
    if (bubbleEl && !bubbleEl.querySelector('.message-edited')) {
      bubbleEl.insertAdjacentHTML('beforeend', '<span class="message-edited">(edited)</span>');
    }
  }
}

function markMessageDeleted(messageId, forEveryone) {
  if (!forEveryone) return;
  const msgEl = document.getElementById(`msg_${messageId}`);
  if (msgEl) {
    const bubble = msgEl.querySelector('.message-bubble');
    if (bubble) bubble.innerHTML = '<div class="message-deleted">🗑️ This message was deleted</div>';
  }
}

// ─── File Upload ───────────────────────────────────────────────────────────────
async function uploadFile(input, type) {
  const file = input.files[0];
  if (!file) return;
  document.getElementById('attachMenu').classList.add('hidden');

  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);
  formData.append('chat_id', state.currentChatId);

  showToast('Uploading...', 'info');

  try {
    const res = await fetch('/api/v1/upload', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (data.success) {
      const msgType = type === 'image' ? (file.type.startsWith('video') ? 'video' : 'image') : (type === 'audio' ? 'audio' : 'document');
      state.socket.emit('send_message', {
        chat_id: state.currentChatId,
        type: msgType,
        media_url: data.url,
        media_type: file.type,
        media_name: file.name,
        media_size: file.size,
      });
      showToast('File sent!', 'success');
    } else {
      showToast(data.error || 'Upload failed', 'error');
    }
  } catch (e) {
    showToast('Upload failed', 'error');
  }
  input.value = '';
}

// ─── Voice Notes ───────────────────────────────────────────────────────────────
async function startVoiceNote() {
  if (!navigator.mediaDevices) return showToast('Microphone not available', 'error');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.mediaRecorder = new MediaRecorder(stream);
    const chunks = [];
    state.mediaRecorder.ondataavailable = e => chunks.push(e.data);
    state.mediaRecorder.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('file', blob, 'voice_note.webm');
      formData.append('type', 'voice');
      formData.append('chat_id', state.currentChatId);
      try {
        const res = await fetch('/api/v1/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
          state.socket.emit('send_message', {
            chat_id: state.currentChatId,
            type: 'voice',
            media_url: data.url,
            media_type: 'audio/webm',
            media_name: 'Voice Note',
          });
        }
      } catch (e) { showToast('Failed to send voice note', 'error'); }
      stream.getTracks().forEach(t => t.stop());
    };
    state.mediaRecorder.start();
    state.recordingSeconds = 0;
    state.recordingInterval = setInterval(() => {
      state.recordingSeconds++;
      document.getElementById('voiceNoteBtn').title = `Recording: ${state.recordingSeconds}s`;
    }, 1000);
    document.getElementById('voiceNoteBtn').style.color = 'var(--danger)';
  } catch (e) {
    showToast('Microphone permission denied', 'error');
  }
}

function stopVoiceNote() {
  if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
    state.mediaRecorder.stop();
    clearInterval(state.recordingInterval);
    document.getElementById('voiceNoteBtn').style.color = '';
    document.getElementById('voiceNoteBtn').title = 'Hold for voice note';
  }
}

// ─── Search ────────────────────────────────────────────────────────────────────
let searchDebounce;
function searchUsers(q) {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(async () => {
    if (!q.trim()) { document.getElementById('userSearchResults').innerHTML = ''; return; }
    try {
      const res = await api('GET', `/api/v1/users/search?q=${encodeURIComponent(q)}`);
      const container = document.getElementById('userSearchResults');
      container.innerHTML = (res.users || []).map(u => `
        <div class="chat-item" onclick="startChatWith('${u.id}')">
          <img src="${escapeHtml(u.avatar_url || '/static/images/default-avatar.png')}" class="avatar avatar-md" />
          <div class="chat-item-info">
            <div class="chat-item-name">${escapeHtml(u.display_name)}</div>
            <div style="font-size:0.8rem;color:var(--text-3);">@${escapeHtml(u.username)}</div>
          </div>
        </div>
      `).join('') || '<div style="padding:16px;text-align:center;color:var(--text-3);">No users found</div>';
    } catch (e) {}
  }, 300);
}

async function startChatWith(userId) {
  closeModal('newChatModal');
  const res = await api('POST', '/api/v1/chats/start', { user_id: userId });
  if (res.chat_id) {
    await loadChats();
    openChat(res.chat_id);
  }
}

function searchChats(q) {
  renderChatList(state.chats);
}

function searchInChat() {
  showToast('Message search: Type in the search bar above', 'info');
}

// ─── Groups ────────────────────────────────────────────────────────────────────
let groupMemberSearchDebounce;
function searchGroupMembers(q) {
  clearTimeout(groupMemberSearchDebounce);
  groupMemberSearchDebounce = setTimeout(async () => {
    if (!q.trim()) return;
    const res = await api('GET', `/api/v1/users/search?q=${encodeURIComponent(q)}`);
    const container = document.getElementById('groupMemberResults');
    container.innerHTML = (res.users || []).map(u => `
      <div class="chat-item" onclick="toggleGroupMember('${u.id}','${escapeHtml(u.display_name)}','${escapeHtml(u.avatar_url || '')}')">
        <img src="${escapeHtml(u.avatar_url || '/static/images/default-avatar.png')}" class="avatar avatar-sm" />
        <div class="chat-item-info">
          <div class="chat-item-name">${escapeHtml(u.display_name)}</div>
          <div style="font-size:0.8rem;color:var(--text-3);">@${escapeHtml(u.username)}</div>
        </div>
        <div id="tick_${u.id}" style="display:none;color:var(--success);">✓</div>
      </div>
    `).join('') || '';
  }, 300);
}

function toggleGroupMember(userId, name, avatar) {
  const idx = state.selectedGroupMembers.findIndex(m => m.id === userId);
  const tick = document.getElementById(`tick_${userId}`);
  if (idx > -1) {
    state.selectedGroupMembers.splice(idx, 1);
    if (tick) tick.style.display = 'none';
  } else {
    state.selectedGroupMembers.push({ id: userId, name, avatar });
    if (tick) tick.style.display = 'block';
  }
  renderSelectedMembers();
}

function renderSelectedMembers() {
  const container = document.getElementById('selectedMembers');
  container.innerHTML = state.selectedGroupMembers.map(m => `
    <div style="display:flex;align-items:center;gap:4px;background:var(--primary-glow);border:1px solid var(--primary);border-radius:20px;padding:3px 10px;font-size:0.8rem;color:var(--primary-light);">
      ${escapeHtml(m.name)}
      <button onclick="toggleGroupMember('${m.id}','','')" style="background:none;border:none;color:inherit;cursor:pointer;padding:0 0 0 4px;font-size:0.9rem;">×</button>
    </div>
  `).join('');
}

async function createGroup() {
  const name = document.getElementById('groupNameInput').value.trim();
  const desc = document.getElementById('groupDescInput').value.trim();
  if (!name) return showToast('Group name is required', 'error');

  const res = await api('POST', '/api/v1/groups', {
    name, description: desc,
    member_ids: state.selectedGroupMembers.map(m => m.id)
  });

  if (res.success) {
    closeModal('newGroupModal');
    state.selectedGroupMembers = [];
    await loadChats();
    if (res.chat_id) openChat(res.chat_id);
    showToast(`Group "${name}" created!`, 'success');
  } else {
    showToast(res.error || 'Failed to create group', 'error');
  }
}

// ─── Online Status ────────────────────────────────────────────────────────────
function updateUserOnlineStatus(userId, isOnline, lastSeen) {
  if (state.currentChatData?.other_user?.id === userId) {
    const status = document.getElementById('chatHeaderStatus');
    const dot = document.getElementById('headerOnlineDot');
    status.textContent = isOnline ? '● Online' : 'Offline';
    status.className = `chat-header-status ${isOnline ? '' : 'offline'}`;
    dot.style.display = isOnline ? 'block' : 'none';
  }
  // Update in chat list
  const chat = state.chats.find(c => c.other_user?.id === userId);
  if (chat) {
    chat.other_user.is_online = isOnline;
    renderChatList(state.chats);
  }
}

// ─── Media Viewer ─────────────────────────────────────────────────────────────
function openMedia(url, type) {
  const viewer = document.getElementById('mediaViewer');
  const img = document.getElementById('mediaViewerImg');
  const video = document.getElementById('mediaViewerVideo');
  if (type === 'image') {
    img.src = url; img.style.display = 'block'; video.style.display = 'none';
  } else {
    video.src = url; video.style.display = 'block'; img.style.display = 'none';
  }
  viewer.classList.remove('hidden');
}

function closeMediaViewer(e) {
  if (!e || e.target === document.getElementById('mediaViewer') || e.target.className === 'media-viewer-close') {
    document.getElementById('mediaViewer').classList.add('hidden');
  }
}

// ─── Info Panel ────────────────────────────────────────────────────────────────
function toggleInfoPanel() {
  document.getElementById('infoPanel').classList.toggle('open');
}

// ─── Chat Actions ──────────────────────────────────────────────────────────────
async function archiveCurrentChat() {
  if (!state.currentChatId) return;
  await api('POST', `/api/v1/chats/${state.currentChatId}/archive`);
  showToast('Chat archived', 'success');
  await loadChats();
}

async function blockCurrentUser() {
  const chat = state.currentChatData;
  if (!chat || chat.type !== 'direct') return;
  const userId = chat.other_user?.id;
  if (userId && confirm('Block this user?')) {
    await api('POST', `/api/v1/users/${userId}/block`);
    showToast('User blocked', 'success');
  }
}

async function reportCurrentUser() {
  const chat = state.currentChatData;
  if (!chat || chat.type !== 'direct') return;
  const userId = chat.other_user?.id;
  if (!userId) return;
  const reason = prompt('Reason for report:');
  if (reason) {
    await api('POST', `/api/v1/users/${userId}/report`, { reason });
    showToast('Report submitted', 'success');
  }
}

async function exportChat() {
  if (!state.currentChatId) return;
  const msgs = state.messages[state.currentChatId] || [];
  const text = msgs.map(m => `[${formatTime(m.created_at)}] ${m.sender_id === CURRENT_USER.id ? 'You' : 'Other'}: ${m.content || '[media]'}`).join('\n');
  const blob = new Blob([text], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `chat_${state.currentChatId}.txt`;
  a.click();
}

function clearCurrentChat() {
  if (confirm('Clear all messages? This cannot be undone.')) {
    document.getElementById('messagesContainer').innerHTML = `<div class="chat-empty"><div class="chat-empty-icon">💬</div><h3>No messages</h3></div>`;
  }
}

// ─── Calls ─────────────────────────────────────────────────────────────────────
function initiateVoiceCall() {
  showToast('Voice calls require WebRTC setup. Architecture is ready!', 'info');
}

function initiateVideoCall() {
  showToast('Video calls require WebRTC setup. Architecture is ready!', 'info');
}

function showIncomingCall(data) {
  const modal = document.getElementById('callModal');
  document.getElementById('callName').textContent = data.caller?.display_name || 'Unknown';
  document.getElementById('callAvatar').src = data.caller?.avatar_url || '/static/images/default-avatar.png';
  document.getElementById('callStatus').textContent = 'Incoming call...';
  document.getElementById('acceptCallBtn').style.display = 'flex';
  modal.classList.remove('hidden');
  modal.classList.add('open');
}

function endCall() {
  document.getElementById('callModal').classList.add('hidden');
  document.getElementById('callModal').classList.remove('open');
}

function acceptCall() {}
function toggleMute() {}
function handleCallAnswered(data) {}
function handleCallRejected(data) { endCall(); showToast('Call declined', 'info'); }
function handleIceCandidate(data) {}

// ─── Notifications ─────────────────────────────────────────────────────────────
function showNotification(data) {
  if ('Notification' in window && Notification.permission === 'granted') {
    const msg = data.message;
    new Notification(data.sender?.display_name || 'New Message', {
      body: msg?.content || 'Sent a file',
      icon: data.sender?.avatar_url || '/static/images/default-avatar.png',
    });
  }
}

function requestNotificationPermission() {
  if ('Notification' in window) Notification.requestPermission();
}

// ─── Unread ────────────────────────────────────────────────────────────────────
function incrementUnread(chatId) {
  state.unreadCounts[chatId] = (state.unreadCounts[chatId] || 0) + 1;
  const item = document.getElementById(`chatItem_${chatId}`);
  if (item) {
    const badge = item.querySelector('.badge-count');
    if (badge) badge.textContent = state.unreadCounts[chatId];
    else item.querySelector('.chat-item-bottom')?.insertAdjacentHTML('beforeend', `<div class="badge-count">${state.unreadCounts[chatId]}</div>`);
  }
}

function clearUnread(chatId) {
  state.unreadCounts[chatId] = 0;
  const item = document.getElementById(`chatItem_${chatId}`);
  if (item) { const badge = item.querySelector('.badge-count'); if (badge) badge.remove(); }
}

// ─── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(tab) {
  state.activePage = tab;
  document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(`tab${tab.charAt(0).toUpperCase() + tab.slice(1)}`).classList.add('active');
  renderChatList(state.chats);
}

// ─── Mobile ────────────────────────────────────────────────────────────────────
function backToList() {
  document.getElementById('chatSidebar').classList.add('open');
  document.getElementById('sidebarOverlay').classList.add('active');
}

function closeSidebar() {
  document.getElementById('chatSidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('active');
}

// ─── Theme ─────────────────────────────────────────────────────────────────────
async function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  await api('POST', '/auth/profile', { theme: next });
}

// ─── Emoji / Attach ────────────────────────────────────────────────────────────
function toggleEmojiPanel() {
  document.getElementById('emojiPanel').classList.toggle('hidden');
  document.getElementById('attachMenu').classList.add('hidden');
}

function toggleAttachMenu() {
  document.getElementById('attachMenu').classList.toggle('hidden');
  document.getElementById('emojiPanel').classList.add('hidden');
}

function insertEmoji(emoji) {
  const input = document.getElementById('messageInput');
  input.value += emoji;
  input.focus();
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('emojiPanel').classList.add('hidden');
}

// ─── Modals ────────────────────────────────────────────────────────────────────
function showNewChatModal() { document.getElementById('newChatModal').classList.add('open'); document.getElementById('userSearchInput').focus(); }
function showNewGroupModal() {
  closeAllDropdowns();
  state.selectedGroupMembers = [];
  document.getElementById('groupNameInput').value = '';
  document.getElementById('groupDescInput').value = '';
  document.getElementById('groupMemberResults').innerHTML = '';
  document.getElementById('selectedMembers').innerHTML = '';
  document.getElementById('newGroupModal').classList.add('open');
}
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

// ─── Dropdown ──────────────────────────────────────────────────────────────────
function toggleDropdown(containerId) {
  const container = document.getElementById(containerId);
  const menu = container.querySelector('.dropdown-menu');
  const isOpen = menu.classList.contains('open');
  closeAllDropdowns();
  if (!isOpen) menu.classList.add('open');
}

function closeAllDropdowns() {
  document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('open'));
}

// ─── Helpers ───────────────────────────────────────────────────────────────────
async function api(method, url, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function scrollToBottom(behavior = 'smooth') {
  const container = document.getElementById('messagesContainer');
  container.scrollTo({ top: container.scrollHeight, behavior });
}

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return 'now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
  if (diff < 86400000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toastContainer') || (() => {
    const el = document.createElement('div');
    el.id = 'toastContainer';
    el.className = 'toast-container';
    document.body.appendChild(el);
    return el;
  })();
  const toast = document.createElement('div');
  toast.className = `toast toast-${type} show`;
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<div class="toast-icon">${icon}</div><span>${escapeHtml(msg)}</span><button onclick="this.parentElement.remove()">×</button>`;
  container.appendChild(toast);
  setTimeout(() => toast.classList.remove('show'), 4000);
  setTimeout(() => toast.remove(), 4500);
}

// Request notification permission on load
setTimeout(requestNotificationPermission, 2000);
