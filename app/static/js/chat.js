/**
 * KHANDHARS CHAT - Chat Client
 * WhatsApp-style, fast, mobile-first
 */
'use strict';

// ── State ────────────────────────────────────────────────────────────────────
const S = {
  socket: null,
  currentChatId: null,
  currentChatData: null,
  chats: [],
  tab: 'all',
  replyTo: null,
  ctxMsgId: null,
  ctxIsOwn: false,
  groupMembers: [],
  mediaRecorder: null,
  typingTimer: null,
  isTyping: false,
  unread: {},
  isMobile: window.innerWidth <= 768,
  editMsgId: null,
  searchDebounce: null,
};

const EMOJIS = ['😊','😂','❤️','👍','🔥','😍','🙏','💪','😭','🤣','✨','😎',
                '🥺','🎉','💯','🚀','👀','🤔','😅','😢','💀','🎊','⭐','✅',
                '🙌','😏','🤝','💡','🌟','😘','👏','🥳'];

// ── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSocket();
  loadChats();
  buildEmojiGrid();
  setupMobileBack();

  // Send device fingerprint to server for persistent login
  fetch('/api/v1/me/device', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ device_id: DEVICE_ID })
  }).catch(() => {});

  // Close panels on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('.dropdown')) closeAllDropdowns();
    if (!e.target.closest('#ctxMenu') && !e.target.closest('.message-bubble'))
      document.getElementById('ctxMenu').classList.remove('open');
    if (!e.target.closest('#emojiPanel') && !e.target.closest('#emojiBtn'))
      document.getElementById('emojiPanel').classList.add('hidden');
    if (!e.target.closest('#attachMenu') && !e.target.closest('.attach-btn'))
      document.getElementById('attachMenu').classList.add('hidden');
    if (!e.target.closest('#reactionPicker'))
      document.getElementById('reactionPicker').classList.add('hidden');
  });

  if (OPEN_CHAT) openChat(OPEN_CHAT);
  else if (OPEN_GROUP) {/* handled after chats load */}

  // Request notifications
  if ('Notification' in window && Notification.permission === 'default')
    Notification.requestPermission();
});

// ── Socket ───────────────────────────────────────────────────────────────────
function initSocket() {
  S.socket = io({ transports: ['websocket','polling'], upgrade: true });

  S.socket.on('connect', () => {
    S.chats.forEach(c => S.socket.emit('join_chat', { chat_id: c.id }));
  });

  S.socket.on('new_message', msg => {
    if (msg.chat_id === S.currentChatId) {
      appendMessage(msg, true);
      scrollToBottom('smooth');
      markRead(msg.id, msg.chat_id);
    }
    updateChatPreview(msg);
    if (msg.sender_id !== ME.id && msg.chat_id !== S.currentChatId) {
      S.unread[msg.chat_id] = (S.unread[msg.chat_id] || 0) + 1;
      renderChatList();
      pushNotification(msg);
    }
  });

  S.socket.on('user_typing', d => {
    if (d.chat_id === S.currentChatId && d.user_id !== ME.id)
      d.is_typing ? showTyping(d.display_name) : hideTyping();
  });

  S.socket.on('user_online',  d => updateOnlineStatus(d.user_id, true));
  S.socket.on('user_offline', d => updateOnlineStatus(d.user_id, false, d.last_seen));

  S.socket.on('message_read_receipt', d => markDelivered(d.message_id, true));
  S.socket.on('message_reaction_update', d => {
    if (d.chat_id === S.currentChatId) refreshReactions(d.message_id, d.reactions);
  });
  S.socket.on('message_deleted', d => {
    if (d.chat_id === S.currentChatId && d.deleted_for_everyone) markDeleted(d.message_id);
  });
  S.socket.on('message_edited', d => {
    if (d.chat_id === S.currentChatId) updateMsgText(d.message_id, d.content);
  });
  S.socket.on('chat_notification', d => {
    if (d.chat_id !== S.currentChatId) pushNotification(d);
  });
}

// ── Load Chats ───────────────────────────────────────────────────────────────
async function loadChats() {
  try {
    const res = await api('GET', '/api/v1/chats');
    S.chats = res.chats || [];
    renderChatList();
    S.chats.forEach(c => S.socket.emit('join_chat', { chat_id: c.id }));
    if (OPEN_CHAT) openChat(OPEN_CHAT);
  } catch (e) {
    console.error('Load chats', e);
  }
}

function renderChatList() {
  const el = document.getElementById('chatList');
  const q  = (document.getElementById('searchInput').value || '').toLowerCase();
  const tab = S.tab;

  let list = S.chats.filter(c => {
    if (tab === 'groups')   return c.type === 'group';
    if (tab === 'archived') return c.is_archived;
    if (tab === 'unread')   return (S.unread[c.id] || 0) > 0 || (c.unread_count || 0) > 0;
    return !c.is_archived;
  });

  if (q) {
    list = list.filter(c => {
      const name = c.type === 'group' ? c.group?.name : c.other_user?.display_name;
      return (name || '').toLowerCase().includes(q);
    });
  }

  if (!list.length) {
    el.innerHTML = `<div style="padding:32px;text-align:center;color:var(--text-3);font-size:0.86rem;">
      ${tab === 'unread' ? 'No unread chats' : tab === 'groups' ? 'No groups yet' : tab === 'archived' ? 'No archived chats' : 'No conversations yet'}
    </div>`;
    return;
  }

  el.innerHTML = list.map(c => chatItemHTML(c)).join('');
}

