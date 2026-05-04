// SmartChat — Global JS utilities (Phase 1 skeleton)
// Full WebSocket logic added in Phase 3

const SmartChat = {
  // Format timestamp to HH:MM
  formatTime(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
  },

  // Auto-resize textarea
  autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  },

  // Scroll chat to bottom
  scrollToBottom(el) {
    if (el) el.scrollTop = el.scrollHeight;
  },

  // Show a temporary toast (in case backend messages aren't available)
  toast(msg, type = 'info') {
    const wrap = document.querySelector('.sc-toast-container');
    if (!wrap) return;
    const id = 'toast-' + Date.now();
    const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle', warning: 'exclamation-triangle' };
    wrap.insertAdjacentHTML('beforeend', `
      <div id="${id}" class="toast show align-items-center sc-toast sc-toast-${type}" role="alert">
        <div class="d-flex">
          <div class="toast-body">
            <i class="bi bi-${icons[type] || 'info-circle'} me-2"></i>${msg}
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      </div>`);
    setTimeout(() => document.getElementById(id)?.remove(), 4000);
  },

  // CSRF token helper for fetch()
  getCookie(name) {
    const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
    return v ? v[2] : null;
  },

  csrfHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-CSRFToken': this.getCookie('csrftoken'),
    };
  },
};

// Global textarea auto-resize
document.addEventListener('input', e => {
  if (e.target.classList.contains('sc-msg-input')) {
    SmartChat.autoResize(e.target);
  }
});

// OTP input auto-advance
document.addEventListener('DOMContentLoaded', () => {
  const otpInputs = document.querySelectorAll('.sc-otp-input');
  otpInputs.forEach((input, i) => {
    input.addEventListener('input', () => {
      if (input.value.length === 1 && i < otpInputs.length - 1) {
        otpInputs[i + 1].focus();
      }
      // Combine all digits into hidden field
      const hidden = document.getElementById('otp-combined');
      if (hidden) hidden.value = [...otpInputs].map(x => x.value).join('');
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !input.value && i > 0) {
        otpInputs[i - 1].focus();
      }
    });
    input.addEventListener('paste', e => {
      const text = e.clipboardData.getData('text').trim();
      if (/^\d{6}$/.test(text)) {
        e.preventDefault();
        [...text].forEach((ch, j) => { if (otpInputs[j]) otpInputs[j].value = ch; });
        const hidden = document.getElementById('otp-combined');
        if (hidden) hidden.value = text;
        otpInputs[5]?.focus();
      }
    });
  });
});
