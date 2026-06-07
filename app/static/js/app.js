/**
 * KHANDHARS CHAT - Global App JS
 * Fast PWA, theme persistence, utilities
 */
'use strict';

// Restore theme instantly (before paint)
(function(){
  const t = localStorage.getItem('kc_theme');
  if (t) document.documentElement.dataset.theme = t;
})();

// PWA Install
let deferredPWA = null;
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredPWA = e;
  const b = document.getElementById('pwaInstallBanner');
  if (b) b.classList.remove('hidden');
});
document.getElementById('pwaInstallBtn')?.addEventListener('click', async () => {
  if (!deferredPWA) return;
  deferredPWA.prompt();
  deferredPWA = null;
  document.getElementById('pwaInstallBanner')?.classList.add('hidden');
});

// Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}

// Auto dismiss flash toasts
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.toast').forEach(t => {
      t.classList.remove('show');
      setTimeout(() => t.remove(), 500);
    });
  }, 5000);
});

// Global toast function
window.showToast = function(msg, type = 'info') {
  let c = document.getElementById('toastContainer');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toastContainer';
    c.className = 'toast-container';
    document.body.appendChild(c);
  }
  const t = document.createElement('div');
  t.className = `toast toast-${type} show`;
  const icons = { success: '&#x2713;', error: '&#x2715;', warning: '!', info: 'i' };
  t.innerHTML = `<div class="toast-icon">${icons[type]||'i'}</div><span>${msg}</span><button onclick="this.parentElement.remove()">&#x2715;</button>`;
  c.appendChild(t);
  setTimeout(() => t.classList.remove('show'), 4500);
  setTimeout(() => t.remove(), 5100);
};