function chatItemHTML(c) {
  const isGroup  = c.type === 'group';
  const name     = isGroup ? (c.group?.name || 'Group') : (c.other_user?.display_name || 'Unknown');
  const avatar   = isGroup ? (c.group?.avatar_url || '/static/images/default-group.png') : (c.other_user?.avatar_url || '/static/images/default-avatar.png');
  const isOnline = !isGroup && c.other_user?.is_online;
  const last     = c.last_message;
  const preview  = last ? (last.is_deleted ? 'Deleted message' : last.message_type !== 'text' ? last.message_type : (last.content || '')) : 'No messages yet';
  const time     = last ? relativeTime(last.created_at) : '';
  const unread   = S.unread[c.id] || c.unread_count || 0;
  const active   = c.id === S.currentChatId;

  return `<div class="chat-item ${active ? 'active' : ''}" id="ci_${c.id}" onclick="openChat('${c.id}')">
    <div class="avatar-wrap">
      <img src="${esc(avatar)}" class="avatar avatar-md" onerror="this.src='/static/images/default-avatar.png'" />
      ${isOnline ? '<div class="online-dot"></div>' : ''}
    </div>
    <div class="chat-item-info">
      <div class="chat-item-top">
        <div class="chat-item-name truncate">${esc(name)}</div>
        <div class="chat-item-time">${time}</div>
      </div>
      <div class="chat-item-bottom">
        <div class="chat-item-preview ${unread > 0 ? 'unread' : ''} truncate">${esc(preview)}</div>
        ${unread > 0 ? `<div class="badge-count">${unread > 99 ? '99+' : unread}</div>` : ''}
      </div>
    </div>
  </div>`;
}

function updateChatPreview(msg) {
  const chat = S.chats.find(c => c.id === msg.chat_id);
  if (chat) {
    chat.last_message = msg;
    chat.last_message_at = msg.created_at;
    // Move to top
    S.chats = [chat, ...S.chats.filter(c => c.id !== msg.chat_id)];
  }
  renderChatList();
}

