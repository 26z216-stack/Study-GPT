// Shared helpers: CSRF-aware JSON POST, theme toggle, busy buttons.
(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;

  window.postJSON = async function (url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'Accept': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { data = { error: 'Unexpected server response.' }; }
    if (!res.ok && !data.error) data.error = 'Request failed (' + res.status + ').';
    return data;
  };

  window.withBusy = async function (btn, label, fn) {
    const old = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> ' + label;
    try { return await fn(); } finally { btn.disabled = false; btn.innerHTML = old; }
  };

  window.escapeHtml = function (s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  };

  const toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem('studygpt-theme', next); } catch (e) {}
    });
  }

  // Forms marked data-busy show a spinner while the (slow, AI) request runs.
  document.querySelectorAll('form[data-busy]').forEach(f => {
    f.addEventListener('submit', () => {
      const b = f.querySelector('button[type=submit], button:not([type])');
      if (b) { b.disabled = true; b.innerHTML = '<span class="spinner"></span> ' + f.dataset.busy; }
    });
  });
})();
