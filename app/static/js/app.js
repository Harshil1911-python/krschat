/**
 * KHANDHARS CHAT - Global App JavaScript
 * PWA, theme, global utilities
 */

'use strict';

// ─── PWA Install ───────────────────────────────────────────────────────────────
let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const banner = document.getElementById('pwaInstallBanner');
  if (banner) banner.classList.remove('hidden');
});

document.getElementById('pwaInstallBtn')?.addEventListener('click', async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  deferredPrompt = null;
  document.getElementById('pwaInstallBanner')?.classList.add('hidden');
});

window.addEventListener('appinstalled', () => {
  document.getElementById('pwaInstallBanner')?.classList.add('hidden');
});

// ─── Service Worker ────────────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}

// ─── Theme Persistence ─────────────────────────────────────────────────────────
(function() {
  const saved = localStorage.getItem('kc_theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
})();

// ─── Toast Helper ──────────────────────────────────────────────────────────────
window.showToast = function(msg, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast-${type} show`;
  const icons = { success: '✓', error: '✕', warning: '!', info: 'ℹ' };
  toast.innerHTML = `<div class="toast-icon">${icons[type] || 'ℹ'}</div><span>${msg}</span><button onclick="this.parentElement.remove()">×</button>`;
  container.appendChild(toast);
  setTimeout(() => toast.classList.remove('show'), 4500);
  setTimeout(() => toast.remove(), 5000);
};

// ─── Auto dismiss flash toasts ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.toast').forEach(t => {
      t.classList.remove('show');
      setTimeout(() => t.remove(), 500);
    });
  }, 5000);
});