// ── Open Chat ─────────────────────────────────────────────────────────────────
async function openChat(chatId) {
  S.currentChatId = chatId;
  const chat = S.chats.find(c => c.id === chatId);
  S.currentChatData = chat;

  // Clear unread
  S.unread[chatId] = 0;

  // UI
  document.getElementById('welcomeScreen').classList.add('hidden');
  const win = document.getElementById('chatWindow');
  win.classList.remove('hidden');
  win.style.display = 'flex';

  // Active state
  document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
  const ci = document.getElementById('ci_' + chatId);
  if (ci) ci.classList.add('active');

  // Mobile: show main panel
  if (S.isMobile) {
    document.getElementById('chatSidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('active');
    document.getElementById('backBtn').style.display = 'flex';
    // Ensure chat main is visible
    document.getElementById('chatMain').style.display = 'flex';
  }

  // Update header
  if (chat) {
    const isGroup = chat.type === 'group';
    const name    = isGroup ? chat.group?.name : chat.other_user?.display_name;
    const avatar  = isGroup ? (chat.group?.avatar_url || '/static/images/default-group.png') : (chat.other_user?.avatar_url || '/static/images/default-avatar.png');
    const online  = !isGroup && chat.other_user?.is_online;

    document.getElementById('headerAvatar').src      = avatar;
    document.getElementById('chatHeaderName').textContent = name || 'Chat';
    document.getElementById('chatHeaderStatus').textContent = isGroup
      ? `${chat.group?.member_count || 0} members`
      : (online ? 'Online' : 'Tap for info');
    document.getElementById('chatHeaderStatus').className = 'chat-header-status ' + (online ? '' : 'offline');
    document.getElementById('headerOnlineDot').style.display = online ? 'block' : 'none';

    // Info panel
    document.getElementById('infoPanelAvatar').src  = avatar;
    document.getElementById('infoPanelName').textContent  = name || '';
    document.getElementById('infoPanelMeta').textContent  = isGroup ? 'Group' : (online ? 'Online' : 'Offline');
  }

  S.socket.emit('join_chat', { chat_id: chatId });
  openChatMobile(chatId);
  await loadMessages(chatId);
}

// ── Load Messages ─────────────────────────────────────────────────────────────
async function loadMessages(chatId, page = 1) {
  const container = document.getElementById('messagesContainer');
  if (page === 1) {
    container.innerHTML = `<div style="display:flex;justify-content:center;align-items:center;height:100%;color:var(--text-3);gap:10px;">
      <div class="spinner"></div><span>Loading</span>
    </div>`;
  }
  try {
    const res = await api('GET', `/api/v1/chats/${chatId}/messages?page=${page}&per_page=50`);
    const msgs = res.messages || [];
    if (page === 1) container.innerHTML = '';

    if (res.has_more) {
      const lb = document.createElement('div');
      lb.style.cssText = 'text-align:center;padding:8px;';
      lb.innerHTML = `<button class="btn btn-ghost btn-sm" onclick="loadMessages('${chatId}',${page+1})">Load earlier</button>`;
      container.prepend(lb);
    }

    if (!msgs.length && page === 1) {
      container.innerHTML = `<div class="chat-empty">
        <svg class="chat-empty-icon" width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <h3>No messages yet</h3>
        <p>Say hello to start the conversation</p>
      </div>`;
      return;
    }

    // Date separators + messages
    let lastDate = '';
    msgs.forEach(msg => {
      const d = new Date(msg.created_at).toLocaleDateString();
      if (d !== lastDate) {
        lastDate = d;
        const sep = document.createElement('div');
        sep.className = 'date-separator';
        sep.innerHTML = `<span>${friendlyDate(msg.created_at)}</span>`;
        container.appendChild(sep);
      }
      appendMessage(msg, false);
    });

    if (page === 1) scrollToBottom('instant');
  } catch (e) {
    container.innerHTML = `<div style="text-align:center;padding:24px;color:var(--danger);">Failed to load. <button class="btn btn-ghost btn-sm" onclick="loadMessages('${chatId}')">Retry</button></div>`;
  }
}

// ── Render Message ─────────────────────────────────────────────────────────────
function appendMessage(msg, animate) {
  const container = document.getElementById('messagesContainer');
  const isOwn = msg.sender_id === ME.id;
  const sender = msg.sender || {};
  container.querySelector('.chat-empty')?.remove();

  let body = '';
  if (msg.is_deleted) {
    body = `<span style="opacity:0.5;font-style:italic;">Message deleted</span>`;
  } else if (msg.message_type === 'text') {
    body = `<span class="selectable">${esc(msg.content || '')}</span>`;
  } else if (msg.message_type === 'image') {
    body = `<img src="${esc(msg.media_url||'')}" style="max-width:240px;max-height:240px;border-radius:10px;cursor:pointer;display:block;" onclick="openMedia('${esc(msg.media_url||'')}','image')" loading="lazy" />`;
  } else if (msg.message_type === 'video') {
    body = `<video src="${esc(msg.media_url||'')}" controls style="max-width:240px;border-radius:10px;" preload="metadata"></video>`;
  } else if (msg.message_type === 'voice' || msg.message_type === 'audio') {
    body = `<audio src="${esc(msg.media_url||'')}" controls style="max-width:220px;"></audio>`;
  } else if (msg.message_type === 'document') {
    body = `<div style="display:flex;align-items:center;gap:9px;padding:7px 10px;background:rgba(255,255,255,0.07);border-radius:9px;min-width:180px;">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <div style="flex:1;min-width:0;"><div style="font-size:0.82rem;font-weight:600;truncate:true;">${esc(msg.media_name||'Document')}</div>${msg.media_size ? `<div style="font-size:0.72rem;opacity:0.6;">${fmtBytes(msg.media_size)}</div>` : ''}</div>
      <a href="${esc(msg.media_url||'')}" download style="color:inherit;opacity:0.7;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
      </a>
    </div>`;
  }

  // Reply
  let replyHTML = '';
  if (msg.reply_to_id) {
    replyHTML = `<div style="border-left:3px solid rgba(255,255,255,0.4);padding:3px 8px;margin-bottom:5px;border-radius:0 6px 6px 0;font-size:0.78rem;opacity:0.75;">Replying to a message</div>`;
  }

  // Reactions
  const reactions = (typeof msg.reactions === 'object' && msg.reactions) ? msg.reactions : {};
  let reactHTML = '';
  const rEntries = Object.entries(reactions);
  if (rEntries.length) {
    reactHTML = `<div class="message-reactions">${rEntries.map(([e,u])=>
      `<button class="reaction-chip ${u.includes(ME.id)?'mine':''}" onclick="toggleReact('${msg.id}','${e}')">${e} <span>${u.length}</span></button>`
    ).join('')}</div>`;
  }

  const el = document.createElement('div');
  el.className = `message-row ${isOwn ? 'own' : ''} ${animate ? 'animate-slideIn' : ''}`;
  el.id = `msg_${msg.id}`;
  el.dataset.msgId = msg.id;
  el.dataset.senderId = msg.sender_id;

  const avatarHTML = !isOwn
    ? `<img src="${esc(sender.avatar_url||'/static/images/default-avatar.png')}" class="avatar avatar-sm" onerror="this.src='/static/images/default-avatar.png'" />`
    : '';

  const timeStr = fmtTime(msg.created_at);
  const readIcon = isOwn ? `<svg style="width:13px;height:13px;" viewBox="0 0 24 24" fill="none" stroke="${(msg.read_by||[]).length > 0 ? 'var(--primary-light)' : 'rgba(255,255,255,0.5)'}" stroke-width="2.5" id="ri_${msg.id}"><polyline points="20 6 9 17 4 12"/></svg>` : '';

  el.innerHTML = `
    ${avatarHTML ? `<div class="avatar-wrap">${avatarHTML}</div>` : (isOwn ? '' : '<div style="width:34px;flex-shrink:0;"></div>')}
    <div style="display:flex;flex-direction:column;${isOwn?'align-items:flex-end;':''}max-width:68%;">
      ${!isOwn && sender.display_name ? `<div style="font-size:0.74rem;font-weight:600;color:var(--primary-light);margin-bottom:2px;">${esc(sender.display_name)}</div>` : ''}
      ${replyHTML}
      <div class="message-bubble" id="bubble_${msg.id}" oncontextmenu="showCtxMenu(event,'${msg.id}',${isOwn})">
        ${body}
        ${msg.is_edited ? `<span style="font-size:0.68rem;opacity:0.55;margin-left:4px;">(edited)</span>` : ''}
      </div>
      ${reactHTML}
      <div class="message-time">${timeStr} ${readIcon}</div>
    </div>`;

  container.appendChild(el);
  return el;
}

// ── Send ────────────────────────────────────────────────────────────────────
function sendMessage() {
  const input = document.getElementById('msgInput');
  const text  = input.value.trim();
  if (!text && !S.editMsgId) return;
  if (!S.currentChatId) return;

  if (S.editMsgId) {
    S.socket.emit('message_edit', { message_id: S.editMsgId, content: text, chat_id: S.currentChatId });
    S.editMsgId = null;
    document.getElementById('sendBtn').style.background = '';
  } else {
    S.socket.emit('send_message', {
      chat_id: S.currentChatId,
      content: text,
      type: 'text',
      reply_to_id: S.replyTo?.id || null,
    });
  }

  input.value = '';
  input.style.height = 'auto';
  document.getElementById('sendBtn').disabled = true;
  cancelReply();
  stopTyping();
}

function onInputKey(e) {
  const enterSend = ME.enter_to_send;
  if (e.key === 'Enter') {
    if (enterSend && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    else if (!enterSend && e.ctrlKey) { e.preventDefault(); sendMessage(); }
  }
}

function onInputChange(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 130) + 'px';
  document.getElementById('sendBtn').disabled = !el.value.trim();
  if (!S.isTyping && el.value.trim()) {
    S.isTyping = true;
    S.socket.emit('typing_start', { chat_id: S.currentChatId });
  }
  clearTimeout(S.typingTimer);
  S.typingTimer = setTimeout(stopTyping, 2000);
}

function stopTyping() {
  if (S.isTyping) {
    S.isTyping = false;
    S.socket.emit('typing_stop', { chat_id: S.currentChatId });
  }
}

// ── Upload ────────────────────────────────────────────────────────────────────
async function uploadAttachment(input, type) {
  const files = Array.from(input.files);
  if (!files.length) return;
  document.getElementById('attachMenu').classList.add('hidden');

  for (const file of files) {
    showToast('Uploading ' + file.name + '...', 'info');
    const fd = new FormData();
    fd.append('file', file);
    fd.append('type', type);
    fd.append('chat_id', S.currentChatId);

    try {
      const res = await fetch('/api/v1/upload', { method: 'POST', body: fd });
      const data = await res.json();
      if (data.success) {
        const msgType = type === 'image' && file.type.startsWith('video') ? 'video' : type;
        S.socket.emit('send_message', {
          chat_id: S.currentChatId,
          type: msgType,
          media_url: data.url,
          media_type: file.type,
          media_name: file.name,
          media_size: file.size,
        });
      } else {
        showToast(data.error || 'Upload failed', 'error');
      }
    } catch { showToast('Upload failed', 'error'); }
  }
  input.value = '';
}

// ── Voice Note ─────────────────────────────────────────────────────────────
let voiceChunks = [];
async function startVoice(e) {
  if (e) e.preventDefault();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    S.mediaRecorder = new MediaRecorder(stream);
    voiceChunks = [];
    S.mediaRecorder.ondataavailable = e => voiceChunks.push(e.data);
    S.mediaRecorder.onstop = async () => {
      const blob = new Blob(voiceChunks, { type: 'audio/webm' });
      stream.getTracks().forEach(t => t.stop());
      const fd = new FormData();
      fd.append('file', blob, 'voice.webm');
      fd.append('type', 'voice');
      fd.append('chat_id', S.currentChatId);
      try {
        const res = await fetch('/api/v1/upload', { method: 'POST', body: fd });
        const d = await res.json();
        if (d.success) S.socket.emit('send_message', { chat_id: S.currentChatId, type: 'voice', media_url: d.url });
      } catch {}
    };
    S.mediaRecorder.start();
    document.getElementById('voiceBtn').style.color = 'var(--danger)';
  } catch { showToast('Microphone permission denied', 'error'); }
}

function stopVoice(e) {
  if (e) e.preventDefault();
  if (S.mediaRecorder && S.mediaRecorder.state === 'recording') {
    S.mediaRecorder.stop();
    document.getElementById('voiceBtn').style.color = '';
  }
}

// ── Typing ───────────────────────────────────────────────────────────────────
function showTyping(name) {
  document.getElementById('typingName').textContent = name + ' is typing';
  document.getElementById('typingIndicator').classList.remove('hidden');
  clearTimeout(S._typingHide);
  S._typingHide = setTimeout(() => document.getElementById('typingIndicator').classList.add('hidden'), 3000);
}
function hideTyping() { document.getElementById('typingIndicator').classList.add('hidden'); }

// ── Reply ────────────────────────────────────────────────────────────────────
function setReply(msgId, author, content) {
  S.replyTo = { id: msgId };
  document.getElementById('replyAuthor').textContent = author;
  document.getElementById('replyContent').textContent = content;
  document.getElementById('replyPreview').classList.remove('hidden');
  document.getElementById('msgInput').focus();
}
function cancelReply() {
  S.replyTo = null;
  document.getElementById('replyPreview').classList.add('hidden');
}

// ── Context Menu ─────────────────────────────────────────────────────────────
function showCtxMenu(e, msgId, isOwn) {
  e.preventDefault();
  S.ctxMsgId = msgId;
  S.ctxIsOwn = isOwn;
  const m = document.getElementById('ctxMenu');
  m.classList.add('open');
  document.getElementById('ctxEditBtn').style.display = isOwn ? 'flex' : 'none';
  const x = Math.min(e.clientX, window.innerWidth - 180);
  const y = Math.min(e.clientY, window.innerHeight - 240);
  m.style.left = x + 'px';
  m.style.top  = y + 'px';
}
function ctxReply() {
  const el = document.getElementById(`bubble_${S.ctxMsgId}`);
  const text = el?.innerText?.trim() || '';
  const sid  = document.getElementById(`msg_${S.ctxMsgId}`)?.dataset.senderId;
  setReply(S.ctxMsgId, sid === ME.id ? 'You' : 'Someone', text);
  document.getElementById('ctxMenu').classList.remove('open');
}
function ctxCopy() {
  const el = document.getElementById(`bubble_${S.ctxMsgId}`);
  if (el) navigator.clipboard.writeText(el.innerText.trim());
  showToast('Copied', 'success');
  document.getElementById('ctxMenu').classList.remove('open');
}
function ctxDelete() {
  if (!confirm('Delete this message?')) return;
  S.socket.emit('message_delete', { message_id: S.ctxMsgId, chat_id: S.currentChatId, for: S.ctxIsOwn ? 'everyone' : 'me' });
  document.getElementById('ctxMenu').classList.remove('open');
}
function ctxEdit() {
  const el = document.getElementById(`bubble_${S.ctxMsgId}`);
  const text = el?.querySelector('.selectable')?.textContent?.trim() || '';
  const inp = document.getElementById('msgInput');
  inp.value = text;
  inp.focus();
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('sendBtn').style.background = 'var(--warning)';
  S.editMsgId = S.ctxMsgId;
  document.getElementById('ctxMenu').classList.remove('open');
}
function ctxPin() {
  api('POST', `/api/v1/messages/${S.ctxMsgId}/pin`).then(() => showToast('Pinned', 'success'));
  document.getElementById('ctxMenu').classList.remove('open');
}
function ctxForward() { showToast('Forward coming soon', 'info'); document.getElementById('ctxMenu').classList.remove('open'); }
function ctxReact() {
  document.getElementById('ctxMenu').classList.remove('open');
  showReactionPicker(S.ctxMsgId);
}

// ── Reactions ─────────────────────────────────────────────────────────────────
function showReactionPicker(msgId) {
  const picker = document.getElementById('reactionPicker');
  const quickEmojis = ['❤️','😂','😮','😢','👍','👎','🙏','🔥'];
  picker.innerHTML = quickEmojis.map(e =>
    `<button onclick="toggleReact('${msgId}','${e}');document.getElementById('reactionPicker').classList.add('hidden');"
      style="font-size:1.3rem;background:none;border:none;cursor:pointer;padding:4px 5px;border-radius:7px;line-height:1;"
      onmouseover="this.style.background='var(--surface-3)'" onmouseout="this.style.background='none'">${e}</button>`
  ).join('');
  const el = document.getElementById(`msg_${msgId}`);
  if (el) {
    const r = el.getBoundingClientRect();
    picker.style.left = Math.min(r.left, window.innerWidth - 280) + 'px';
    picker.style.top  = (r.top - 60) + 'px';
  }
  picker.classList.remove('hidden');
}
function toggleReact(msgId, emoji) {
  S.socket.emit('message_react', { message_id: msgId, emoji, chat_id: S.currentChatId });
}
function refreshReactions(msgId, reactions) {
  const el = document.getElementById(`msg_${msgId}`);
  if (!el) return;
  let rd = el.querySelector('.message-reactions');
  const entries = Object.entries(reactions || {});
  const html = entries.length ? `<div class="message-reactions">${entries.map(([e,u]) =>
    `<button class="reaction-chip ${u.includes(ME.id)?'mine':''}" onclick="toggleReact('${msgId}','${e}')">${e} <span>${u.length}</span></button>`
  ).join('')}</div>` : '';
  if (rd) rd.outerHTML = html;
  else el.querySelector('.message-time')?.insertAdjacentHTML('beforebegin', html);
}

// ── Read receipts / status ───────────────────────────────────────────────────
function markRead(msgId, chatId) {
  S.socket.emit('message_read', { message_id: msgId, chat_id: chatId });
}
function markDelivered(msgId, read) {
  const icon = document.getElementById(`ri_${msgId}`);
  if (icon) icon.setAttribute('stroke', read ? 'var(--primary-light)' : 'rgba(255,255,255,0.5)');
}
function markDeleted(msgId) {
  const b = document.getElementById(`bubble_${msgId}`);
  if (b) b.innerHTML = '<span style="opacity:0.5;font-style:italic;">Message deleted</span>';
}
function updateMsgText(msgId, content) {
  const b = document.getElementById(`bubble_${msgId}`);
  if (b) {
    const sp = b.querySelector('.selectable');
    if (sp) sp.textContent = content;
    if (!b.querySelector('.edited-label')) b.insertAdjacentHTML('beforeend', '<span class="edited-label" style="font-size:0.68rem;opacity:0.55;margin-left:4px;">(edited)</span>');
  }
}

// ── Online status ────────────────────────────────────────────────────────────
function updateOnlineStatus(userId, online, lastSeen) {
  if (S.currentChatData?.other_user?.id === userId) {
    document.getElementById('chatHeaderStatus').textContent = online ? 'Online' : 'Offline';
    document.getElementById('chatHeaderStatus').className = 'chat-header-status ' + (online ? '' : 'offline');
    document.getElementById('headerOnlineDot').style.display = online ? 'block' : 'none';
  }
  const chat = S.chats.find(c => c.other_user?.id === userId);
  if (chat) { chat.other_user.is_online = online; renderChatList(); }
}

// ── User Search ───────────────────────────────────────────────────────────────
let _searchT;
function debounceSearchUsers(q) {
  clearTimeout(_searchT);
  _searchT = setTimeout(() => searchUsers(q), 280);
}
async function searchUsers(q) {
  const el = document.getElementById('userSearchResults');
  if (!q.trim()) { el.innerHTML = ''; return; }
  try {
    const res = await api('GET', `/api/v1/users/search?q=${encodeURIComponent(q)}`);
    el.innerHTML = (res.users || []).map(u => `
      <div class="chat-item" onclick="startChat('${u.id}')">
        <img src="${esc(u.avatar_url||'/static/images/default-avatar.png')}" class="avatar avatar-md" onerror="this.src='/static/images/default-avatar.png'" />
        <div class="chat-item-info">
          <div class="chat-item-name">${esc(u.display_name)}</div>
          <div style="font-size:0.78rem;color:var(--text-3);">@${esc(u.username)}</div>
        </div>
      </div>`).join('') || '<div style="padding:16px;text-align:center;color:var(--text-3);font-size:0.86rem;">No users found</div>';
  } catch {}
}
async function startChat(userId) {
  closeModal('newChatModal');
  const res = await api('POST', '/api/v1/chats/start', { user_id: userId });
  if (res.chat_id) { await loadChats(); openChat(res.chat_id); }
}

// ── Group ─────────────────────────────────────────────────────────────────────
let _gSearchT;
function debounceGroupSearch(q) {
  clearTimeout(_gSearchT);
  _gSearchT = setTimeout(() => searchGroupUsers(q), 280);
}
async function searchGroupUsers(q) {
  if (!q.trim()) return;
  const res = await api('GET', `/api/v1/users/search?q=${encodeURIComponent(q)}`);
  document.getElementById('groupMemberResults').innerHTML = (res.users || []).map(u =>
    `<div class="chat-item" onclick="toggleGroupMember('${u.id}','${esc(u.display_name)}')">
      <img src="${esc(u.avatar_url||'/static/images/default-avatar.png')}" class="avatar avatar-sm" onerror="this.src='/static/images/default-avatar.png'" />
      <div class="chat-item-info"><div class="chat-item-name">${esc(u.display_name)}</div></div>
      <div id="gm_${u.id}" style="color:var(--success);display:none;font-size:1.1rem;">&#x2713;</div>
    </div>`
  ).join('');
}
function toggleGroupMember(id, name) {
  const idx = S.groupMembers.findIndex(m => m.id === id);
  if (idx > -1) { S.groupMembers.splice(idx, 1); const t = document.getElementById('gm_'+id); if(t) t.style.display='none'; }
  else { S.groupMembers.push({ id, name }); const t = document.getElementById('gm_'+id); if(t) t.style.display='block'; }
  document.getElementById('selectedGroupMembers').innerHTML = S.groupMembers.map(m =>
    `<span style="display:inline-flex;align-items:center;gap:4px;background:var(--primary-glow);border:1px solid var(--primary);border-radius:14px;padding:2px 8px;font-size:0.78rem;color:var(--primary-light);">
      ${esc(m.name)}<button onclick="toggleGroupMember('${m.id}','')" style="background:none;border:none;color:inherit;cursor:pointer;padding:0 0 0 2px;font-size:0.9rem;">&#x2715;</button>
    </span>`
  ).join('');
}
async function createGroup() {
  const name = document.getElementById('groupName').value.trim();
  if (!name) return showToast('Group name required', 'error');
  const res = await api('POST', '/api/v1/groups', { name, description: document.getElementById('groupDesc').value.trim(), member_ids: S.groupMembers.map(m=>m.id) });
  if (res.success) { closeModal('newGroupModal'); S.groupMembers = []; await loadChats(); if(res.chat_id) openChat(res.chat_id); showToast('Group created!', 'success'); }
  else showToast(res.error || 'Error', 'error');
}

// ── Chat actions ──────────────────────────────────────────────────────────────
async function archiveChat() {
  if (!S.currentChatId) return;
  await api('POST', `/api/v1/chats/${S.currentChatId}/archive`);
  showToast('Chat archived', 'success');
  loadChats();
}
async function blockUser() {
  const chat = S.currentChatData;
  if (!chat || chat.type !== 'direct') return;
  if (!confirm('Block this user?')) return;
  await api('POST', `/api/v1/users/${chat.other_user.id}/block`);
  showToast('User blocked', 'success');
}
async function reportUser() {
  const chat = S.currentChatData;
  if (!chat || chat.type !== 'direct') return;
  const reason = prompt('Reason for report:');
  if (!reason) return;
  await api('POST', `/api/v1/users/${chat.other_user.id}/report`, { reason });
  showToast('Report submitted', 'success');
}
function exportChatHistory() {
  const msgs = document.querySelectorAll('.message-bubble');
  let text = '';
  msgs.forEach(b => { text += b.innerText.trim() + '\n'; });
  const a = document.createElement('a');
  a.href = 'data:text/plain;charset=utf-8,' + encodeURIComponent(text);
  a.download = 'chat_export.txt';
  a.click();
}
function initiateCall(type) { showToast(type + ' calls coming soon', 'info'); }

// ── Info Panel ────────────────────────────────────────────────────────────────
function toggleInfoPanel() {
  document.getElementById('infoPanel').classList.toggle('open');
}

// ── Scroll ────────────────────────────────────────────────────────────────────
function scrollToBottom(behavior='smooth') {
  const c = document.getElementById('messagesContainer');
  c.scrollTo({ top: c.scrollHeight, behavior });
}
function onMessagesScroll(el) {
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  document.getElementById('scrollBtn').classList.toggle('visible', !atBottom);
}

// ── Emoji ─────────────────────────────────────────────────────────────────────
function buildEmojiGrid() {
  document.getElementById('emojiGrid').innerHTML = EMOJIS.map(e =>
    `<button class="emoji-btn" onclick="insertEmoji('${e}')">${e}</button>`
  ).join('');
}
function toggleEmojiPanel() {
  document.getElementById('emojiPanel').classList.toggle('hidden');
  document.getElementById('attachMenu').classList.add('hidden');
}
function insertEmoji(e) {
  const inp = document.getElementById('msgInput');
  inp.value += e;
  inp.focus();
  document.getElementById('sendBtn').disabled = false;
}
function toggleAttachMenu() {
  document.getElementById('attachMenu').classList.toggle('hidden');
  document.getElementById('emojiPanel').classList.add('hidden');
}

// ── Media Viewer ──────────────────────────────────────────────────────────────
function openMedia(url, type) {
  const v = document.getElementById('mediaViewer');
  const img = document.getElementById('mediaImg');
  const vid = document.getElementById('mediaVideo');
  if (type === 'image') { img.src = url; img.style.display = 'block'; vid.style.display = 'none'; }
  else { vid.src = url; vid.style.display = 'block'; img.style.display = 'none'; }
  v.classList.remove('hidden');
}
function closeMedia() { document.getElementById('mediaViewer').classList.add('hidden'); }

// ── Chat Search ───────────────────────────────────────────────────────────────
function toggleSearch() {
  const bar = document.getElementById('chatSearchBar');
  bar.classList.toggle('hidden');
  if (!bar.classList.contains('hidden')) document.getElementById('chatSearchInput').focus();
  else document.getElementById('chatSearchInput').value = '';
}
async function searchMessages(q) {
  if (!q || q.length < 2 || !S.currentChatId) return;
  const res = await api('GET', `/api/v1/chats/${S.currentChatId}/search?q=${encodeURIComponent(q)}`);
  const msgs = res.messages || [];
  if (msgs.length) {
    const el = document.getElementById(`msg_${msgs[0].id}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ── Mobile ────────────────────────────────────────────────────────────────────
function setupMobileBack() {
  window.addEventListener('resize', () => {
    S.isMobile = window.innerWidth <= 768;
    if (!S.isMobile) {
      // Desktop: show welcome or chat
      document.getElementById('chatSidebar').classList.remove('open');
      document.getElementById('sidebarOverlay').classList.remove('active');
      if (!S.currentChatId) document.getElementById('welcomeScreen').classList.remove('hidden');
    }
  });

  // On mobile, start with sidebar visible (chats list)
  if (window.innerWidth <= 768) {
    // Make sidebar visible by default
    document.getElementById('chatSidebar').classList.add('open');
    // Hide chat window until user clicks a chat
    const win = document.getElementById('chatWindow');
    win.classList.add('hidden');
    win.style.display = 'none';
    document.getElementById('backBtn').style.display = 'flex';
  }
}

function openChatMobile(chatId) {
  if (window.innerWidth <= 768) {
    // Hide sidebar, show chat
    document.getElementById('chatSidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('active');
    const win = document.getElementById('chatWindow');
    win.classList.remove('hidden');
    win.style.display = 'flex';
    document.getElementById('backBtn').style.display = 'flex';
  }
}
function goBackToList() {
  if (window.innerWidth <= 768) {
    // Hide chat, show sidebar
    const win = document.getElementById('chatWindow');
    win.classList.add('hidden');
    win.style.display = 'none';
    document.getElementById('chatSidebar').classList.add('open');
    document.getElementById('sidebarOverlay').classList.remove('active');
    S.currentChatId = null;
    S.currentChatData = null;
    // Clear active state
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
  } else {
    document.getElementById('chatSidebar').classList.add('open');
    document.getElementById('sidebarOverlay').classList.add('active');
  }
}
function closeMobileSidebar() {
  document.getElementById('chatSidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('active');
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(t) {
  S.tab = t;
  document.querySelectorAll('.sidebar-tab').forEach(el => el.classList.remove('active'));
  const map = {all:'tabAll',unread:'tabUnread',groups:'tabGroups',archived:'tabArchived'};
  document.getElementById(map[t])?.classList.add('active');
  renderChatList();
}
function filterChats(q) { renderChatList(); }

// ── Theme ─────────────────────────────────────────────────────────────────────
async function toggleTheme() {
  const html = document.documentElement;
  const next = html.dataset.theme === 'dark' ? 'light' : 'dark';
  html.dataset.theme = next;
  localStorage.setItem('kc_theme', next);
  api('POST', '/auth/profile', { theme: next }).catch(() => {});
}

// ── Modals ────────────────────────────────────────────────────────────────────
function showNewChatModal() {
  if (S.isMobile) { document.getElementById('chatSidebar').classList.add('open'); }
  document.getElementById('newChatModal').classList.add('open');
  setTimeout(() => document.getElementById('userSearchInput').focus(), 100);
}
function showNewGroupModal() {
  S.groupMembers = [];
  document.getElementById('groupName').value = '';
  document.getElementById('groupDesc').value = '';
  document.getElementById('groupMemberResults').innerHTML = '';
  document.getElementById('selectedGroupMembers').innerHTML = '';
  document.getElementById('newGroupModal').classList.add('open');
  closeAllDropdowns();
}
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
function toggleDropdown(id) {
  const el = document.getElementById(id);
  const menu = el.querySelector('.dropdown-menu');
  const open = menu.classList.contains('open');
  closeAllDropdowns();
  if (!open) menu.classList.add('open');
}
function closeAllDropdowns() {
  document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('open'));
}

// ── Notifications ─────────────────────────────────────────────────────────────
function pushNotification(data) {
  if (document.hasFocus()) return;
  if ('Notification' in window && Notification.permission === 'granted') {
    const msg = data.message || data;
    new Notification(data.sender?.display_name || 'New Message', {
      body: msg.content || 'Sent a file',
      icon: data.sender?.avatar_url || '/static/images/default-avatar.png',
    });
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
async function api(method, url, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  if (!r.ok && r.status === 401) { location.href = '/auth/login'; throw new Error('Unauthorized'); }
  return r.json();
}

function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return 'now';
  if (diff < 3600000) return Math.floor(diff/60000) + 'm';
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  return d.toLocaleDateString([],{month:'short',day:'numeric'});
}

function relativeTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  const yesterday = new Date(now); yesterday.setDate(now.getDate()-1);
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([],{month:'short',day:'numeric'});
}

function friendlyDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return 'Today';
  const y = new Date(now); y.setDate(now.getDate()-1);
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([],{weekday:'long',month:'long',day:'numeric'});
}

function fmtBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}

function showToast(msg, type='info') {
  let c = document.getElementById('toastContainer');
  if (!c) { c = document.createElement('div'); c.id = 'toastContainer'; c.className = 'toast-container'; document.body.appendChild(c); }
  const t = document.createElement('div');
  t.className = `toast toast-${type} show`;
  const icons = {success:'&#x2713;',error:'&#x2715;',warning:'!',info:'i'};
  t.innerHTML = `<div class="toast-icon">${icons[type]||'i'}</div><span>${esc(msg)}</span><button onclick="this.parentElement.remove()">&#x2715;</button>`;
  c.appendChild(t);
  setTimeout(()=>t.classList.remove('show'), 4000);
  setTimeout(()=>t.remove(), 4600);
}

// Disable right-click & devtools
document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('keydown', e => {
  if (e.key==='F12'||(e.ctrlKey&&e.shiftKey&&['I','J','C'].includes(e.key))||(e.ctrlKey&&e.key==='U'))
    e.preventDefault();
});
