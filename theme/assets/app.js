/* core.js: the shared front-end engine (window.UI). Same in every app made from APP_MAKER/template;
   app-specific things live in web/app.js (brand, nav, footer) and web/pages/*.html (the pages).

   Pages:   UI.page(name, {title, nav, icon, auth, order, chrome}, mount)
              auth: null (anyone) | 'guest' (signed-out only) | 'user' | 'admin'
              nav: label for the header / phone tab bar (omit to keep it out of the menus)
              mount(view, ctx) draws into `view`; ctx = {args, me, go, api}. Return a Promise (the page
              is "ready" when it resolves) or {ready, destroy}. URLs are #name/arg1/arg2.
   Server:  UI.api(fn, ...args) -> Promise of the server function's return value. A reply of
              {ok: false, error} rejects with that message (shown as a toast unless you .catch it).
            UI.apiQuiet(fn, ...args) is the same without Anvil's loading spinner.
   Auth:    UI.auth('login'|'signup'|'reset'|'logout', {...}) -> Promise of {ok, me, message}
   Helpers: UI.esc, UI.icon, UI.toast, UI.modal, UI.confirm, UI.busy, UI.formData, UI.fmtDate, UI.ago,
            UI.store, UI.setTheme, UI.feedback, UI.go, UI.refresh
   Tests:   window.UI_READY is true when the current page has finished loading. */
(function () {
  'use strict';
  if (window.UI && window.UI.__v) return;
  var UI = window.UI = { __v: 1, pages: {}, me: null, config: { name: 'App', key: 'app', home: 'home', landing: 'landing' } };
  window.UI_READY = false;

  // The saved theme lives under the app's key ('<key>.theme'), which is only known once the app configures UI:
  // apply it again then, or a saved Light/Dark choice is ignored after every reload.
  UI.configure = function (cfg) { Object.keys(cfg).forEach(function (k) { UI.config[k] = cfg[k]; }); if (cfg.key && UI.applyTheme) UI.applyTheme(UI.theme()); };

  /* ------------------------------------------------------------------ small helpers */
  UI.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  UI.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  UI.initials = function (name) {
    var p = String(name || '?').trim().split(/\s+/);
    return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
  };
  UI.fmtDate = function (iso, opts) {
    if (!iso) return '';
    var d = iso.length <= 10 ? new Date(iso + 'T12:00:00') : new Date(iso);
    return d.toLocaleDateString(undefined, opts || { day: 'numeric', month: 'short', year: 'numeric' });
  };
  UI.fmtDateTime = function (iso) {
    return iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  };
  UI.ago = function (iso) {
    if (!iso) return '';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return 'just now';
    var steps = [[60, 'minute'], [24, 'hour'], [7, 'day'], [4.35, 'week'], [12, 'month'], [Infinity, 'year']], n = s / 60;
    for (var i = 0; i < steps.length; i++) {
      if (n < steps[i][0]) { n = Math.floor(n); return UI.plural(n, steps[i][1]) + ' ago'; }
      n = n / steps[i][0];
    }
    return '';
  };
  UI.store = {
    get: function (k, dflt) { try { var v = localStorage.getItem(UI.config.key + '.' + k); return v == null ? dflt : JSON.parse(v); } catch (e) { return dflt; } },
    set: function (k, v) { try { localStorage.setItem(UI.config.key + '.' + k, JSON.stringify(v)); } catch (e) {} }
  };
  UI.formData = function (form) {
    var out = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled) return;
      if (el.type === 'checkbox') out[el.name] = el.checked;
      else if (el.type === 'radio') { if (el.checked) out[el.name] = el.value; }
      else out[el.name] = el.value;
    });
    return out;
  };
  /* Disable a button while a Promise runs; returns the Promise. */
  UI.busy = function (btn, promise) {
    if (!btn) return promise;
    btn.disabled = true; btn.classList.add('is-busy');
    var done = function () { btn.disabled = false; btn.classList.remove('is-busy'); };
    promise.then(done, done);
    return promise;
  };

  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.7c2.2.6 3.5 2.4 3.5 5.3"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/>',
    bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    bug: '<rect x="7" y="8" width="10" height="12" rx="5"/><path d="M12 8V5M9 5.5 7.5 4M15 5.5 16.5 4M7 13H3M21 13h-4M7.5 18l-3 2M16.5 18l3 2M7.5 9.5l-3-2M16.5 9.5l3-2"/>',
    bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13"/><path d="M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    pin: '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13.5" r="3.5"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    filter: '<path d="M4 5h16l-6 7.5V19l-4 1.5v-8z"/>',
    more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>'
  };
  UI.ICONS = ICONS;
  UI.icon = function (name, cls) {
    return '<svg class="ui-ic ' + (cls || '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || ICONS.sparkle) + '</svg>';
  };

  /* ------------------------------------------------------------------ toasts, modals */
  UI.toast = function (msg, kind) {
    var box = document.querySelector('.ui-toasts');
    if (!box) { box = document.createElement('div'); box.className = 'ui ui-toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var t = document.createElement('div');
    t.className = 'ui-toast' + (kind ? ' ' + kind : '');
    t.innerHTML = (kind === 'error' ? UI.icon('info') : kind === 'ok' ? UI.icon('check') : '') + '<span>' + UI.esc(msg) + '</span>';
    box.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }, kind === 'error' ? 6500 : 3200);
  };
  UI.modal = function (html, opts) {
    opts = opts || {};
    var prev = document.activeElement;
    var wrap = document.createElement('div');
    wrap.className = 'ui ui-modal-wrap';
    wrap.innerHTML = '<div class="ui-modal' + (opts.wide ? ' wide' : '') + '" role="dialog" aria-modal="true">' +
      '<button class="ui-btn ghost icon ui-modal-x" data-close aria-label="Close">' + UI.icon('x') + '</button>' + html + '</div>';
    document.body.appendChild(wrap);
    document.documentElement.classList.add('ui-modal-open');
    function key(e) { if (e.key === 'Escape') close(); }
    function close() {
      if (!wrap.parentNode) return;
      wrap.remove(); document.removeEventListener('keydown', key);
      if (!document.querySelector('.ui-modal-wrap')) document.documentElement.classList.remove('ui-modal-open');
      if (opts.onclose) opts.onclose();
      if (prev && prev.focus) prev.focus();
    }
    document.addEventListener('keydown', key);
    wrap.addEventListener('mousedown', function (e) { if (e.target === wrap) close(); });
    wrap.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) close(); });
    var first = wrap.querySelector('input, textarea, select');
    setTimeout(function () { (first || wrap.querySelector('.ui-modal')).focus && (first || wrap.querySelector('.ui-modal')).focus(); }, 30);
    return { el: wrap.querySelector('.ui-modal'), close: close };
  };
  UI.confirm = function (o) {
    o = typeof o === 'string' ? { title: o } : (o || {});
    return new Promise(function (resolve) {
      var answered = false;
      var m = UI.modal('<h2>' + UI.esc(o.title || 'Are you sure?') + '</h2>' + (o.text ? '<p class="muted">' + UI.esc(o.text) + '</p>' : '') +
        '<div class="ui-row end" style="margin-top:20px"><button class="ui-btn ghost" data-close>' + UI.esc(o.cancel || 'Cancel') + '</button>' +
        '<button class="ui-btn ' + (o.danger ? 'danger solid' : 'primary') + '" data-ok>' + UI.esc(o.ok || 'OK') + '</button></div>',
      { onclose: function () { if (!answered) resolve(false); } });
      m.el.querySelector('[data-ok]').onclick = function () { answered = true; m.close(); resolve(true); };
    });
  };

  /* ------------------------------------------------------------------ theme */
  UI.theme = function () { return UI.store.get('theme', 'auto'); };
  UI.applyTheme = function (t) {
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
    else document.documentElement.removeAttribute('data-theme');
    var dark = t === 'dark' || (t !== 'light' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('ui-dark', !!dark);
  };
  UI.setTheme = function (t) { UI.store.set('theme', t); UI.applyTheme(t); };
  UI.applyTheme(UI.theme());
  if (window.matchMedia) {
    try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { UI.applyTheme(UI.theme()); }); } catch (e) {}
  }

  /* ------------------------------------------------------------------ server bridge */
  var bridge = null;
  function send(kind, payload) {
    if (!bridge) return Promise.reject(new Error('The app is still starting.'));
    var out;
    try { out = bridge(kind, JSON.stringify(payload || {})); } catch (e) { return Promise.reject(e); }
    return Promise.resolve(out).then(function (r) {
      r = typeof r === 'string' ? JSON.parse(r) : (r || {});
      if (r.error) {
        var err = new Error(r.error); err.uiApi = true; err.denied = !!r.denied;
        if (r.detail) console.error(kind, payload && payload.fn, r.detail);
        if (r.reload) setTimeout(function () { location.reload(); }, 2500);
        throw err;
      }
      return r.result;
    });
  }
  function apiCall(quiet, fn, args) {
    return send('call', { fn: fn, args: args, quiet: quiet }).then(function (res) {
      if (res && typeof res === 'object' && res.ok === false) {
        var err = new Error(res.error || 'That didn\'t work.'); err.uiApi = true; err.expected = true; err.result = res;
        throw err;
      }
      return res;
    });
  }
  UI.api = function (fn) { return apiCall(false, fn, Array.prototype.slice.call(arguments, 1)); };
  UI.apiQuiet = function (fn) { return apiCall(true, fn, Array.prototype.slice.call(arguments, 1)); };
  /* Errors nobody caught become a toast, so a failed action is never silent. */
  window.addEventListener('unhandledrejection', function (e) {
    if (e.reason && e.reason.uiApi) { e.preventDefault(); UI.toast(e.reason.message, 'error'); }
  });

  /* Sign in / up / out. On success it navigates: to where the visitor was heading (UI.after) or home
     after signing in, to the landing page after signing out. */
  UI.auth = function (kind, payload) {
    return send(kind, payload || {}).then(function (r) {
      if (r && r.ok === false) { var err = new Error(r.error); err.uiApi = true; err.expected = true; throw err; }
      if (r && 'me' in r && (r.me || kind === 'logout')) {
        UI.me = r.me || null;
        var target = r.me ? (UI.after || '#' + UI.config.home) : '#' + UI.config.landing;
        UI.after = null;
        if (location.hash === target) route(); else location.hash = target;
      }
      return r;
    });
  };
  /* Update the signed-in user's details (e.g. a new name) and redraw the header, without reloading the page. */
  UI.setMe = function (me) {
    UI.me = me || null;
    if (shellRoot) renderChrome(current.name);
  };

  /* ------------------------------------------------------------------ pages and routing */
  UI.page = function (name, opts, mount) {
    if (typeof opts === 'function') { mount = opts; opts = {}; }
    opts.name = name; opts.mount = mount;
    UI.pages[name] = opts;
  };
  UI.allowed = function (p) {
    if (!p) return false;
    if (p.auth === 'user') return !!UI.me;
    if (p.auth === 'admin') return !!(UI.me && UI.me.is_admin);
    if (p.auth === 'guest') return !UI.me;
    return true;
  };
  UI.navPages = function () {
    return Object.keys(UI.pages).map(function (k) { return UI.pages[k]; })
      .filter(function (p) { return p.nav && UI.allowed(p) && (!p.when || p.when()); })
      .sort(function (a, b) { return (a.order || 50) - (b.order || 50); });
  };
  UI.parseHash = function () {
    var h = (location.hash || '').replace(/^#!?\/?/, '');
    var parts = h.split('?')[0].split('/').filter(function (x) { return x !== ''; }).map(decodeURIComponent);
    return { name: parts[0] || '', args: parts.slice(1) };
  };
  UI.hashFor = function (name) {
    var args = Array.prototype.slice.call(arguments, 1).filter(function (a) { return a != null && a !== ''; });
    return '#' + [name].concat(args.map(encodeURIComponent)).join('/');
  };
  UI.go = function (name) {
    var h = UI.hashFor.apply(null, arguments);
    if (location.hash === h) route(); else location.hash = h;
  };
  UI.refresh = function () { route(); };
  UI.after = null;  // where to go after signing in

  var shellRoot = null, view = null, current = { name: null, destroy: null }, routeSeq = 0;

  function defaultPage() { return UI.me ? UI.config.home : UI.config.landing; }

  function route() {
    var r = UI.parseHash(), name = r.name || defaultPage(), p = UI.pages[name];
    if (!p) { name = defaultPage(); p = UI.pages[name]; r.args = []; }
    if (p.auth === 'guest' && UI.me) { p = UI.pages[UI.config.home]; name = UI.config.home; r.args = []; }
    if ((p.auth === 'user' || p.auth === 'admin') && !UI.me) {
      UI.after = location.hash && location.hash !== '#' ? location.hash : null;
      p = UI.pages.auth; name = 'auth'; r.args = [];
    }
    if (p.auth === 'admin' && !(UI.me && UI.me.is_admin)) {
      UI.toast('That page is for admins only.', 'error');
      p = UI.pages[UI.config.home]; name = UI.config.home; r.args = [];
    }
    var seq = ++routeSeq;
    window.UI_READY = false;
    if (current.destroy) { try { current.destroy(); } catch (e) { console.error(e); } }
    current = { name: name, args: r.args, destroy: null };
    if (shellRoot) {
      shellRoot.className = 'ui ui-shell page-' + name + (UI.me ? ' signed-in' : ' signed-out') + (p.chrome === false ? ' no-chrome' : '');
      renderChrome(name);
    }
    // A fresh element for every page, so listeners a page adds to `view` never pile up.
    var fresh = view.cloneNode(false);
    view.parentNode.replaceChild(fresh, view);
    view = fresh;
    window.scrollTo(0, 0);
    document.title = (p.title ? (typeof p.title === 'function' ? p.title(r.args) : p.title) + ' · ' : '') + UI.config.name;
    var ctx = { name: name, args: r.args, me: UI.me, go: UI.go, api: UI.api, page: p };
    var out;
    try { out = p.mount(view, ctx); } catch (e) { console.error(e); out = Promise.reject(e); }
    var ready = out && typeof out.then === 'function' ? out : (out && out.ready) || Promise.resolve();
    if (out && out.destroy) current.destroy = out.destroy;
    Promise.resolve(ready).then(function () { if (seq === routeSeq) window.UI_READY = true; },
      function (e) {
        if (seq !== routeSeq) return;
        console.error(e);
        if (!view.innerHTML) view.innerHTML = '<div class="ui-wrap"><div class="ui-empty">' + UI.icon('info') +
          '<h3>This page didn\'t load</h3><p class="muted">' + UI.esc(e && e.message || 'Something went wrong.') + '</p>' +
          '<button class="ui-btn" onclick="UI.refresh()">Try again</button></div></div>';
        window.UI_READY = true;
      });
  }
  UI.current = function () { return current; };

  /* The shell's parts come from web/app.js: UI.shell = {header(me, active), footer(me), tabbar(me, active)} */
  function renderChrome(active) {
    var S = UI.shell || {};
    var hd = shellRoot.querySelector('[data-ui-header]'), ft = shellRoot.querySelector('[data-ui-footer]'), tb = shellRoot.querySelector('[data-ui-tabbar]');
    if (hd) hd.innerHTML = S.header ? S.header(UI.me, active) : '';
    if (ft) ft.innerHTML = S.footer ? S.footer(UI.me, active) : '';
    if (tb) tb.innerHTML = S.tabbar ? S.tabbar(UI.me, active) : '';
  }
  UI.renderChrome = function () { if (shellRoot) renderChrome(current.name); };

  /* Called by client_code/Main.py (and by the local harness) once the page is up. */
  UI.start = function (node, bridgeFn, bootJson) {
    bridge = bridgeFn;
    var boot = typeof bootJson === 'string' ? JSON.parse(bootJson || '{}') : (bootJson || {});
    UI.me = boot.me || null;
    var host = node && node.matches && node.matches('[data-ui-app]') ? node : (node && node.querySelector('[data-ui-app]')) || node || document.body;
    host.innerHTML = '<div class="ui ui-shell">' +
      '<header class="ui-header" data-ui-header></header>' +
      '<main class="ui-main" data-ui-view></main>' +
      '<footer class="ui-footer" data-ui-footer></footer>' +
      '<nav class="ui-tabbar" data-ui-tabbar aria-label="Main"></nav></div>';
    shellRoot = host.firstChild;
    view = host.querySelector('[data-ui-view]');
    if (UI.shell && UI.shell.wire) UI.shell.wire(shellRoot);
    window.addEventListener('hashchange', route);
    route();
  };

  /* ------------------------------------------------------------------ feedback (footer + menu)
     All feedback goes to Prepsto. The widget tag in head.html (data-prepsto="CODE") slides its panel in;
     any [data-feedback] or [data-prepsto-open] element opens it. If the widget hasn't loaded, the panel opens in a new tab.
     There is no in-app feedback form any more: Admin -> Feedback only lists older messages (and app requests). */
  UI.feedback = function () {
    if (window.Prepsto && window.Prepsto.open) { window.Prepsto.open(); return; }
    var tag = document.querySelector('script[data-prepsto]');
    var code = tag && tag.getAttribute('data-prepsto');
    if (code && code.indexOf('__') !== 0) window.open('https://prepsto.com/#f/' + encodeURIComponent(code), '_blank', 'noopener');
    else UI.toast('Feedback is not set up yet.', 'error');
  };

  /* Shared clicks: [data-go="page/arg"], [data-feedback], [data-theme-set] anywhere in the app. */
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-go],[data-feedback],[data-theme-set]');
    if (!el) return;
    if (el.hasAttribute('data-go')) { e.preventDefault(); UI.go.apply(null, el.getAttribute('data-go').split('/')); }
    else if (el.hasAttribute('data-feedback')) { e.preventDefault(); UI.feedback(el.getAttribute('data-feedback') || null); }
    else if (el.hasAttribute('data-theme-set')) { e.preventDefault(); UI.setTheme(el.getAttribute('data-theme-set')); if (UI.shell && UI.shell.onTheme) UI.shell.onTheme(); }
  });
})();


/* app.js: this app's identity and frame: name, header, footer, phone tab bar.
   Pages live in web/pages/*.html. The engine (window.UI) is web/core.js. */
(function () {
  'use strict';
  UI.configure({
    name: 'Service Request',
    key: 'servicerequest',          // prefix for this app's browser storage
    tagline: 'Neighbourhood bounties from $20. Cash or e-Transfer, no fees, no middleman.',
    home: 'board',               // first page after signing in
    landing: 'landing'           // first page for visitors who aren't signed in
  });

  var esc = UI.esc;

  function brand() {
    return '<a class="ui-brand" href="#" data-go="' + (UI.me ? UI.config.home : UI.config.landing) + '" aria-label="' + esc(UI.config.name) + ' home">' +
      '<img src="_/theme/icon.svg" alt="" width="32" height="32"><span>' + esc(UI.config.name) + '</span></a>';
  }

  function themeSwitch() {
    var t = UI.theme();
    return '<div class="ui-seg" role="group" aria-label="Appearance">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
      return '<button type="button" data-theme-set="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
    }).join('') + '</div>';
  }

  function userMenu(me) {
    return '<div class="ui-menu" data-menu hidden>' +
      '<div class="ui-menu-head"><strong>' + esc(me.name) + '</strong><span class="muted small">' + esc(me.email) + '</span></div>' +
      '<a href="#profile" data-go="profile">' + UI.icon('user') + 'Your profile</a>' +
      '<a href="#neighbour/' + esc(me.id) + '" data-go="neighbour/' + esc(me.id) + '">' + UI.icon('star') + 'Your public page</a>' +
      '<a href="#rules" data-go="rules">' + UI.icon('shield') + 'Rules &amp; safety</a>' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<div class="ui-menu-block"><span class="small muted">Appearance</span>' + themeSwitch() + '</div>' +
      '<button type="button" data-feedback>' + UI.icon('chat') + 'Submit feedback</button>' +
      '<button type="button" data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms</button>' +
      '<button type="button" data-signout>' + UI.icon('logout') + 'Sign out</button></div>';
  }

  UI.shell = {
    header: function (me, active) {
      var nav = UI.navPages();
      return '<div class="ui-header-in">' + brand() +
        (me ? '<nav class="ui-nav" aria-label="Main">' + nav.map(function (p) {
          return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
        }).join('') + '</nav>' : '<nav class="ui-nav" aria-label="Main">' +
          '<a href="#board" class="' + (active === 'board' ? 'on' : '') + '">' + UI.icon('search') + '<span>Browse bounties</span></a>' +
          '<a href="#rules" class="' + (active === 'rules' ? 'on' : '') + '">' + UI.icon('shield') + '<span>How it stays safe</span></a></nav>') +
        '<div class="ui-header-right">' +
        (me ? '<button type="button" class="ui-avatar-btn" data-menu-toggle aria-label="Your account" aria-haspopup="true">' + esc(UI.initials(me.name)) + '</button>' + userMenu(me)
          : (active === 'auth' ? '' : '<a class="ui-btn ghost" href="#auth" data-go="auth">Sign in</a><a class="ui-btn primary" href="#auth/signup" data-go="auth/signup">Get started</a>')) +
        '</div></div>';
    },
    footer: function (me) {
      return '<div class="ui-footer-in"><div class="ui-footer-brand">' + brand() + '<p class="muted small">' + esc(UI.config.tagline) + '</p></div>' +
        '<div class="ui-footer-links">' +
        '<a href="#landing" data-go="landing">About</a>' +
        '<a href="#board" data-go="board">Browse bounties</a>' +
        '<a href="#rules" data-go="rules">Rules &amp; safety</a>' +
        '<a href="https://prepsto.com/#f/u2cum5r" target="_blank" rel="noopener" data-prepsto-open>Submit feedback</a>' +
        '<button type="button" data-lk-open="overview">Privacy &amp; Terms</button>' +
        '</div><p class="ui-footer-legal small muted">© ' + new Date().getFullYear() + ' ' + esc(UI.config.name) + '</p></div>';
    },
    tabbar: function (me, active) {
      var nav = UI.navPages();
      if (!me || nav.length < 2) return '';
      return nav.slice(0, 4).map(function (p) {
        return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
      }).join('') + '<a href="#profile" class="' + (active === 'profile' ? 'on' : '') + '">' + UI.icon('user') + '<span>You</span></a>';
    },
    wire: function (root) {
      root.addEventListener('click', function (e) {
        var t = e.target.closest('[data-menu-toggle]');
        var menu = root.querySelector('[data-menu]');
        if (t && menu) { menu.hidden = !menu.hidden; t.setAttribute('aria-expanded', String(!menu.hidden)); return; }
        if (e.target.closest('[data-signout]')) { UI.auth('logout').then(function () { UI.toast('Signed out. See you soon!'); }); }
        if (menu && !menu.hidden && !e.target.closest('[data-menu] .ui-seg')) menu.hidden = true;
      });
      document.addEventListener('keydown', function (e) {
        var menu = root.querySelector('[data-menu]');
        if (e.key === 'Escape' && menu) menu.hidden = true;
      });
    },
    onTheme: function () {  // redraw the menu's Auto/Light/Dark buttons and keep the menu open
      var menu = document.querySelector('[data-menu]'), open = menu && !menu.hidden;
      UI.renderChrome();
      if (open) document.querySelector('[data-menu]').hidden = false;
    }
  };
})();


/* ===== _sr.html ===== */
(function () {
  'use strict';
  var esc = UI.esc;
  var SR = window.SR = {};
  SR.HOME = { lat: 45.5088, lng: -73.5878 };  // Montréal: where maps open when we know nothing else

  /* ---------------------------------------------------------------- extra icons */
  var more = {
    leaf: '<path d="M5 19c8 0 14-6 14-15C10 4 5 9 5 15v4z"/><path d="M5 19 14 10"/>',
    snow: '<path d="M12 2v20M4.5 6.5l15 11M19.5 6.5l-15 11"/><path d="M9.5 3.5 12 6l2.5-2.5M9.5 20.5 12 18l2.5 2.5"/>',
    bin: '<path d="M4 7h16M9 7V4h6v3M6 7l1.2 13h9.6L18 7"/><path d="M10 11v6M14 11v6"/>',
    box: '<path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z"/><path d="M3 7.5 12 12l9-4.5M12 12v9"/>',
    spray: '<path d="M8 10h6v11H8z"/><path d="M9 10V7h4v3M13 7h3M18 4h.01M20 6h.01M18 8h.01M16 4.5l1.5-1"/>',
    bag: '<path d="M5 8h14l-1 13H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    paw: '<circle cx="6.5" cy="10" r="2"/><circle cx="17.5" cy="10" r="2"/><circle cx="9.5" cy="5.5" r="2"/><circle cx="14.5" cy="5.5" r="2"/><path d="M12 12c-3 0-5.5 3.5-5.5 6 0 1.7 1.5 2.5 3 2l2.5-.8 2.5.8c1.5.5 3-.3 3-2 0-2.5-2.5-6-5.5-6z"/>',
    wrench: '<path d="M14.5 5.5a4 4 0 0 0 4.8 5.2L21 12.5 12.5 21l-1.8-1.7a4 4 0 0 0-5.2-4.8L3 12l3-3 2.5 2.5L11.5 8.5 9 6l3-3z"/>',
    tag: '<path d="M3 12 11 4h9v9l-8 8z"/><circle cx="16" cy="8" r="1.6"/>',
    wallet: '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M16 15h2"/><path d="M6 6l9-3 1.5 3"/>',
    clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 10h6M9 14h6M9 18h4"/>',
    flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
    cash: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.5v5M18 9.5v5"/>',
    bank: '<path d="M3 9.5 12 4l9 5.5H3z"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>',
    hand: '<path d="M7 11V6.5a1.5 1.5 0 0 1 3 0V11M10 10V4.5a1.5 1.5 0 0 1 3 0V10M13 10V5.5a1.5 1.5 0 0 1 3 0V12M16 9.5a1.5 1.5 0 0 1 3 0V15a6 6 0 0 1-6 6h-1.5a6 6 0 0 1-4.6-2.2L4 15.5a1.5 1.5 0 0 1 2.3-2L7 14.5V11"/>',
    eyeoff: '<path d="M3 3l18 18"/><path d="M10.6 6.1A9.7 9.7 0 0 1 12 6c5 0 8.5 4.5 9.5 6-.5.8-1.6 2.3-3.2 3.6M6.4 7.9C4.6 9.2 3.3 10.9 2.5 12c1 1.5 4.5 6 9.5 6 1.6 0 3-.4 4.3-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    route: '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5"/>',
    bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    gift: '<rect x="3" y="8" width="18" height="5" rx="1"/><path d="M5 13v8h14v-8M12 8v13M12 8c-1.5-3-5.5-4-6-1.5S9 8 12 8zM12 8c1.5-3 5.5-4 6-1.5S15 8 12 8z"/>',
    ruler: '<path d="M3 17 17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>',
    send: '<path d="M21 3 3 10.5l7 2.5 2.5 7z"/><path d="M21 3 10 13"/>'
  };
  Object.keys(more).forEach(function (k) { UI.ICONS[k] = more[k]; });

  /* ---------------------------------------------------------------- catalogue */
  var catP = null, CAT = null;
  SR.catalog = function () {
    if (CAT) return Promise.resolve(CAT);
    if (!catP) catP = UI.api('get_catalog').then(function (c) {
      CAT = c;
      c.byKey = {}; c.tasks.forEach(function (t) { c.byKey[t.key] = t; });
      c.catByKey = {}; c.categories.forEach(function (x) { c.catByKey[x.key] = x; });
      return c;
    }, function (e) { catP = null; throw e; });
    return catP;
  };
  SR.task = function (key) { return (CAT && CAT.byKey[key]) || { key: key, name: 'Neighbourly task', cat: 'other', checklist: [], prices: [20, 40, 70] }; };
  SR.cat = function (key) { return (CAT && CAT.catByKey[key]) || { key: 'other', name: 'Something else', icon: 'sparkle' }; };
  SR.inSeason = function (t) { return t.months.indexOf(new Date().getMonth() + 1) >= 0 && t.months.length < 12; };
  SR.ti = function (taskKey, cls) {
    var t = SR.task(taskKey), c = SR.cat(t.cat);
    return '<span class="sr-ti c-' + esc(c.key) + ' ' + (cls || '') + '" title="' + esc(c.name) + '">' + UI.icon(c.icon) + '</span>';
  };

  /* ---------------------------------------------------------------- formatting */
  SR.money = function (n) {
    n = Number(n || 0);
    var whole = Math.round(n) === n;
    return '$' + n.toLocaleString('en-CA', { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 });
  };
  SR.tag = function (b, cls) {
    return '<span class="sr-tag ' + (cls || '') + '"><b>' + SR.money(b.base) + '</b>' +
      (b.bonus ? '<i>+' + SR.money(b.bonus) + ' at ' + (b.bar || 80) + '%</i>' : '<i>bounty</i>') + '</span>';
  };
  SR.STATUS = { review: 'In review', open: 'Open', assigned: 'Booked', submitted: 'Proof sent', validated: 'Payment due', paid: 'Paid',
                done: 'Done', disputed: 'Dispute', cancelled: 'Cancelled', rejected: 'Not approved', expired: 'Expired', removed: 'Removed' };
  SR.stamp = function (status) { return '<span class="sr-stamp ' + esc(status) + '">' + esc(SR.STATUS[status] || status) + '</span>'; };
  SR.PAY = { cash: 'Cash', etransfer: 'e-Transfer', either: 'Cash or e-Transfer' };
  SR.payIcon = function (p) { return UI.icon(p === 'cash' ? 'cash' : p === 'etransfer' ? 'bank' : 'wallet'); };
  SR.dist = function (km) {
    if (km == null) return '';
    return km < 1 ? Math.max(100, Math.round(km * 10) * 100) + ' m' : (km < 10 ? km.toFixed(1) : Math.round(km)) + ' km';
  };
  SR.when = function (b) {
    var parts = [];
    if (b.when_date) parts.push(UI.fmtDate(b.when_date, { weekday: 'short', day: 'numeric', month: 'short' }));
    if (b.when_note) parts.push(b.when_note);
    return parts.join(' · ') || 'Flexible';
  };
  SR.stars = function (n, total) {
    total = total || 5;
    var out = '<span class="sr-stars" aria-label="' + (n || 0) + ' out of 5 stars">';
    for (var i = 1; i <= total; i++) out += '<span class="' + (i <= Math.round(n || 0) ? '' : 'off') + '">' + UI.icon('star') + '</span>';
    return out + '</span>';
  };
  SR.rating = function (rec) {
    return rec && rec.rating ? '<span class="sr-star">★ ' + Number(rec.rating).toFixed(1) + '</span> <span class="faint">(' + rec.reviews + ')</span>' : '<span class="faint">New</span>';
  };
  SR.payRecord = function (rec) {
    if (!rec) return '';
    if (!rec.paid) return 'No payments yet';
    return 'Pays within 2 days: <b>' + rec.paid_fast + '/' + rec.paid + '</b>' + (rec.bonus_jobs ? ' · Bonus paid <b>' + rec.bonus_paid + '/' + rec.bonus_jobs + '</b>' : '');
  };
  SR.photo = function (key, thumb) {
    return key ? (window.APP_API || '_/api').replace(/\/$/, '') + '/photo?k=' + encodeURIComponent(key) + (thumb ? '&s=t' : '') : '';
  };

  /* ---------------------------------------------------------------- the board card */
  SR.card = function (b) {
    var p = b.poster || {};
    return '<a class="sr-card" href="#bounty/' + esc(b.id) + '" data-go="bounty/' + esc(b.id) + '" data-card="' + esc(b.id) + '">' +
      SR.ti(b.task) +
      '<div><h3>' + esc(b.title) + '</h3><div class="meta">' +
        '<span>' + UI.icon('pin') + esc(b.area) + (b.dist != null ? ' · ' + SR.dist(b.dist) : '') + '</span>' +
        '<span>' + UI.icon('calendar') + esc(SR.when(b)) + '</span>' +
        '<span>' + SR.payIcon(b.pay) + esc(SR.PAY[b.pay] || '') + '</span>' +
        (b.vehicle ? '<span>' + UI.icon('route') + 'Needs a vehicle</span>' : '') + '</div>' +
        '<div class="who"><span class="sr-mini">' + esc(UI.initials(p.name)) + '</span><b>' + esc(p.name) + '</b>' + SR.rating(p.record) +
        (p.record && p.record.paid >= 3 && p.record.paid_fast === p.record.paid ? '<span class="ui-badge good">' + UI.icon('bolt') + 'Pays fast</span>' : '') +
        (b.demo ? '<span class="ui-badge">Demo</span>' : '') + (b.mine ? '<span class="ui-badge brand">Yours</span>' : '') + '</div></div>' +
      '<div class="right">' + SR.tag(b) + (b.cover ? '<img class="ph" src="' + esc(SR.photo(b.cover, true)) + '" alt="" loading="lazy">' : '') +
        '<span class="offers">' + (b.offers ? UI.plural(b.offers, 'offer') : 'No offers yet') + '</span></div></a>';
  };

  /* ---------------------------------------------------------------- maps */
  var leafletP = null;
  SR.leaflet = function () {
    if (window.L && window.L.map) return Promise.resolve(window.L);
    if (leafletP) return leafletP;
    leafletP = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      s.onload = function () { window.L ? resolve(window.L) : reject(new Error('no map')); };
      s.onerror = function () { leafletP = null; reject(new Error('The map couldn\'t load.')); };
      document.head.appendChild(s);
      setTimeout(function () { if (!window.L) { leafletP = null; reject(new Error('The map is taking too long to load.')); } }, 12000);
    });
    return leafletP;
  };
  /* OpenStreetMap's own tiles (light use, with the browser's normal Referer). Dark mode inverts them in CSS. */
  SR.tiles = function (L, map) {
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
  };
  SR.pricePin = function (L, b, cls) {
    return L.divIcon({ className: '', iconSize: [0, 0], iconAnchor: [0, 0],
      html: '<span class="sr-pin ' + (cls || '') + '" data-pin="' + esc(b.id || '') + '">' + esc(b.label || SR.money(b.base + (b.bonus || 0))) + '</span>' });
  };
  function areaName(a) {
    if (!a) return '';
    var local = a.neighbourhood || a.suburb || a.quarter || a.city_district || a.borough || '';
    var town = a.city || a.town || a.village || a.municipality || a.county || '';
    return [local, town].filter(Boolean).filter(function (v, i, all) { return all.indexOf(v) === i; }).join(', ').slice(0, 60);
  }
  /* Nominatim: only on a tap (search or pin), never while typing, as its usage policy asks. */
  SR.reverse = function (lat, lng) {
    return fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=17&addressdetails=1&lat=' + lat + '&lon=' + lng)
      .then(function (r) { return r.json(); }).then(function (j) {
        var a = j.address || {};
        return { area: areaName(a), street: [a.house_number, a.road].filter(Boolean).join(' ') };
      }).catch(function () { return { area: '', street: '' }; });
  };
  SR.search = function (text) {
    return fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&countrycodes=ca&limit=5&q=' + encodeURIComponent(text))
      .then(function (r) { return r.json(); });
  };

  /* The spot picker: a map with a pin, "use my location", a place search and the area name.
     Resolves {lat, lng, label, street} or null when closed. */
  SR.pickSpot = function (o) {
    o = o || {};
    return new Promise(function (resolve) {
      var done = false, pos = o.lat != null ? { lat: o.lat, lng: o.lng } : null, map = null, marker = null, L = null, autoLabel = !o.label, street = '';
      var m = UI.modal('<h2>' + esc(o.title || 'Where are you?') + '</h2>' + (o.text ? '<p class="muted">' + esc(o.text) + '</p>' : '') +
        '<div class="ui-row sr-spot-tools"><button type="button" class="ui-btn sm primary" data-locate>' + UI.icon('pin') + 'Use my location</button>' +
        '<form class="sr-spot-search" data-find><input type="search" name="q" placeholder="Or search a street or place" aria-label="Search a place">' +
        '<button class="ui-btn sm icon" type="submit" aria-label="Search">' + UI.icon('search') + '</button></form></div>' +
        '<div class="sr-spot-results" data-results hidden></div>' +
        '<div class="sr-map" data-map style="height:300px"><div class="sr-map-msg">Loading the map…</div></div>' +
        '<p class="ui-hint">' + esc(o.hint || 'Tap the map to move the pin.') + '</p>' +
        '<label class="ui-field"><span>' + esc(o.labelTitle || 'Name of the area') + '</span><input type="text" name="label" maxlength="60" placeholder="e.g. Rosemont, Montréal" value="' + esc(o.label || '') + '"></label>' +
        '<div data-err class="ui-error" hidden style="margin-top:12px"></div>' +
        '<div class="ui-row end" style="margin-top:16px"><button type="button" class="ui-btn ghost" data-close>Cancel</button>' +
        '<button type="button" class="ui-btn primary" data-ok>' + esc(o.ok || 'Save') + '</button></div>',
      { wide: true, onclose: function () { if (!done) resolve(null); } });
      var el = m.el, labelInput = el.querySelector('[name=label]');
      labelInput.addEventListener('input', function () { autoLabel = !labelInput.value.trim(); });
      function err(msg) { var b = el.querySelector('[data-err]'); b.textContent = msg || ''; b.hidden = !msg; }
      function setPos(p, zoom, lookUp) {
        pos = { lat: +p.lat, lng: +p.lng };
        err('');
        if (map) {
          if (!marker) marker = L.marker([pos.lat, pos.lng], { icon: SR.pricePin(L, { label: o.pinLabel || 'Here' }, 'me'), draggable: true }).addTo(map)
            .on('dragend', function (ev) { var ll = ev.target.getLatLng(); setPos({ lat: ll.lat, lng: ll.lng }, null, true); });
          else marker.setLatLng([pos.lat, pos.lng]);
          if (zoom) map.setView([pos.lat, pos.lng], zoom, { animate: false });
        }
        if (lookUp) SR.reverse(pos.lat, pos.lng).then(function (r) { street = r.street; if (r.area && autoLabel) labelInput.value = r.area; });
      }
      SR.leaflet().then(function (LL) {
        L = LL;
        var box = el.querySelector('[data-map]');
        box.innerHTML = '';
        map = L.map(box, { scrollWheelZoom: true }).setView([pos ? pos.lat : SR.HOME.lat, pos ? pos.lng : SR.HOME.lng], pos ? 15 : 11);
        SR.tiles(L, map);
        map.on('click', function (ev) { setPos(ev.latlng, null, true); });
        if (pos) setPos(pos);
        setTimeout(function () { map.invalidateSize(); }, 120);
      }, function (e) {
        el.querySelector('[data-map]').innerHTML = '<div class="sr-map-msg">' + esc(e.message) + ' Use your location or search a place instead.</div>';
      });
      el.addEventListener('click', function (e) {
        if (e.target.closest('[data-locate]')) {
          var b = e.target.closest('[data-locate]');
          if (!navigator.geolocation) { err('This browser can\'t share its location. Search a place instead.'); return; }
          UI.busy(b, new Promise(function (res) {
            navigator.geolocation.getCurrentPosition(function (p) {
              setPos({ lat: p.coords.latitude, lng: p.coords.longitude }, 16, true); res();
            }, function () { err('We couldn\'t get your location. Allow it in your browser, or search a place.'); res(); },
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 600000 });
          }));
          return;
        }
        var r = e.target.closest('[data-pick]');
        if (r) {
          var it = JSON.parse(r.getAttribute('data-pick'));
          if (autoLabel || !labelInput.value.trim()) { labelInput.value = it.name; autoLabel = true; }
          street = it.street || '';
          setPos(it, 16, false);
          el.querySelector('[data-results]').hidden = true;
          return;
        }
        if (e.target.closest('[data-ok]')) {
          var label = labelInput.value.trim();
          if (!pos) { err('Put a pin on the map first (tap the map, use your location, or search).'); return; }
          if (label.length < 2) { err('Give the area a name, like a neighbourhood.'); labelInput.focus(); return; }
          done = true; m.close(); resolve({ lat: pos.lat, lng: pos.lng, label: label, street: street });
        }
      });
      el.querySelector('[data-find]').addEventListener('submit', function (e) {
        e.preventDefault();
        var text = e.target.q.value.trim(), box = el.querySelector('[data-results]');
        if (text.length < 2) return;
        UI.busy(e.target.querySelector('button'), SR.search(text).then(function (list) {
          box.hidden = false;
          box.innerHTML = list.length ? list.map(function (p) {
            var a = p.address || {};
            var name = areaName(a) || (p.display_name || '').split(',').slice(0, 2).join(',');
            var st = [a.house_number, a.road].filter(Boolean).join(' ');
            return '<button type="button" data-pick="' + esc(JSON.stringify({ lat: +p.lat, lng: +p.lon, name: name.slice(0, 60), street: st })) + '">' + esc(p.display_name) + '</button>';
          }).join('') : '<p class="muted small" style="margin:0">No place found. Try another spelling, or tap the map.</p>';
        }, function () { box.hidden = false; box.innerHTML = '<p class="muted small" style="margin:0">Search isn\'t working right now. Tap the map instead.</p>'; }));
      });
    });
  };
  SR.editArea = function () {
    var s = UI.me && UI.me.spot;
    return SR.pickSpot({ title: 'Where do you help out?', ok: 'Save my area', pinLabel: 'You',
      text: 'Bounties are sorted by distance from here. Others only see the area name, never your address.',
      label: s && s.label, lat: s && s.lat, lng: s && s.lng }).then(function (p) {
      if (!p) return null;
      return UI.api('set_spot', p.lat, p.lng, p.label).then(function (r) { UI.setMe(r.me); UI.toast('Area saved: ' + p.label, 'ok'); return r.me; });
    });
  };

  /* ---------------------------------------------------------------- photos: shrink on the phone, upload right away */
  function drawJpeg(img, max, quality) {
    var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height, s = Math.min(1, max / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
    var g = c.getContext('2d');
    g.fillStyle = '#ffffff'; g.fillRect(0, 0, c.width, c.height);
    g.imageSmoothingQuality = 'high';
    g.drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', quality);
  }
  SR.shrink = function (file) {
    return new Promise(function (resolve, reject) {
      if (!file || !/^image\//.test(file.type || 'image/')) { reject(new Error('That file isn\'t a picture.')); return; }
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        try { var full = drawJpeg(img, 1600, 0.82), thumb = drawJpeg(img, 480, 0.74); URL.revokeObjectURL(url); resolve({ full: full, thumb: thumb }); }
        catch (e) { reject(new Error('That picture couldn\'t be read.')); }
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('That picture couldn\'t be read. Try a JPEG or PNG.')); };
      img.src = url;
    });
  };
  /* A photo picker inside `box`: tiles + an "add" tile. Returns {keys(), busy()} */
  SR.uploader = function (box, max, label) {
    var tiles = [], seq = 0;
    function draw() {
      box.innerHTML = '<div class="sr-up">' + tiles.map(function (t) {
        return '<div class="tile' + (t.key ? '' : ' busy') + '" data-tile="' + t.id + '"><img src="' + esc(t.src) + '" alt="">' +
          '<button type="button" data-rm="' + t.id + '" aria-label="Remove photo">' + UI.icon('x') + '</button></div>';
      }).join('') + (tiles.length < max ? '<label class="add">' + UI.icon('camera') + '<span>' + esc(label || 'Add photo') + '</span>' +
        '<input type="file" accept="image/*" multiple data-file></label>' : '') + '</div>';
    }
    box.addEventListener('change', function (e) {
      if (!e.target.matches('[data-file]')) return;
      Array.prototype.slice.call(e.target.files || [], 0, max - tiles.length).forEach(function (file) {
        var t = { id: 't' + (++seq), key: null, src: '' };
        tiles.push(t);
        t.ready = SR.shrink(file).then(function (d) {
          t.src = d.thumb; draw();
          return UI.apiQuiet('upload_photo', d.full, d.thumb);
        }).then(function (r) { t.key = r.key; draw(); }, function (err) {
          tiles = tiles.filter(function (x) { return x !== t; }); draw(); UI.toast(err.message, 'error');
        });
      });
      draw();
    });
    box.addEventListener('click', function (e) {
      var rm = e.target.closest('[data-rm]');
      if (rm) { e.preventDefault(); tiles = tiles.filter(function (x) { return x.id !== rm.getAttribute('data-rm'); }); draw(); }
    });
    draw();
    return {
      keys: function () { return tiles.filter(function (t) { return t.key; }).map(function (t) { return t.key; }); },
      busy: function () { return tiles.some(function (t) { return !t.key; }); }
    };
  };
  SR.zoom = function (key) { UI.modal('<div class="sr-zoom"><img src="' + esc(SR.photo(key)) + '" alt="Photo"></div>', { wide: true }); };
  document.addEventListener('click', function (e) {
    var z = e.target.closest && e.target.closest('[data-zoom]');
    if (z) { e.preventDefault(); SR.zoom(z.getAttribute('data-zoom')); }
  });

  /* ---------------------------------------------------------------- confetti, copy, report */
  SR.confetti = function () {
    var box = document.createElement('div'), colors = ['#ffd400', '#111111', '#ffffff', '#ffd400', '#ff8a3d'];
    box.className = 'sr-confetti';
    for (var i = 0; i < 80; i++) {
      var p = document.createElement('i');
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[i % colors.length];
      p.style.animationDelay = (Math.random() * .4) + 's';
      p.style.setProperty('--dx', (Math.random() * 200 - 100) + 'px');
      p.style.setProperty('--r', (Math.random() * 900 - 450) + 'deg');
      box.appendChild(p);
    }
    document.body.appendChild(box);
    setTimeout(function () { box.remove(); }, 3200);
  };
  SR.copy = function (text, what) {
    var done = function () { UI.toast((what || 'Copied') + ' copied', 'ok'); };
    if (navigator.clipboard) return navigator.clipboard.writeText(text).then(done, function () { UI.toast('Select it and copy by hand.'); });
    UI.toast('Select it and copy by hand.');
  };
  SR.report = function (o) {
    if (!UI.me) { UI.go('auth'); return; }
    var kinds = [['scam', 'Looks like a scam'], ['unsafe', 'Unsafe or not allowed'], ['not_paid', 'Didn\'t pay'], ['no_show', 'Didn\'t show up'],
                 ['rude', 'Rude or harassing'], ['fake', 'Fake bounty or profile'], ['other', 'Something else']];
    var m = UI.modal('<h2>' + UI.icon('flag') + ' Report ' + esc(o.what || 'this') + '</h2><p class="muted">A moderator reads every report. Three reports take a bounty off the board until it\'s checked.</p>' +
      '<form class="ui-stack" data-rep><div class="ui-choices">' + kinds.map(function (k, i) {
        return '<label class="ui-choice"><input type="radio" name="kind" value="' + k[0] + '"' + (i ? '' : ' checked') + '><span>' + esc(k[1]) + '</span></label>';
      }).join('') + '</div><label class="ui-field"><span>What happened?</span><textarea name="text" required minlength="10" maxlength="1000" placeholder="Facts help: what was said or asked, when."></textarea></label>' +
      '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('flag') + 'Send report</button></div></form>');
    m.el.querySelector('[data-rep]').addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(e.target);
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('report', v.kind, v.text, o.bounty || null, o.user || null)).then(function (r) {
        m.close(); UI.toast(r.hidden ? 'Thanks. It\'s off the board until a moderator checks it.' : 'Thanks. A moderator will look at it.', 'ok');
      });
    });
  };
})();

/* ===== admin.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['overview', 'Overview', 'grid'], ['queue', 'Review queue', 'flag'], ['safety', 'Trust & safety', 'shield'], ['bounties', 'Bounties', 'tag'],
              ['feedback', 'Feedback', 'inbox'], ['users', 'Users', 'users'], ['demo', 'Demo data', 'database']];

  UI.page('admin', { title: 'Admin', auth: 'admin' }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'overview';
    var fbFilter = 'new';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Admin</h1><p class="muted">Only admins see this page.</p></div></div>' +
      '<nav class="ui-tabs">' + TABS.map(function (t) {
        return '<a href="#admin/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + '</a>';
      }).join('') + '</nav><div data-body><div class="ui-skel"></div></div></div>';
    var body = view.querySelector('[data-body]');

    function overview() {
      return UI.api('admin_overview').then(function (d) {
        var stat = function (n, label, go) { return '<a class="ui-card ui-stat" href="#admin/' + go + '" style="text-decoration:none;color:inherit"><b>' + n + '</b><span>' + label + '</span></a>'; };
        var bs = d.bounties;
        body.innerHTML = '<div class="ad-stats">' + stat(bs.review, 'waiting for review', 'queue') + stat(bs.disputed + ' · ' + d.reports_open, 'disputes · open reports', 'safety') +
          stat(bs.open, 'open bounties', 'bounties') + stat(bs.assigned + bs.submitted, 'jobs under way', 'bounties') + stat(bs.validated + bs.paid, 'payments pending', 'bounties') +
          stat(bs.done, 'jobs done', 'bounties') + stat(SR.money(d.settled), 'settled (real jobs)', 'bounties') +
          stat(d.users, 'people signed up', 'users') + stat(d.feedback_new, 'new feedback', 'feedback') + '</div>' +
          '<p class="muted small" style="margin-top:18px">Demo data is <b>' + esc(d.demo.state) + '</b> (' + d.demo.counts.users + ' demo people). Manage it in the Demo data tab.</p>';
      });
    }

    function feedback() {
      return UI.api('list_feedback', null).then(function (d) {
        var items = d.items.filter(function (i) { return fbFilter === 'all' || i.status === fbFilter; });
        body.innerHTML = '<div class="ui-row" style="margin-bottom:16px"><div class="ui-seg">' + [['new', 'New'], ['read', 'Read'], ['done', 'Done'], ['all', 'All']].map(function (f) {
          var n = f[0] === 'all' ? d.items.length : d.counts[f[0]];
          return '<button data-filter="' + f[0] + '" class="' + (fbFilter === f[0] ? 'on' : '') + '">' + f[1] + ' (' + n + ')</button>';
        }).join('') + '</div></div>' +
          (items.length ? '<div class="ad-fb">' + items.map(function (i) {
            var c = i.context || {};
            return '<div class="ui-item" data-id="' + esc(i.id) + '"><div class="meta"><span class="ui-badge ' + (i.kind === 'bug' ? 'bad' : i.kind === 'idea' ? 'brand' : '') + '">' + esc(i.kind_label) + '</span>' +
              '<b>' + esc(i.name) + '</b>' + (i.email ? '<a href="mailto:' + esc(i.email) + '">' + esc(i.email) + '</a>' : '') + '<span>' + esc(UI.fmtDateTime(i.created)) + '</span></div>' +
              '<p class="msg">' + esc(i.message) + '</p>' +
              '<div class="ctx">' + esc([c.page, c.screen, c.theme, c.browser].filter(Boolean).join(' · ')) + '</div>' +
              '<textarea data-note placeholder="Private note (only admins see it)">' + esc(i.note) + '</textarea>' +
              '<div class="ui-row" style="margin-top:10px">' + ['new', 'read', 'done'].map(function (s) {
                return '<button class="ui-btn sm' + (i.status === s ? ' primary' : '') + '" data-status="' + s + '">' + s[0].toUpperCase() + s.slice(1) + '</button>';
              }).join('') + '<span class="ui-spacer"></span><button class="ui-btn sm danger" data-del-fb>' + UI.icon('trash') + 'Delete</button></div></div>';
          }).join('') + '</div>'
            : '<div class="ui-empty">' + UI.icon('inbox') + '<h3>No ' + (fbFilter === 'all' ? '' : fbFilter + ' ') + 'messages</h3><p>New feedback goes to Prepsto (prepsto.com). Older messages and requests from the app show up here.</p></div>');
      });
    }

    function users(query) {
      return UI.api('list_users', query || null).then(function (d) {
        body.innerHTML = '<form class="ui-row" data-search style="margin-bottom:14px"><input type="search" name="q" placeholder="Search by name or email" value="' + esc(query || '') + '" style="max-width:360px">' +
          '<button class="ui-btn" type="submit">' + UI.icon('search') + 'Search</button><span class="muted small">' + UI.plural(d.total, 'person', 'people') + '</span></form>' +
          '<table class="ad-users"><thead><tr><th>Name</th><th>Email</th><th>Joined</th><th>Admin</th><th>Active</th></tr></thead><tbody>' +
          d.users.map(function (u) {
            return '<tr data-id="' + esc(u.id) + '"><td><b>' + esc(u.name) + '</b></td><td class="email">' + esc(u.email) + '</td><td class="joined muted">' + esc(UI.fmtDate(u.joined)) + '</td>' +
              '<td><label class="ui-check"><input type="checkbox" data-admin' + (u.is_admin ? ' checked' : '') + '> Admin</label></td>' +
              '<td><label class="ui-check"><input type="checkbox" data-enabled' + (u.enabled ? ' checked' : '') + '> Active</label></td></tr>';
          }).join('') + '</tbody></table>';
      });
    }

    function demo() {
      return UI.api('admin_overview').then(function (d) {
        var c = d.demo.counts;
        body.innerHTML = '<div class="ui-card ui-narrow" style="margin:0"><h3>Demo data</h3>' +
          '<p class="muted">Example people and content, so the app never looks empty for the first visitors. Demo rows are flagged, so removing them never touches real data. Once removed, it stays removed until you load it again.</p>' +
          '<p>Status: <b>' + esc(d.demo.state) + '</b> · ' + Object.keys(c).map(function (k) { return c[k] + ' ' + esc(k); }).join(', ') + '</p>' +
          '<div class="ui-row"><button class="ui-btn primary" data-demo="load">' + UI.icon('refresh') + (d.demo.state === 'loaded' ? 'Reload demo data' : 'Load demo data') + '</button>' +
          '<button class="ui-btn danger" data-demo="remove">' + UI.icon('trash') + 'Remove demo data</button></div></div>';
      });
    }

    function bountyItem(b, actions) {
      return '<div class="ui-item" data-bid="' + esc(b.id) + '"><div class="ui-row between top"><div><b>' + esc(b.title) + '</b> ' + SR.stamp(b.status) + (b.demo ? ' <span class="ui-badge">Demo</span>' : '') + '</div>' +
        '<span class="sr-tag sm"><b>' + SR.money(b.base) + '</b>' + (b.bonus ? '<i>+' + SR.money(b.bonus) + '</i>' : '') + '</span></div>' +
        (b.flags.length ? '<div class="flags">' + b.flags.map(function (f) { return '<span class="ui-badge warn">' + UI.icon('flag') + esc(f) + '</span>'; }).join('') + '</div>' : '') +
        (b.details ? '<p class="det">' + esc(b.details) + '</p>' : '') +
        (b.dispute ? '<div class="ui-note small" style="margin-bottom:10px"><b>' + esc(b.dispute_by) + ' says:</b> ' + esc(b.dispute) + '</div>' : '') +
        '<div class="meta"><span>' + UI.icon('user') + esc(b.poster) + ' &lt;' + esc(b.poster_email) + '&gt;' + (b.poster_strikes ? ' · ' + UI.plural(b.poster_strikes, 'strike') : '') + '</span>' +
        (b.helper ? '<span>Helper: ' + esc(b.helper) + '</span>' : '') + (b.quality != null ? '<span>Quality ' + b.quality + '%</span>' : '') +
        (b.amount_due != null ? '<span>Owed ' + SR.money(b.amount_due) + '</span>' : '') + '<span>' + esc(b.area) + ' · ' + esc(UI.ago(b.created)) + '</span>' +
        '<a href="#bounty/' + esc(b.id) + '" data-go="bounty/' + esc(b.id) + '">Open</a></div>' + (actions ? '<div class="ui-row" style="margin-top:12px">' + actions + '</div>' : '') + '</div>';
    }

    function queue() {
      return UI.api('admin_queue').then(function (d) {
        body.innerHTML = '<p class="muted">New bounties the scanner flagged (scam words, unsafe or licensed work, "another task", big amounts from new accounts), and bounties reported by 3 neighbours.</p>' +
          (d.items.length ? '<div class="ad-q">' + d.items.map(function (b) {
            return bountyItem(b, '<button class="ui-btn sm primary" data-approve>' + UI.icon('check') + 'Approve</button><button class="ui-btn sm danger" data-reject>' + UI.icon('x') + 'Reject</button>');
          }).join('') + '</div>' : '<div class="ui-empty">' + UI.icon('check') + '<h3>Queue is empty</h3><p>Nothing waiting for review.</p></div>');
      });
    }

    function safety() {
      return UI.api('admin_safety').then(function (d) {
        var open = d.reports.filter(function (r) { return r.status === 'open'; }), done = d.reports.filter(function (r) { return r.status !== 'open'; });
        body.innerHTML = '<div class="ad-h">Disputes (' + d.disputes.length + ')</div>' + (d.disputes.length ? '<div class="ad-q">' + d.disputes.map(function (b) {
            return bountyItem(b, '<select data-outcome style="width:auto"><option value="full">Owed: bounty + bonus</option><option value="base">Owed: bounty only</option>' +
              '<option value="done">Payment confirmed: close</option><option value="cancel">Nothing owed: cancel</option></select>' +
              '<select data-strike style="width:auto"><option value="">No strike</option><option value="poster">Strike the poster</option><option value="helper">Strike the helper</option></select>' +
              '<input type="text" data-note placeholder="Note for both sides" maxlength="300" style="max-width:260px"><button class="ui-btn sm primary" data-resolve>Settle</button>');
          }).join('') + '</div>' : '<p class="muted">No open disputes.</p>') +
          '<div class="ad-h">Open reports (' + open.length + ')</div>' + (open.length ? '<div class="ad-q">' + open.map(reportItem).join('') + '</div>' : '<p class="muted">No open reports.</p>') +
          '<div class="ad-h">People with strikes (' + d.people.length + ')</div>' + (d.people.length ? '<table class="ad-users"><thead><tr><th>Name</th><th>Email</th><th>Strikes</th><th>Paused</th><th></th></tr></thead><tbody>' +
            d.people.map(function (u) {
              return '<tr data-pid="' + esc(u.id) + '"><td><b>' + esc(u.name) + '</b><div class="small muted">' + esc(u.last_strike) + '</div></td><td class="email">' + esc(u.email) + '</td>' +
                '<td><input type="number" min="0" max="9" value="' + u.strikes + '" data-strikes style="width:70px"></td><td><label class="ui-check"><input type="checkbox" data-paused' + (u.paused ? ' checked' : '') + '> Paused</label></td>' +
                '<td><button class="ui-btn sm" data-standing>Save</button></td></tr>';
            }).join('') + '</tbody></table>' : '<p class="muted">Nobody has a strike.</p>') +
          (done.length ? '<div class="ad-h">Handled reports</div><div class="ad-q">' + done.slice(0, 20).map(reportItem).join('') + '</div>' : '');
      });
    }
    function reportItem(r) {
      return '<div class="ui-item" data-rid="' + esc(r.id) + '"><div class="ui-row between top"><div><span class="ui-badge ' + (r.status === 'open' ? 'bad' : '') + '">' + esc(r.kind_label) + '</span> ' +
        '<b>' + esc(r.reporter) + '</b> reported ' + (r.subject ? '<b>' + esc(r.subject.name) + '</b> (' + esc(r.subject.email) + ', ' + UI.plural(r.subject.strikes, 'strike') + ')' : '') +
        (r.bounty ? ' on <a href="#bounty/' + esc(r.bounty.id) + '" data-go="bounty/' + esc(r.bounty.id) + '">' + esc(r.bounty.title) + '</a>' : '') + '</div><span class="small muted">' + esc(UI.ago(r.created)) + '</span></div>' +
        '<p class="det" style="margin:8px 0">' + esc(r.text) + '</p>' + (r.status === 'open' ? '<div class="ui-row"><input type="text" data-note placeholder="Note (optional)" maxlength="300" style="max-width:280px">' +
          '<button class="ui-btn sm danger" data-uphold>Uphold (strike)</button><button class="ui-btn sm" data-dismiss>Dismiss</button></div>' :
          '<p class="small muted" style="margin:0">' + esc(r.status) + (r.note ? ': ' + esc(r.note) : '') + '</p>') + '</div>';
    }

    var bFilter = 'all';
    function bounties() {
      return UI.api('admin_bounties', bFilter).then(function (d) {
        body.innerHTML = '<div class="ui-row" style="margin-bottom:14px"><select data-bfilter style="width:auto">' + ['all', 'review', 'open', 'assigned', 'submitted', 'validated', 'paid', 'done', 'disputed', 'cancelled', 'rejected', 'removed'].map(function (s) {
            return '<option value="' + s + '"' + (bFilter === s ? ' selected' : '') + '>' + (s === 'all' ? 'All statuses' : esc(SR.STATUS[s] || s)) + '</option>';
          }).join('') + '</select><span class="muted small">' + UI.plural(d.total, 'bounty', 'bounties') + '</span></div>' +
          (d.items.length ? '<div class="ad-q">' + d.items.map(function (b) {
            return bountyItem(b, b.status !== 'removed' ? '<button class="ui-btn sm danger" data-remove>' + UI.icon('trash') + 'Remove</button>' : '');
          }).join('') + '</div>' : '<div class="ui-empty">' + UI.icon('tag') + '<h3>No bounties</h3></div>');
      });
    }

    var DRAW = { overview: overview, queue: queue, safety: safety, bounties: bounties, feedback: feedback, users: users, demo: demo };
    view.addEventListener('click', function (e) {
      var t, item = e.target.closest('[data-bid]');
      if ((t = e.target.closest('[data-approve]'))) { UI.busy(t, UI.api('admin_approve', item.getAttribute('data-bid'))).then(function () { UI.toast('Approved: it\'s on the board', 'ok'); queue(); }); return; }
      if ((t = e.target.closest('[data-reject]'))) {
        var bid = item.getAttribute('data-bid');
        var m = UI.modal('<h2>Reject this bounty?</h2><form class="ui-stack" data-rej><label class="ui-field"><span>Why? (the poster sees this)</span>' +
          '<textarea name="why" maxlength="300">It breaks the rules for bounties.</textarea></label><div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Back</button>' +
          '<button class="ui-btn danger solid" type="submit">Reject</button></div></form>');
        m.el.querySelector('[data-rej]').addEventListener('submit', function (ev) {
          ev.preventDefault();
          UI.busy(ev.target.querySelector('[type=submit]'), UI.api('admin_reject', bid, ev.target.why.value)).then(function () { m.close(); UI.toast('Rejected', 'ok'); queue(); });
        });
        return;
      }
      if ((t = e.target.closest('[data-resolve]'))) {
        UI.busy(t, UI.api('admin_resolve_dispute', item.getAttribute('data-bid'), item.querySelector('[data-outcome]').value, item.querySelector('[data-strike]').value || null,
          item.querySelector('[data-note]').value)).then(function () { UI.toast('Dispute settled', 'ok'); safety(); });
        return;
      }
      var rep = e.target.closest('[data-rid]');
      if (rep && (t = e.target.closest('[data-uphold],[data-dismiss]'))) {
        UI.busy(t, UI.api('admin_resolve_report', rep.getAttribute('data-rid'), t.hasAttribute('data-uphold') ? 'uphold' : 'dismiss', rep.querySelector('[data-note]').value))
          .then(function () { UI.toast('Done', 'ok'); safety(); });
        return;
      }
      var pr = e.target.closest('[data-pid]');
      if (pr && (t = e.target.closest('[data-standing]'))) {
        UI.busy(t, UI.api('admin_set_standing', pr.getAttribute('data-pid'), +pr.querySelector('[data-strikes]').value, pr.querySelector('[data-paused]').checked))
          .then(function () { UI.toast('Saved', 'ok'); safety(); });
        return;
      }
      if ((t = e.target.closest('[data-remove]'))) {
        UI.confirm({ title: 'Remove this bounty?', text: 'It disappears for everyone. The poster sees it was removed by a moderator.', ok: 'Remove', danger: true }).then(function (yes) {
          if (yes) UI.api('admin_remove_bounty', item.getAttribute('data-bid'), '').then(function () { UI.toast('Removed', 'ok'); bounties(); });
        });
      }
    });
    view.addEventListener('change', function (e) { if (e.target.matches('[data-bfilter]')) { bFilter = e.target.value; bounties(); } });

    view.addEventListener('click', function (e) {
      var f = e.target.closest('[data-filter]');
      if (f) { fbFilter = f.getAttribute('data-filter'); feedback(); return; }
      var st = e.target.closest('[data-status]');
      if (st) {
        var card = st.closest('[data-id]');
        UI.api('set_feedback_status', card.getAttribute('data-id'), st.getAttribute('data-status'), card.querySelector('[data-note]').value).then(function () { UI.toast('Saved', 'ok'); feedback(); });
        return;
      }
      var del = e.target.closest('[data-del-fb]');
      if (del) {
        UI.confirm({ title: 'Delete this message?', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_feedback', del.closest('[data-id]').getAttribute('data-id')).then(feedback);
        });
        return;
      }
      var dm = e.target.closest('[data-demo]');
      if (dm) {
        var load = dm.getAttribute('data-demo') === 'load';
        UI.confirm({ title: load ? 'Load the demo data?' : 'Remove the demo data?', text: load ? 'Demo people and content are added (any old demo rows are replaced).' : 'Every demo row is deleted. Real data stays.', ok: load ? 'Load' : 'Remove', danger: !load })
          .then(function (yes) { if (yes) UI.busy(dm, UI.api(load ? 'demo_load' : 'demo_remove')).then(function () { UI.toast('Done', 'ok'); demo(); }); });
      }
    });
    view.addEventListener('change', function (e) {
      var row = e.target.closest('tr[data-id]');
      if (!row) return;
      var id = row.getAttribute('data-id'), box = e.target;
      var fn = box.hasAttribute('data-admin') ? 'set_admin' : box.hasAttribute('data-enabled') ? 'set_enabled' : null;
      if (fn) UI.api(fn, id, box.checked).then(function () { UI.toast('Saved', 'ok'); }, function (err) { box.checked = !box.checked; UI.toast(err.message, 'error'); });
    });
    view.addEventListener('submit', function (e) {
      if (e.target.matches('[data-search]')) { e.preventDefault(); users(UI.formData(e.target).q); }
    });
    return DRAW[tab]();
  });
})();

/* ===== auth.html ===== */
(function () {
  var esc = UI.esc;
  var GOOGLE_G = '<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>' +
    '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>' +
    '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>' +
    '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>';
  function pw(name, auto) {
    return '<div class="au-pw"><input type="password" name="' + name + '" autocomplete="' + auto + '" required minlength="8">' +
      '<button type="button" data-show>Show</button></div>';
  }
  UI.page('auth', { title: 'Sign in', auth: 'guest' }, function (view, ctx) {
    var mode = ['signup', 'reset'].indexOf(ctx.args[0]) >= 0 ? ctx.args[0] : 'login';
    function draw(msg, isErr) {
      var heading = { login: 'Welcome back', signup: 'Create your account', reset: 'Reset your password' }[mode];
      var sub = { login: 'Sign in to continue to ' + esc(UI.config.name) + '.', signup: 'It\'s free and takes a few seconds.',
        reset: 'We\'ll email you a link to choose a new password.' }[mode];
      view.innerHTML = '<div class="au-wrap"><div class="ui-card au-card">' +
        '<h1>' + heading + '</h1><p class="muted">' + sub + '</p>' +
        (mode !== 'reset' ? '<div class="ui-seg" role="tablist"><button type="button" data-mode="login" class="' + (mode === 'login' ? 'on' : '') + '">Sign in</button>' +
          '<button type="button" data-mode="signup" class="' + (mode === 'signup' ? 'on' : '') + '">Create account</button></div>' : '<div style="height:14px"></div>') +
        '<form class="ui-stack" data-form="' + mode + '" novalidate>' +
        (mode === 'signup' ? '<label class="ui-field"><span>Your name</span><input type="text" name="name" autocomplete="name" required maxlength="60"></label>' : '') +
        '<label class="ui-field"><span>Email</span><input type="email" name="email" autocomplete="email" required></label>' +
        (mode === 'login' ? '<label class="ui-field"><span>Password</span>' + pw('password', 'current-password') + '</label>' : '') +
        (mode === 'signup' ? '<label class="ui-field"><span>Password <em>(at least 8 characters)</em></span>' + pw('password', 'new-password') + '</label>' +
          (window.LegalKit ? '<div>' + LegalKit.consentField() + '</div>' : '') : '') +
        '<div data-msg role="alert"' + (msg ? ' class="' + (isErr ? 'ui-error' : 'ui-note') + '">' + esc(msg) : ' hidden>') + '</div>' +
        '<button class="ui-btn primary block" type="submit">' + { login: 'Sign in', signup: 'Create account', reset: 'Send the link' }[mode] + '</button></form>' +
        (mode !== 'reset' ? '<div class="au-or">or</div><button type="button" class="ui-btn block au-google" data-google>' + GOOGLE_G + 'Continue with Google</button>' : '') +
        '<div class="au-links">' + (mode === 'login' ? '<a data-mode="reset">Forgot your password?</a>' : '<a data-mode="login">' + UI.icon('back') + ' Back to sign in</a>') +
        '<a href="#landing" data-go="landing">About ' + esc(UI.config.name) + '</a></div></div></div>';
      var first = view.querySelector('input');
      if (first && !msg) first.focus();
    }
    view.addEventListener('click', function (e) {
      var m = e.target.closest('[data-mode]');
      if (m) { e.preventDefault(); mode = m.getAttribute('data-mode'); history.replaceState(null, '', '#auth' + (mode === 'login' ? '' : '/' + mode)); draw(); return; }
      var g = e.target.closest('[data-google]');
      if (g) { google(g); return; }
      var s = e.target.closest('[data-show]');
      if (s) { var i = s.parentNode.querySelector('input'); i.type = i.type === 'password' ? 'text' : 'password'; s.textContent = i.type === 'password' ? 'Show' : 'Hide'; }
    });
    view.addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target, v = UI.formData(form);
      var problem = !/^\S+@\S+\.\S+$/.test(v.email || '') ? 'Please enter a valid email address.'
        : mode !== 'reset' && (v.password || '').length < (mode === 'signup' ? 8 : 1) ? (mode === 'signup' ? 'Please choose a password of at least 8 characters.' : 'Please enter your password.')
        : mode === 'signup' && (v.name || '').trim().length < 2 ? 'Please tell us your name.' : null;
      if (problem) { say(problem, true); return; }
      if (mode === 'signup' && window.LegalKit && !LegalKit.consentChecked(form)) return;  // the kit shows its own message
      UI.busy(form.querySelector('[type=submit]'), UI.auth(mode, v)).then(function (r) {
        if (mode === 'reset' || (r && !r.me)) { mode = 'login'; draw(r && r.message, false); restore({ email: v.email }); }
        else UI.toast(mode === 'signup' ? 'Welcome to ' + UI.config.name + '!' : 'Welcome back!', 'ok');
      }, function (err) { say(err.message, true); });
    });
    // Sign-up asks for the Privacy & Terms tick here too (ticking it is remembered for the new account).
    function google(btn) {
      var form = view.querySelector('form'), v = mode === 'signup' ? UI.formData(form) : {};
      if (mode === 'signup' && window.LegalKit && !LegalKit.consentChecked(form)) return;
      UI.busy(btn, UI.auth('google', { name: (v.name || '').trim() })).then(function () {
        UI.toast(mode === 'signup' ? 'Welcome to ' + UI.config.name + '!' : 'Welcome back!', 'ok');
      }, function (err) { say(err.message, true); });
    }
    function say(msg, isErr) {
      var box = view.querySelector('[data-msg]');
      box.className = isErr ? 'ui-error' : 'ui-note'; box.textContent = msg; box.hidden = false;
    }
    function restore(v) {
      ['name', 'email'].forEach(function (k) { var i = view.querySelector('[name=' + k + ']'); if (i && v[k]) i.value = v[k]; });
    }
    draw();
  });
})();

/* ===== board.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('board', { title: 'Bounty board', nav: 'Bounties', icon: 'search', order: 10 }, function (view, ctx) {
    var F = Object.assign({ q: '', cat: 'all', sort: 'new', dist: 'any', pay: 'any', bonus: false }, UI.store.get('board.f', {}));
    F.q = '';
    var data = null, center = null, guestSpot = null, map = null, L = null, layer = null, markers = {}, show = 'list', alive = true;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:120px;margin-bottom:16px"></div><div class="ui-skel" style="height:420px"></div></div>';

    function filtered() {
      var q = F.q.trim().toLowerCase(), max = F.dist === 'any' ? null : +F.dist;
      var list = data.items.filter(function (b) {
        var t = SR.task(b.task);
        if (F.cat === 'season' && !SR.inSeason(t)) return false;
        if (F.cat !== 'all' && F.cat !== 'season' && b.cat !== F.cat) return false;
        if (max != null && b.dist != null && b.dist > max) return false;
        if (F.pay !== 'any' && b.pay !== F.pay && b.pay !== 'either') return false;
        if (F.bonus && !b.bonus) return false;
        if (q && (b.title + ' ' + b.details + ' ' + b.area + ' ' + t.name + ' ' + SR.cat(b.cat).name).toLowerCase().indexOf(q) < 0) return false;
        return true;
      });
      var by = {
        new: function (a, b) { return a.created < b.created ? 1 : -1; },
        money: function (a, b) { return (b.base + b.bonus) - (a.base + a.bonus); },
        near: function (a, b) { return (a.dist == null ? 1e9 : a.dist) - (b.dist == null ? 1e9 : b.dist); },
        soon: function (a, b) { return (a.when_date || '9999') < (b.when_date || '9999') ? -1 : 1; }
      }[F.sort] || null;
      if (by) list.sort(by);
      return list;
    }

    function shell() {
      var cats = [['all', 'All', 'grid'], ['season', 'In season', 'sparkle']].concat(
        SR._cat.categories.filter(function (c) { return c.key !== 'other'; }).map(function (c) { return [c.key, c.name, c.icon]; }));
      var area = (UI.me && UI.me.spot && UI.me.spot.label) || (guestSpot ? 'you' : 'Montréal');
      view.innerHTML = '<div class="ui-wrap">' +
        (UI.me ? '' : '<div class="bd-guest"><p>' + UI.icon('hand') + ' Neighbours pay from $20 for leaves, snow, junk and more. Sign up to make offers or post your own.</p>' +
          '<div class="ui-row"><a class="ui-btn primary" href="#auth/signup" data-go="auth/signup">Join free</a><a class="ui-btn" href="#landing" data-go="landing" style="background:transparent;color:inherit;border-color:currentColor">How it works</a></div></div>') +
        '<section class="bd-hero"><div><span class="eyebrow">Bounty board</span>' +
          '<h1>Bounties near <button type="button" data-area title="Change area">' + esc(area) + '</button></h1>' +
          '<p data-summary></p></div>' +
          '<div class="ui-row"><button class="ui-btn" type="button" data-area>' + UI.icon('pin') + (UI.me ? 'Change area' : 'Use my location') + '</button>' +
          '<a class="ui-btn primary" href="#post" data-go="post">' + UI.icon('plus') + 'Post a bounty</a></div></section>' +
        '<form class="bd-search" data-search role="search"><input type="search" name="q" placeholder="Search: leaves, snow, moving, Verdun…" aria-label="Search bounties" value="' + esc(F.q) + '">' +
          '<button class="ui-btn dark" type="submit">' + UI.icon('search') + '<span>Search</span></button></form>' +
        '<div class="bd-chips" role="toolbar" aria-label="Categories">' + cats.map(function (c) {
          return '<button type="button" class="sr-chip' + (F.cat === c[0] ? ' on' : '') + '" data-cat="' + c[0] + '">' + UI.icon(c[2]) + esc(c[1]) + '</button>';
        }).join('') + '</div>' +
        '<div class="bd-filters">' +
          sel('sort', [['new', 'Newest'], ['money', 'Highest bounty'], ['near', 'Closest'], ['soon', 'Soonest']], 'Sort') +
          sel('dist', [['any', 'Any distance'], ['2', 'Within 2 km'], ['5', 'Within 5 km'], ['10', 'Within 10 km'], ['25', 'Within 25 km']], 'Distance') +
          sel('pay', [['any', 'Any payment'], ['cash', 'Cash'], ['etransfer', 'e-Transfer']], 'Payment') +
          '<label class="ui-check"><input type="checkbox" data-f="bonus"' + (F.bonus ? ' checked' : '') + '> Quality bonus only</label>' +
          '<span class="ui-spacer"></span><div class="ui-seg bd-view"><button type="button" data-show="list" class="on">' + 'List</button><button type="button" data-show="map">Map</button></div></div>' +
        '<div class="bd-split" data-show="list"><div class="bd-list" data-list></div><div class="bd-mapcol"><div class="sr-map" data-map><div class="sr-map-msg">Loading the map…</div></div></div></div></div>';
      function sel(k, opts, label) {
        return '<select data-f="' + k + '" aria-label="' + label + '">' + opts.map(function (o) {
          return '<option value="' + o[0] + '"' + (String(F[k]) === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
        }).join('') + '</select>';
      }
      initMap();
    }

    function drawList() {
      var list = filtered(), box = view.querySelector('[data-list]');
      view.querySelector('[data-summary]').innerHTML = '<b>' + UI.plural(data.total, 'open bounty', 'open bounties') + '</b> · <b>' + SR.money(data.money) + '</b> waiting to be earned';
      box.innerHTML = '<p class="bd-count">' + (list.length === data.items.length ? 'Showing all ' + list.length : list.length + ' of ' + data.items.length + ' match') + '</p>' +
        (list.length ? list.map(SR.card).join('') :
          '<div class="ui-empty">' + UI.icon('search') + '<h3>No bounties match</h3><p>Try another category or a wider distance, or post the job you need done.</p>' +
          '<button class="ui-btn" type="button" data-reset>Clear filters</button></div>');
      drawPins(list);
      UI.store.set('board.f', { cat: F.cat, sort: F.sort, dist: F.dist, pay: F.pay, bonus: F.bonus });
    }

    function initMap() {
      SR.leaflet().then(function (LL) {
        if (!alive) return;
        L = LL;
        var box = view.querySelector('[data-map]');
        if (!box) return;
        box.innerHTML = '';
        map = L.map(box, { scrollWheelZoom: false }).setView([center.lat, center.lng], 12);
        SR.tiles(L, map);
        layer = L.layerGroup().addTo(map);
        drawPins(filtered());
      }, function (e) {
        var box = view.querySelector('[data-map]');
        if (box) box.innerHTML = '<div class="sr-map-msg">' + esc(e.message) + '</div>';
      });
    }
    function drawPins(list) {
      if (!map || !layer) return;
      layer.clearLayers(); markers = {};
      var pts = [];
      list.forEach(function (b) {
        if (b.lat == null) return;
        var mk = L.marker([b.lat, b.lng], { icon: SR.pricePin(L, b), riseOnHover: true, keyboard: false }).addTo(layer);
        mk.on('click', function () { UI.go('bounty', b.id); });
        mk.on('mouseover', function () { hot(b.id, true); });
        mk.on('mouseout', function () { hot(b.id, false); });
        markers[b.id] = mk; pts.push([b.lat, b.lng]);
      });
      if (data.spot || guestSpot) {
        var s = guestSpot || data.spot;
        L.marker([s.lat, s.lng], { icon: SR.pricePin(L, { label: 'You' }, 'me'), interactive: false }).addTo(layer);
      }
      if (pts.length) map.fitBounds(pts, { padding: [40, 40], maxZoom: 14, animate: false });
      else map.setView([center.lat, center.lng], 12, { animate: false });
    }
    function hot(id, on) {
      var card = view.querySelector('[data-card="' + id + '"]');
      if (card) card.classList.toggle('hot', on);
      var pin = view.querySelector('[data-pin="' + id + '"]');
      if (pin) pin.classList.toggle('hot', on);
    }

    view.addEventListener('click', function (e) {
      var c = e.target.closest('[data-cat]');
      if (c) { F.cat = c.getAttribute('data-cat'); view.querySelectorAll('[data-cat]').forEach(function (x) { x.classList.toggle('on', x === c); }); drawList(); return; }
      var s = e.target.closest('[data-show]');
      if (s && s.tagName === 'BUTTON') {
        show = s.getAttribute('data-show');
        view.querySelector('.bd-split').setAttribute('data-show', show);
        view.querySelectorAll('.bd-view button').forEach(function (x) { x.classList.toggle('on', x === s); });
        if (map) setTimeout(function () { map.invalidateSize(); drawPins(filtered()); }, 50);
        return;
      }
      if (e.target.closest('[data-reset]')) { F = { q: '', cat: 'all', sort: 'new', dist: 'any', pay: 'any', bonus: false }; shell(); drawList(); return; }
      if (e.target.closest('[data-area]')) {
        if (UI.me) { SR.editArea().then(function (me) { if (me) load(); }); return; }
        if (!navigator.geolocation) { UI.toast('This browser can\'t share its location.', 'error'); return; }
        navigator.geolocation.getCurrentPosition(function (p) {
          guestSpot = { lat: p.coords.latitude, lng: p.coords.longitude }; load();
        }, function () { UI.toast('We couldn\'t get your location. Showing Montréal.', 'error'); }, { timeout: 12000, maximumAge: 600000 });
      }
    });
    view.addEventListener('mouseover', function (e) { var c = e.target.closest('[data-card]'); if (c) hot(c.getAttribute('data-card'), true); });
    view.addEventListener('mouseout', function (e) { var c = e.target.closest('[data-card]'); if (c) hot(c.getAttribute('data-card'), false); });
    view.addEventListener('change', function (e) {
      var k = e.target.getAttribute('data-f');
      if (!k) return;
      F[k] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
      drawList();
    });
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-search]')) return;
      e.preventDefault(); F.q = e.target.q.value; drawList();
    });
    view.addEventListener('input', function (e) { if (e.target.name === 'q' && !e.target.value) { F.q = ''; drawList(); } });

    function load() {
      return Promise.all([SR.catalog(), UI.api('get_board', guestSpot ? guestSpot.lat : null, guestSpot ? guestSpot.lng : null)]).then(function (r) {
        SR._cat = r[0]; data = r[1]; center = data.center;
        if (map) { try { map.remove(); } catch (e) {} map = null; layer = null; }
        shell(); drawList();
      });
    }
    return { ready: load(), destroy: function () { alive = false; if (map) { try { map.remove(); } catch (e) {} map = null; } } };
  });
})();

/* ===== bounty.html ===== */
(function () {
  var esc = UI.esc;
  var TIPS = ['Never pay anything to get a job, and never send money back for an "overpayment".',
              'Check an e-Transfer in your bank app, not by clicking a link in an email.',
              'Keep the first chats in the app: reports only work for what happens here.',
              'Meet outside, in daylight. Tell someone where you are going.'];

  function hoursLeft(iso, hours) { return iso ? Math.max(0, Math.round(hours - (Date.now() - new Date(iso).getTime()) / 3600000)) : hours; }
  function first(name) { return String(name || '').split(' ')[0]; }

  function meter(q, bar, bonus) {
    return '<div class="bt-meter" aria-label="Quality ' + q + '%"><div class="fill' + (q >= 100 ? ' full' : '') + '" style="width:' + q + '%"></div>' +
      (bonus ? '<div class="bar" style="left:' + bar + '%"><span>Bonus at ' + bar + '%</span></div>' : '') + '<span class="val">' + q + '%</span></div>';
  }
  function personCard(p, role, title) {
    if (!p) return '';
    var r = p.record || {};
    var lines = role === 'poster' ?
      ['<div>' + UI.icon('star') + 'Rated ' + SR.rating(r) + ' by helpers</div>',
       '<div>' + UI.icon('bolt') + SR.payRecord(r) + '</div>',
       '<div>' + UI.icon('check') + '<span><b>' + r.completed + '</b> bounties completed' + (r.late_cancels ? ' · ' + r.late_cancels + ' late cancel' + (r.late_cancels > 1 ? 's' : '') : '') + '</span></div>'] :
      ['<div>' + UI.icon('star') + 'Rated ' + SR.rating(r) + ' by posters</div>',
       '<div>' + UI.icon('check') + '<span><b>' + r.jobs + '</b> jobs done · <b>' + r.bonus_won + '</b> quality bonuses' + (r.dropouts ? ' · ' + r.dropouts + ' drop-out' + (r.dropouts > 1 ? 's' : '') : '') + '</span></div>'];
    if (r.standing === 'warned') lines.push('<div class="ui-badge warn">' + UI.icon('info') + 'Has a warning from moderators</div>');
    return '<div class="ui-card"><h4 style="margin:0 0 12px">' + esc(title) + '</h4><a class="bt-who" href="#neighbour/' + esc(p.id) + '" data-go="neighbour/' + esc(p.id) + '">' +
      '<span class="ui-avatar">' + esc(UI.initials(p.name)) + '</span><span><b>' + esc(p.name) + '</b><span class="muted small">' + esc(p.area || 'Neighbour') +
      (p.joined ? ' · since ' + esc(UI.fmtDate(p.joined, { month: 'short', year: 'numeric' })) : '') + '</span></span></a><div class="bt-rec">' + lines.join('') + '</div></div>';
  }

  UI.page('bounty', { title: 'Bounty' }, function (view, ctx) {
    var id = ctx.args[0], b = null, map = null, up = null, alive = true;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:160px;margin-bottom:16px"></div><div class="ui-skel" style="height:360px"></div></div>';

    /* ---------------------------------------------------------------- side panel: the tag and what to do now */
    function sidePanel() {
      var r = b.role, s = b.status, out = '<div class="ui-card"><div class="bt-amount">' + SR.tag(b, 'big') +
        '<span class="small muted" style="text-align:right">' + SR.payIcon(b.pay) + ' ' + esc(SR.PAY[b.pay]) + (b.status === 'open' ? '<br>' + UI.plural(b.offers, 'offer') : '') + '</span></div>';
      if (b.bonus) out += '<p class="small" style="margin:14px 0 0"><b>Quality bonus:</b> ' + SR.money(b.base) + ' is paid once the work is validated, plus <b>' + SR.money(b.bonus) +
        '</b> if the checklist score reaches <b>' + b.bar + '%</b> (' + Math.ceil(b.checklist.length * b.bar / 100) + ' of ' + b.checklist.length + ' items).</p>';
      else out += '<p class="small muted" style="margin:14px 0 0">Paid once the work is validated. No quality bonus on this one.</p>';
      if (b.base > b.posted_base) out += '<p class="small" style="margin:6px 0 0">' + UI.icon('arrow') + ' Agreed at ' + SR.money(b.base) + ' (posted at ' + SR.money(b.posted_base) + ').</p>';
      out += '<div class="sr-hazard" style="margin:16px 0"></div>' + action(r, s) + '</div>';
      if (r !== 'poster') out += personCard(b.poster, 'poster', 'Posted by');
      if (r === 'poster' && b.helper) out += personCard(b.helper, 'helper', 'Your helper');
      out += '<div class="ui-card flat"><h4 style="margin:0">' + UI.icon('shield') + ' Stay safe</h4><ul class="bt-tips">' + TIPS.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') +
        '</ul><div class="bt-small-links" style="margin-top:10px"><a href="#rules" data-go="rules">Rules &amp; safety</a>' +
        (r !== 'poster' ? '<button type="button" data-report>' + 'Report this bounty</button>' : '') + '</div></div>';
      return out;
    }

    function action(r, s) {
      var P = first(b.poster && b.poster.name), H = first(b.helper && b.helper.name);
      if (s === 'cancelled' || s === 'rejected' || s === 'expired' || s === 'removed')
        return '<h3>' + esc(SR.STATUS[s]) + '</h3><p class="muted">' + esc(b.cancel_reason || 'This bounty is closed.') + '</p>';
      if (s === 'disputed')
        return '<h3>' + UI.icon('shield') + ' A moderator is on it</h3><p class="muted small">' + (b.dispute ? esc((b.dispute.by === r ? 'You' : b.dispute.by === 'poster' ? P : H) + ' opened a dispute: "' + b.dispute.reason + '"') : '') +
          '</p><p class="small">Nothing to do for now. The moderator reads both sides, the chat and the photos, then decides what is owed.</p>';
      if (r === 'visitor' || r === 'admin') {
        if (r === 'admin' && s !== 'open') return '<p class="muted">You\'re seeing this as a moderator.</p><a class="ui-btn" href="#admin/bounties" data-go="admin/bounties">Open admin</a>';
        if (!UI.me) return '<h3>Want this job?</h3><p class="muted small">Join free to send ' + esc(P) + ' an offer. You\'ll see the exact address once you\'re picked.</p>' +
          '<a class="ui-btn primary block" href="#auth/signup" data-signup>' + UI.icon('hand') + 'Join to make an offer</a>' +
          '<p class="small" style="margin:10px 0 0;text-align:center">Already a member? <a href="#auth" data-signin>Sign in</a></p>';
        var mo = b.my_offer;
        if (mo && mo.status === 'pending') return '<h3>' + UI.icon('send') + ' Offer sent</h3><p class="small">You offered <b>' + SR.money(mo.ask) + '</b>' + (mo.when ? ' · ' + esc(mo.when) : '') +
          '. ' + esc(P) + ' will pick a helper soon; you\'ll see it in My jobs.</p><p class="small muted" style="white-space:pre-wrap">"' + esc(mo.message) + '"</p>' +
          '<button class="ui-btn sm" type="button" data-withdraw="' + esc(mo.id) + '">Withdraw my offer</button>';
        if (mo && mo.status === 'declined') return '<h3>Not this time</h3><p class="muted small">' + esc(P) + ' went with someone else. Plenty more on the board!</p><a class="ui-btn block" href="#board" data-go="board">Back to the board</a>';
        if (b.can_help) return '<h3>Make an offer</h3><div class="ui-note small">' + esc(b.can_help) + '</div>';
        return '<h3>Make an offer</h3><form class="ui-stack" data-offer>' +
          '<label class="ui-field"><span>Message to ' + esc(P) + '</span><textarea name="message" required minlength="10" maxlength="500" placeholder="Hi ' + esc(P) + '! I can do this. I have…"></textarea></label>' +
          '<label class="ui-field"><span>When can you come?</span><input type="text" name="when" maxlength="80" placeholder="e.g. Saturday 9 am"></label>' +
          '<label class="ui-field"><span>Your price <em>(the bounty is ' + SR.money(b.base) + ')</em></span><input type="number" name="ask" min="' + b.base + '" max="' + Math.min(b.base * 2, 500) + '" step="1" value="' + b.base + '"></label>' +
          '<p class="ui-hint" style="margin-top:-6px">Ask more only if the job is bigger than described. The poster sees it as a counter-offer.</p>' +
          '<button class="ui-btn primary block" type="submit">' + UI.icon('send') + 'Send offer</button>' +
          '<p class="ui-hint">Contact details in messages are hidden until you\'re picked. Never pay anything to get a job.</p></form>';
      }
      if (r === 'poster') {
        if (s === 'review') return '<h3>' + UI.icon('shield') + ' Waiting for a moderator</h3><p class="small">Your bounty isn\'t on the board yet because:</p><ul class="small">' +
          b.flags.map(function (f) { return '<li>' + esc(f) + '</li>'; }).join('') + '</ul><p class="small muted">Most checks take a few hours. If it breaks the rules it won\'t be approved.</p>' + posterLinks(true);
        if (s === 'open') return '<h3>' + (b.offers ? 'Pick your helper' : 'Waiting for offers') + '</h3><p class="small muted">' +
          (b.offers ? 'Compare the offers below: track record, reviews and what they say. Only the one you pick sees your address.' :
            'Neighbours nearby can see it now. Sweeten the deal to get offers faster.') + '</p>' +
          '<div class="ui-row"><button class="ui-btn sm" type="button" data-raise>' + UI.icon('plus') + 'Raise the bounty</button></div>' + posterLinks(true);
        if (s === 'assigned') return '<h3>' + UI.icon('check') + ' ' + esc(H) + ' is booked</h3><p class="small">They now see your address and can chat with you below. ' +
          'When the job is done they send photos and their checklist, and you validate it here.</p>' + posterLinks(true, true);
        if (s === 'submitted') return '<h3>' + UI.icon('camera') + ' Proof is in!</h3><p class="small">' + esc(H) + ' says the job is done. Check the photos and tick the checklist below.</p>' +
          '<p class="ui-badge warn">' + UI.icon('clock') + hoursLeft(b.proof && b.proof.at, 48) + ' h left, then it\'s validated with ' + esc(H) + '\'s own checklist</p>' + posterLinks(false, true);
        if (s === 'validated') return payPanel();
        if (s === 'paid') return '<h3>' + UI.icon('check') + ' Marked as paid</h3><p class="small">You paid <b>' + SR.money(b.validation.amount_due) + '</b> by ' + esc(SR.PAY[b.payment.method]) +
          (b.payment.ref ? ' (ref. ' + esc(b.payment.ref) + ')' : '') + '. Waiting for ' + esc(H) + ' to confirm. It closes by itself after 7 days.</p>' + posterLinks(false, true);
        if (s === 'done') return '<h3>' + UI.icon('star') + ' All done</h3><p class="small">Paid and confirmed. ' + (b.reviews && !b.reviews.mine ? 'Leave ' + esc(H) + ' a review below: it helps the next neighbour.' : 'Thanks for using the board!') + '</p>' +
          '<a class="ui-btn primary block" href="#post/' + esc(b.task) + '" data-go="post/' + esc(b.task) + '">' + UI.icon('plus') + 'Post a similar bounty</a>';
      }
      if (r === 'helper') {
        var ex = b.exact || {};
        if (s === 'assigned') return '<h3>' + UI.icon('check') + ' You\'re booked!</h3><p class="small muted" style="margin:0">The address (only you see it):</p><div class="bt-addr">' + esc(ex.address) + '</div>' +
          '<div class="ui-row"><a class="ui-btn sm" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=' + ex.lat + ',' + ex.lng + '">' + UI.icon('route') + 'Directions</a>' +
          '<a class="ui-btn sm primary" href="#proof" data-jump="proof">' + UI.icon('camera') + 'Send proof</a></div>' +
          '<div class="bt-small-links" style="margin-top:14px"><button type="button" data-backout>I can\'t do it after all</button><button type="button" data-dispute>Something\'s wrong</button></div>';
        if (s === 'submitted') return '<h3>' + UI.icon('clock') + ' Proof sent</h3><p class="small">' + esc(P) + ' has <b>' + hoursLeft(b.proof && b.proof.at, 48) + ' h</b> to check it. ' +
          'If they don\'t, it\'s validated automatically with your checklist.</p><div class="bt-small-links"><button type="button" data-dispute>Something\'s wrong</button></div>';
        if (s === 'validated') {
          var v = b.validation;
          return '<h3>' + UI.icon('wallet') + ' ' + SR.money(v.amount_due) + ' is owed to you</h3>' + meter(v.quality, b.bar, b.bonus) +
            '<p class="small">' + (b.bonus ? (v.bonus_earned ? '<b>Bonus earned!</b> ' : 'Bonus not reached this time. ') : '') + esc(P) + ' pays by ' + esc(SR.PAY[b.payout.method] || '') +
            (b.payout.method === 'etransfer' ? ' to <b>' + esc(b.payout.email) + '</b>' : '') + '.</p>' +
            '<button class="ui-btn primary block" type="button" data-received>' + UI.icon('check') + 'I got paid</button>' +
            '<div class="bt-small-links" style="margin-top:12px"><button type="button" data-dispute>Not paid, or the score is unfair</button></div>';
        }
        if (s === 'paid') return '<h3>' + UI.icon('bank') + ' ' + esc(P) + ' says they paid</h3><p class="small"><b>' + SR.money(b.validation.amount_due) + '</b> by ' + esc(SR.PAY[b.payment.method]) +
          (b.payment.ref ? ', reference <b>' + esc(b.payment.ref) + '</b>' : '') + '. Check your bank app (not an email link), then confirm.</p>' +
          '<button class="ui-btn primary block" type="button" data-received>' + UI.icon('check') + 'Yes, I got it</button>' +
          '<div class="bt-small-links" style="margin-top:12px"><button type="button" data-dispute>I didn\'t get it</button></div>';
        if (s === 'done') return '<h3>' + UI.icon('star') + ' Job done!</h3><p class="small">You earned <b>' + SR.money(b.validation ? b.validation.amount_due : b.base) + '</b>' +
          (b.validation && b.validation.bonus_earned ? ' including the quality bonus' : '') + '. ' + (b.reviews && !b.reviews.mine ? 'Review ' + esc(P) + ' below.' : '') + '</p>' +
          '<a class="ui-btn block" href="#board" data-go="board">Find the next bounty</a>';
      }
      return '';
    }
    function posterLinks(cancel, dispute) {
      return '<div class="bt-small-links" style="margin-top:14px">' + (cancel ? '<button type="button" data-cancel>Cancel this bounty</button>' : '') +
        (dispute ? '<button type="button" data-dispute>Something\'s wrong</button>' : '') + '</div>';
    }
    function payPanel() {
      var v = b.validation, po = b.payout || {}, H = first(b.helper.name);
      var et = po.method === 'etransfer';
      return '<div class="bt-pay"><h3 style="margin:0">Time to pay ' + esc(H) + '</h3><div class="big">' + SR.money(v.amount_due) + '</div>' +
        '<div class="bt-break"><div><span>Bounty</span><span>' + SR.money(b.base) + '</span></div>' +
        (b.bonus ? '<div class="' + (v.bonus_earned ? '' : 'no') + '"><span>Quality bonus (' + v.quality + '% of ' + b.bar + '%)</span><span>' + SR.money(b.bonus) + '</span></div>' : '') +
        '<div class="tot"><span>Total</span><span>' + SR.money(v.amount_due) + '</span></div></div>' +
        (et ? '<p class="small" style="margin:0">Send an Interac e-Transfer from your bank to:</p><div class="email">' + UI.icon('mail') + '<span>' + esc(po.email) + '</span>' +
          '<button class="ui-btn sm" type="button" data-copy="' + esc(po.email) + '">' + UI.icon('copy') + 'Copy</button></div>'
          : '<p class="small">' + esc(H) + ' asked for <b>cash</b>. Hand it over in person, then mark it paid.</p>') +
        '<form class="ui-stack" data-paid style="margin-top:10px"><input type="hidden" name="method" value="' + (et ? 'etransfer' : 'cash') + '">' +
        (et ? '<label class="ui-field"><span>Reference number from your bank</span><input type="text" name="ref" maxlength="40" required minlength="4" placeholder="e.g. CA1a2B3c4D"></label>' : '') +
        '<button class="ui-btn primary block" type="submit">' + UI.icon('check') + 'I\'ve paid ' + SR.money(v.amount_due) + '</button></form>' +
        '<ul><li>Send exactly ' + SR.money(v.amount_due) + '. No fees: the app never asks you for money.</li><li>Pay within 3 days, or new posts are blocked until you do.</li></ul></div>' +
        posterLinks(false, true);
    }

    /* ---------------------------------------------------------------- main column */
    function mainCol() {
      var r = b.role, s = b.status, out = '';
      if (b.photos.length) out += '<section class="ui-card bt-sec"><h2>' + UI.icon('image') + 'Photos</h2><div class="sr-photos">' +
        b.photos.map(function (k) { return '<img src="' + esc(SR.photo(k, true)) + '" alt="Photo of the job" data-zoom="' + esc(k) + '" loading="lazy">'; }).join('') + '</div></section>';
      if (r === 'poster' && (s === 'open' || s === 'review')) out += offersSec();
      if ((r === 'poster' || r === 'helper') && s === 'submitted' && r === 'poster') out += validateSec();
      if (r === 'helper' && s === 'assigned') out += proofForm();
      if (b.proof && !(r === 'poster' && s === 'submitted')) out += proofView();
      if (b.validation) out += resultSec();
      if (b.reviews) out += reviewsSec();
      if (b.messages && ['assigned', 'submitted', 'validated', 'paid', 'done', 'disputed'].indexOf(s) >= 0) out += chatSec();
      out += '<section class="ui-card bt-sec"><h2>' + UI.icon('clipboard') + 'About the job</h2><div class="bt-details">' + esc(b.details) + '</div>' +
        (b.tools ? '<p class="small muted" style="margin:12px 0 0">' + UI.icon('wrench') + ' ' + esc(b.tools) + '</p>' : '') + '</section>';
      out += '<section class="ui-card bt-sec"><h2>' + UI.icon('ruler') + 'How quality is measured</h2><p class="small muted">The poster ticks this checklist when the job is done. ' +
        'Each item is worth ' + Math.round(100 / Math.max(1, b.checklist.length)) + '%.' + (b.bonus ? ' The ' + SR.money(b.bonus) + ' bonus is paid from ' + b.bar + '%.' : '') + '</p>' +
        '<ol class="bt-checklist">' + b.checklist.map(function (c) { return '<li>' + esc(c) + '<span class="pct">' + Math.round(100 / b.checklist.length) + '%</span></li>'; }).join('') + '</ol></section>';
      out += '<section class="ui-card bt-sec"><h2>' + UI.icon('pin') + 'Where</h2><p class="small muted">' + (b.exact ? esc(b.exact.address) + ' · ' + esc(b.area) :
        'Around ' + esc(b.area) + '. The circle is approximate: the exact address goes only to the helper the poster picks.') + '</p><div class="sr-map" data-map style="height:280px"><div class="sr-map-msg">Loading the map…</div></div></section>';
      if (b.log && b.log.length) out += '<section class="ui-card bt-sec"><h2>' + UI.icon('clock') + 'Timeline</h2><ul class="bt-log">' + b.log.slice().reverse().map(function (l) {
        return '<li class="' + esc(l.who) + '"><time>' + esc(UI.fmtDateTime(l.at)) + '</time>' + esc(l.text) + '</li>';
      }).join('') + '</ul></section>';
      return out;
    }
    function offersSec() {
      var list = b.offers_list || [];
      return '<section class="ui-card bt-sec"><h2>' + UI.icon('hand') + 'Offers <span class="ui-badge">' + list.filter(function (o) { return o.status === 'pending'; }).length + '</span></h2>' +
        (list.length ? '<div class="bt-offers">' + list.map(function (o) {
          var h = o.helper, rec = h.record || {};
          return '<div class="bt-offer ' + esc(o.status) + '"><div class="ui-row between top"><a class="bt-who" href="#neighbour/' + esc(h.id) + '" data-go="neighbour/' + esc(h.id) + '">' +
            '<span class="ui-avatar">' + esc(UI.initials(h.name)) + '</span><span><b>' + esc(h.name) + '</b><span class="small muted">' + SR.rating(rec) + ' · ' + rec.jobs + ' jobs · ' + rec.bonus_won + ' bonuses' +
            (rec.dropouts ? ' · ' + rec.dropouts + ' drop-outs' : '') + '</span></span></a>' +
            '<span class="sr-tag sm"><b>' + SR.money(o.ask) + '</b></span></div>' +
            (o.ask > b.base ? '<span class="ui-badge warn" style="margin-top:8px">Counter-offer: +' + SR.money(o.ask - b.base) + '</span>' : '') +
            '<p class="msg">' + esc(o.message) + '</p>' + (o.when ? '<p class="small" style="margin:0 0 10px">' + UI.icon('calendar') + ' <b>' + esc(o.when) + '</b></p>' : '') +
            (o.skills.length ? '<div class="skills">' + o.skills.map(function (k) { return '<span class="ui-badge">' + esc(k) + '</span>'; }).join('') + '</div>' : '') +
            (o.status === 'pending' && b.status === 'open' ? '<div class="ui-row"><button class="ui-btn primary" type="button" data-accept="' + esc(o.id) + '">' + UI.icon('check') + 'Pick ' + esc(first(h.name)) + '</button>' +
              '<button class="ui-btn ghost" type="button" data-decline="' + esc(o.id) + '">Decline</button></div>' : '<span class="ui-badge">' + esc(o.status) + '</span>') + '</div>';
        }).join('') + '</div>' : '<div class="ui-empty" style="padding:28px">' + UI.icon('hand') + '<h3>No offers yet</h3><p>Neighbours who can help will show up here.</p></div>') + '</section>';
    }
    function proofForm() {
      var pm = b.pay === 'either' ? 'etransfer' : b.pay;
      return '<section class="ui-card bt-sec" id="proof" data-proof-sec><h2>' + UI.icon('camera') + 'Send your proof</h2>' +
        '<p class="small muted">Tick what you did, add photos of the finished job, and say how you want to be paid. ' + esc(first(b.poster.name)) + ' then validates it.</p>' +
        '<form class="ui-stack" data-proof><div class="bt-checks">' + b.checklist.map(function (c, i) {
          return '<label><input type="checkbox" name="c' + i + '" checked> ' + esc(c) + '</label>';
        }).join('') + '</div>' +
        '<div><b class="small">Photos of the finished job</b> <span class="small muted">(at least 1)</span><div data-up style="margin-top:8px"></div></div>' +
        '<label class="ui-field"><span>Note for ' + esc(first(b.poster.name)) + ' <em>(optional)</em></span><textarea name="note" maxlength="800" placeholder="Anything to know: what you did, what you couldn\'t."></textarea></label>' +
        (b.pay === 'either' ? '<div class="bt-pm"><label class="ui-choice"><input type="radio" name="pm" value="etransfer" checked><span>' + UI.icon('bank') + 'e-Transfer</span></label>' +
          '<label class="ui-choice"><input type="radio" name="pm" value="cash"><span>' + UI.icon('cash') + 'Cash</span></label></div>' : '<input type="hidden" name="pm" value="' + pm + '">') +
        '<div data-email-box' + (pm === 'cash' ? ' hidden' : '') + '><label class="ui-field"><span>Your e-Transfer email</span><input type="email" name="email" maxlength="200" value="' + esc((UI.me && UI.me.payout_email) || '') + '" placeholder="the email your bank uses for Interac"></label>' +
        '<label class="ui-check" style="margin-top:8px"><input type="checkbox" name="remember" checked> Remember it for next time</label>' +
        '<p class="ui-hint">' + UI.icon('eyeoff') + ' Only ' + esc(first(b.poster.name)) + ' sees it, and only after validating your work.</p></div>' +
        '<button class="ui-btn primary lg" type="submit">' + UI.icon('send') + 'Send proof</button></form></section>';
    }
    function proofView() {
      var p = b.proof;
      return '<section class="ui-card bt-sec"><h2>' + UI.icon('camera') + 'Proof from ' + esc(first(b.helper.name)) + '</h2>' +
        '<div class="sr-photos">' + p.photos.map(function (k) { return '<img src="' + esc(SR.photo(k, true)) + '" alt="Proof photo" data-zoom="' + esc(k) + '">'; }).join('') + '</div>' +
        (p.note ? '<p style="margin:12px 0 0;white-space:pre-wrap">"' + esc(p.note) + '"</p>' : '') +
        '<p class="small muted" style="margin:8px 0 0">Sent ' + esc(UI.ago(p.at)) + ' · ' + p.self_checks.filter(Boolean).length + ' of ' + p.self_checks.length + ' items ticked by the helper</p></section>';
    }
    function validateSec() {
      var p = b.proof;
      return proofView() + '<section class="ui-card bt-sec"><h2>' + UI.icon('ruler') + 'Check the work</h2>' +
        '<p class="small muted">Tick every item that was done. ' + (b.bonus ? 'The bonus is paid from ' + b.bar + '%. ' : '') + 'If you untick something, say why: ' + esc(first(b.helper.name)) + ' reads it.</p>' +
        '<form class="ui-stack" data-validate><div class="bt-checks">' + b.checklist.map(function (c, i) {
          return '<label><input type="checkbox" name="c' + i + '"' + (p.self_checks[i] ? ' checked' : '') + '> ' + esc(c) + '<span class="self">' + (p.self_checks[i] ? 'Helper: done' : 'Helper: not done') + '</span></label>';
        }).join('') + '</div><div data-live></div>' +
        '<label class="ui-field"><span>Note for ' + esc(first(b.helper.name)) + ' <em>(needed if you untick something)</em></span><textarea name="note" maxlength="600" placeholder="e.g. The walkway wasn\'t swept."></textarea></label>' +
        '<button class="ui-btn primary lg" type="submit">' + UI.icon('check') + 'Validate the work</button></form></section>';
    }
    function liveVerdict(form) {
      var n = b.checklist.length, k = 0;
      for (var i = 0; i < n; i++) if (form['c' + i].checked) k++;
      var q = Math.round(100 * k / n), earned = b.bonus && q >= b.bar;
      form.querySelector('[data-live]').innerHTML = meter(q, b.bar, b.bonus) + '<p class="bt-verdict">Quality ' + q + '% → you\'ll owe <b>' + SR.money(b.base + (earned ? b.bonus : 0)) + '</b>' +
        (b.bonus ? (earned ? ' (bounty + bonus)' : ' (bonus not reached)') : '') + '</p>';
    }
    function resultSec() {
      var v = b.validation;
      return '<section class="ui-card bt-sec"><h2>' + UI.icon('ruler') + 'Quality ' + v.quality + '%' + (v.auto ? ' <span class="ui-badge">Automatic</span>' : '') + '</h2>' + meter(v.quality, b.bar, b.bonus) +
        '<ul class="bt-result">' + b.checklist.map(function (c, i) {
          return '<li>' + (v.checks[i] ? '<span class="y">' + UI.icon('check') + '</span>' : '<span class="n">' + UI.icon('x') + '</span>') + esc(c) + '</li>';
        }).join('') + '</ul>' + (v.note ? '<p class="small" style="margin:0">' + UI.icon('chat') + ' "' + esc(v.note) + '"</p>' : '') +
        (v.auto ? '<p class="small muted">Validated automatically 48 h after the proof, with the helper\'s checklist.</p>' : '') + '</section>';
    }
    function reviewsSec() {
      var rv = b.reviews, other = b.role === 'poster' ? first(b.helper.name) : first(b.poster.name);
      var out = '<section class="ui-card bt-sec"><h2>' + UI.icon('star') + 'Reviews</h2>';
      if (rv.mine) out += '<div class="bt-review"><b>Your review of ' + esc(other) + '</b> ' + SR.stars(rv.mine.stars) + '<p style="margin:6px 0 0">' + esc(rv.mine.text) + '</p>' +
        (rv.mine.tags.length ? '<div class="bt-tags" style="margin-top:8px">' + rv.mine.tags.map(function (t) { return '<span class="ui-badge">' + esc(t) + '</span>'; }).join('') + '</div>' : '') + '</div>';
      else out += '<form class="ui-stack" data-review><p class="small muted" style="margin:0">Reviews are blind: you\'ll see ' + esc(other) + '\'s once you leave yours' +
        (rv.theirs_waiting ? ' (theirs is waiting!)' : '') + '.</p><div class="bt-starpick" data-stars>' + [1, 2, 3, 4, 5].map(function (n) {
          return '<button type="button" data-star="' + n + '" aria-label="' + n + ' stars">' + UI.icon('star') + '</button>';
        }).join('') + '</div><div class="bt-tags">' + rv.tags.map(function (t) { return '<label><input type="checkbox" name="tag" value="' + esc(t) + '"><span>' + esc(t) + '</span></label>'; }).join('') +
        '</div><textarea name="text" maxlength="600" placeholder="How did it go?"></textarea><button class="ui-btn primary" type="submit">' + UI.icon('star') + 'Post review</button></form>';
      if (rv.theirs) out += '<div class="bt-review" style="margin-top:12px"><b>' + esc(rv.theirs.author) + '\'s review of you</b> ' + SR.stars(rv.theirs.stars) +
        (rv.theirs.text ? '<p style="margin:6px 0 0">' + esc(rv.theirs.text) + '</p>' : '') +
        (rv.theirs.tags.length ? '<div class="bt-tags" style="margin-top:8px">' + rv.theirs.tags.map(function (t) { return '<span class="ui-badge">' + esc(t) + '</span>'; }).join('') + '</div>' : '') + '</div>';
      return out + '</section>';
    }
    function chatSec() {
      var other = b.role === 'poster' ? first(b.helper.name) : first(b.poster.name), closed = b.status === 'done';
      return '<section class="ui-card bt-sec"><h2>' + UI.icon('chat') + 'Chat with ' + esc(other) + '</h2><div class="bt-chat" data-chat>' +
        (b.messages.length ? b.messages.map(msgHtml).join('') : '<p class="muted small">Say hi and agree on the details: when, where the tools are, how to get in the yard.</p>') + '</div>' +
        (closed ? '' : '<form class="bt-chatform" data-chatform><textarea name="text" maxlength="1000" placeholder="Write a message" aria-label="Message"></textarea>' +
          '<button class="ui-btn primary icon" type="submit" aria-label="Send">' + UI.icon('send') + '</button></form>') + '</section>';
    }
    function msgHtml(m) { return '<div class="bt-msg' + (m.mine ? ' mine' : '') + '">' + esc(m.text) + '<small>' + esc(m.mine ? 'You' : m.who) + ' · ' + esc(UI.fmtDateTime(m.at)) + '</small></div>'; }

    /* ---------------------------------------------------------------- draw */
    function draw() {
      var t = SR.task(b.task), c = SR.cat(t.cat);
      if (map) { try { map.remove(); } catch (e) {} map = null; }
      view.innerHTML = '<div class="ui-wrap"><a class="bt-back" href="#board" data-go="' + (b.role === 'poster' || b.role === 'helper' ? 'jobs' : 'board') + '">' + UI.icon('back') +
        (b.role === 'poster' || b.role === 'helper' ? 'My jobs' : 'Bounty board') + '</a>' +
        '<div class="bt-grid"><header class="ui-card bt-head"><div class="top">' + SR.ti(b.task, 'lg') + '<div><div class="catname">' + esc(c.name) + ' · ' + esc(t.name) + '</div>' +
        '<div class="ui-row" style="margin-top:6px">' + SR.stamp(b.status) + (b.demo ? '<span class="ui-badge">Demo</span>' : '') + (b.role === 'poster' ? '<span class="ui-badge brand">Your bounty</span>' : '') +
        (b.role === 'helper' ? '<span class="ui-badge brand">Your job</span>' : '') + '</div></div></div>' +
        '<h1>' + esc(b.title) + '</h1><div class="bt-meta">' +
        '<span>' + UI.icon('pin') + '<b>' + esc(b.area) + '</b>' + (b.dist != null && b.role === 'visitor' ? ' · ' + SR.dist(b.dist) + ' away' : '') + '</span>' +
        '<span>' + UI.icon('calendar') + esc(SR.when(b)) + '</span>' +
        '<span>' + UI.icon('ruler') + esc((b.size || 'medium').replace(/^./, function (x) { return x.toUpperCase(); })) + ' job</span>' +
        (b.vehicle ? '<span>' + UI.icon('route') + 'Needs a vehicle</span>' : '') +
        '<span>' + UI.icon('clock') + 'Posted ' + esc(UI.ago(b.created)) + '</span></div></header>' +
        '<aside class="bt-side">' + sidePanel() + '</aside><div class="bt-main">' + mainCol() + '</div></div></div>';
      var pf = view.querySelector('[data-up]');
      up = pf ? SR.uploader(pf, 6, 'Add photo') : null;
      var vf = view.querySelector('[data-validate]');
      if (vf) liveVerdict(vf);
      var chat = view.querySelector('[data-chat]');
      if (chat) chat.scrollTop = chat.scrollHeight;
      drawMap();
      if (b.role === 'helper' && b.validation && b.validation.bonus_earned && !UI.store.get('cheer.' + b.id)) { UI.store.set('cheer.' + b.id, 1); SR.confetti(); }
    }
    function drawMap() {
      SR.leaflet().then(function (L) {
        var box = view.querySelector('[data-map]');
        if (!alive || !box) return;
        box.innerHTML = '';
        var exact = b.exact, ll = exact ? [exact.lat, exact.lng] : [b.lat, b.lng];
        map = L.map(box, { scrollWheelZoom: false }).setView(ll, exact ? 16 : 14);
        SR.tiles(L, map);
        if (exact) L.marker(ll, { icon: SR.pricePin(L, { label: 'Job' }, 'me') }).addTo(map);
        else L.circle(ll, { radius: 500, color: '#111', weight: 2, fillColor: '#ffd400', fillOpacity: .35 }).addTo(map);
      }, function (e) { var box = view.querySelector('[data-map]'); if (box) box.innerHTML = '<div class="sr-map-msg">' + esc(e.message) + '</div>'; });
    }

    /* ---------------------------------------------------------------- actions */
    function act(btn, promise, msg) {
      return UI.busy(btn, promise).then(function (r) { if (msg) UI.toast(msg, 'ok'); return load().then(function () { return r; }); });
    }
    function ask(o) {
      return new Promise(function (resolve) {
        var done = false;
        var m = UI.modal('<h2>' + esc(o.title) + '</h2>' + (o.text ? '<p class="muted">' + esc(o.text) + '</p>' : '') + '<form class="ui-stack" data-ask>' + o.fields +
          '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Back</button><button class="ui-btn ' + (o.danger ? 'danger solid' : 'primary') + '" type="submit">' + esc(o.ok) + '</button></div></form>',
        { onclose: function () { if (!done) resolve(null); } });
        m.el.querySelector('[data-ask]').addEventListener('submit', function (e) {
          e.preventDefault();
          var v = UI.formData(e.target), btn = e.target.querySelector('[type=submit]');
          UI.busy(btn, o.run(v)).then(function () { done = true; m.close(); resolve(true); load(); });
        });
      });
    }
    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-signup]')) || (t = e.target.closest('[data-signin]'))) {
        e.preventDefault(); UI.after = '#bounty/' + id; UI.go('auth', t.hasAttribute('data-signup') ? 'signup' : null); return;
      }
      if ((t = e.target.closest('[data-accept]'))) {
        var oid = t.getAttribute('data-accept'), o = (b.offers_list || []).filter(function (x) { return x.id === oid; })[0];
        UI.confirm({ title: 'Pick ' + first(o.helper.name) + ' for ' + SR.money(o.ask) + '?', text: 'They\'ll see your address and can chat with you. The other offers are declined.', ok: 'Pick ' + first(o.helper.name) })
          .then(function (yes) { if (yes) act(t, UI.api('accept_offer', oid), first(o.helper.name) + ' is booked!').then(SR.confetti); });
        return;
      }
      if ((t = e.target.closest('[data-decline]'))) { act(t, UI.api('decline_offer', t.getAttribute('data-decline')), 'Offer declined'); return; }
      if ((t = e.target.closest('[data-withdraw]'))) { act(t, UI.api('withdraw_offer', t.getAttribute('data-withdraw')), 'Offer withdrawn'); return; }
      if ((t = e.target.closest('[data-copy]'))) { SR.copy(t.getAttribute('data-copy'), 'Email'); return; }
      if ((t = e.target.closest('[data-jump]'))) { e.preventDefault(); var sec = view.querySelector('[data-proof-sec]'); if (sec) sec.scrollIntoView({ behavior: 'smooth' }); return; }
      if ((t = e.target.closest('[data-report]'))) { SR.report({ what: 'this bounty', bounty: id }); return; }
      if ((t = e.target.closest('[data-received]'))) {
        UI.confirm({ title: 'Did you get ' + SR.money(b.validation.amount_due) + '?', text: 'Check your bank app or your wallet first. This closes the job.', ok: 'Yes, I got it' })
          .then(function (yes) { if (yes) act(t, UI.api('confirm_received', id), 'Job closed. Nice work!').then(SR.confetti); });
        return;
      }
      if (e.target.closest('[data-raise]')) {
        ask({ title: 'Raise the bounty', text: 'More money gets more offers. You can raise it, not lower it.', ok: 'Raise it',
          fields: '<div class="ui-grid two"><label class="ui-field"><span>Bounty ($)</span><input type="number" name="base" min="' + b.base + '" max="500" step="1" value="' + (b.base + 5) + '"></label>' +
            '<label class="ui-field"><span>Quality bonus ($)</span><input type="number" name="bonus" min="' + b.bonus + '" max="200" step="1" value="' + b.bonus + '"></label></div>',
          run: function (v) { return UI.api('raise_bounty', id, +v.base, +v.bonus).then(function () { UI.toast('Bounty raised', 'ok'); }); } });
        return;
      }
      if (e.target.closest('[data-cancel]')) {
        var booked = b.status === 'assigned';
        ask({ title: 'Cancel this bounty?', text: booked ? 'Your helper is told why. A late cancel shows on your record.' : 'It comes off the board. Offers are declined.', ok: 'Cancel bounty', danger: true,
          fields: '<label class="ui-field"><span>Why? ' + (booked ? '' : '<em>(optional)</em>') + '</span><textarea name="reason" maxlength="300"' + (booked ? ' required minlength="10"' : '') + '></textarea></label>',
          run: function (v) { return UI.api('cancel_bounty', id, v.reason).then(function () { UI.toast('Cancelled'); }); } });
        return;
      }
      if (e.target.closest('[data-backout]')) {
        ask({ title: 'Back out of this job?', text: 'The bounty goes back on the board and the others who offered are asked again. It shows as a drop-out on your record.', ok: 'Back out', danger: true,
          fields: '<label class="ui-field"><span>Tell ' + esc(first(b.poster.name)) + ' why</span><textarea name="reason" required minlength="10" maxlength="300"></textarea></label>',
          run: function (v) { return UI.api('back_out', id, v.reason).then(function () { UI.toast('You backed out'); }); } });
        return;
      }
      if (e.target.closest('[data-dispute]')) {
        ask({ title: 'Ask a moderator', text: 'Use this when you can\'t sort it out in the chat: not paid, no-show, an unfair score, poor work. The job is frozen until a moderator decides.', ok: 'Open a dispute', danger: true,
          fields: '<label class="ui-field"><span>What went wrong?</span><textarea name="reason" required minlength="20" maxlength="800" placeholder="Facts help: dates, what was agreed, what happened."></textarea></label>',
          run: function (v) { return UI.api('open_dispute', id, v.reason).then(function () { UI.toast('A moderator will look at it.', 'ok'); }); } });
        return;
      }
      if ((t = e.target.closest('[data-star]'))) {
        var n = +t.getAttribute('data-star'), box = t.closest('[data-stars]');
        box.setAttribute('data-value', n);
        box.querySelectorAll('[data-star]').forEach(function (x) { x.classList.toggle('on', +x.getAttribute('data-star') <= n); });
      }
    });
    view.addEventListener('change', function (e) {
      var vf = e.target.closest('[data-validate]');
      if (vf) liveVerdict(vf);
      if (e.target.name === 'pm') { var eb = view.querySelector('[data-email-box]'); if (eb) eb.hidden = e.target.value !== 'etransfer'; }
    });
    view.addEventListener('submit', function (e) {
      var f = e.target, v = UI.formData(f), btn = f.querySelector('[type=submit]');
      if (f.matches('[data-offer]')) { e.preventDefault(); act(btn, UI.api('make_offer', id, v.message, v.when, +v.ask || null), 'Offer sent!'); }
      else if (f.matches('[data-chatform]')) {
        e.preventDefault();
        if (!v.text.trim()) return;
        UI.busy(btn, UI.apiQuiet('send_message', id, v.text)).then(function (r) {
          var chat = view.querySelector('[data-chat]');
          if (!b.messages.length) chat.innerHTML = '';
          b.messages.push(r.message); chat.insertAdjacentHTML('beforeend', msgHtml(r.message)); chat.scrollTop = chat.scrollHeight; f.text.value = '';
        });
      } else if (f.matches('[data-proof]')) {
        e.preventDefault();
        if (up && up.busy()) { UI.toast('Wait for the photos to finish uploading.'); return; }
        var checks = b.checklist.map(function (c, i) { return !!f['c' + i].checked; });
        act(btn, UI.api('submit_proof', id, checks, v.note, up ? up.keys() : [], v.pm, v.email || '', !!v.remember), 'Proof sent to ' + first(b.poster.name) + '!');
      } else if (f.matches('[data-validate]')) {
        e.preventDefault();
        var vc = b.checklist.map(function (c, i) { return !!f['c' + i].checked; });
        act(btn, UI.api('validate_work', id, vc, v.note), 'Validated. Now pay ' + first(b.helper.name) + '.').then(function (r) { if (r && r.bonus_earned) SR.confetti(); });
      } else if (f.matches('[data-paid]')) {
        e.preventDefault();
        act(btn, UI.api('mark_paid', id, v.method, v.ref || ''), 'Marked as paid. Thank you!');
      } else if (f.matches('[data-review]')) {
        e.preventDefault();
        var stars = +(f.querySelector('[data-stars]').getAttribute('data-value') || 0);
        if (!stars) { UI.toast('Pick 1 to 5 stars.', 'error'); return; }
        var tags = Array.prototype.slice.call(f.querySelectorAll('[name=tag]:checked')).map(function (x) { return x.value; });
        act(btn, UI.api('leave_review', id, stars, tags, v.text), 'Thanks for the review!');
      }
    });

    function load() {
      return Promise.all([SR.catalog(), UI.api('get_bounty', id)]).then(function (r) {
        if (!alive) return;
        var res = r[1];
        if (res.gone) {
          view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="ui-empty">' + UI.icon('tag') + '<h3>' + esc(res.title) + '</h3><p>This bounty is no longer open (' + esc((SR.STATUS[res.status] || res.status).toLowerCase()) + ').</p>' +
            '<a class="ui-btn primary" href="#board" data-go="board">See open bounties</a></div></div>';
          return;
        }
        b = res.bounty;
        document.title = b.title + ' · ' + UI.config.name;
        draw();
      }, function (err) {
        view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="ui-empty">' + UI.icon('tag') + '<h3>Bounty not found</h3><p>' + esc(err.message) + '</p><a class="ui-btn primary" href="#board" data-go="board">See open bounties</a></div></div>';
      });
    }
    return { ready: load(), destroy: function () { alive = false; if (map) { try { map.remove(); } catch (e) {} } } };
  });
})();

/* ===== jobs.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['todo', 'To do', 'bell'], ['posted', 'Posted', 'tag'], ['doing', 'Doing', 'hand'], ['offers', 'Offers sent', 'send']];

  function row(j, role) {
    var wait = !j.urgent;
    return '<a class="jb-row" href="#bounty/' + esc(j.id) + '" data-go="bounty/' + esc(j.id) + '">' + SR.ti(j.task) +
      '<div><h3>' + esc(j.title) + '</h3><div class="meta">' + SR.stamp(j.status) +
      (j.needs ? '<span class="needs' + (wait ? ' wait' : '') + '">' + UI.icon(wait ? 'clock' : 'bell') + esc(j.needs) + '</span>' : '') +
      '<span>' + (role === 'poster' ? (j.other ? 'Helper: <b>' + esc(j.other) + '</b>' : UI.plural(j.offers, 'offer')) : 'For <b>' + esc(j.other) + '</b>') + '</span>' +
      '<span>' + UI.icon('pin') + esc(j.area) + '</span><span>Updated ' + esc(UI.ago(j.updated)) + '</span></div></div>' +
      '<span class="sr-tag sm"><b>' + SR.money(j.amount_due != null ? j.amount_due : j.base) + '</b>' + (j.bonus && j.amount_due == null ? '<i>+' + SR.money(j.bonus) + '</i>' : '') + '</span>' +
      (j.unread ? '<span class="dot">' + j.unread + '</span>' : '') + '</a>';
  }

  UI.page('jobs', { title: 'My jobs', nav: 'My jobs', icon: 'clipboard', auth: 'user', order: 30 }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'todo';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:300px"></div></div>';
    function draw(d) {
      var todo = d.posted.filter(function (j) { return j.urgent; }).map(function (j) { return [j, 'poster']; })
        .concat(d.doing.filter(function (j) { return j.urgent; }).map(function (j) { return [j, 'helper']; }));
      var live = function (j) { return ['open', 'review', 'assigned', 'submitted', 'validated', 'paid', 'disputed'].indexOf(j.status) >= 0; };
      var counts = { todo: todo.length, posted: d.posted.filter(live).length, doing: d.doing.filter(live).length, offers: d.offers.filter(function (o) { return o.status === 'pending'; }).length };
      var body = '';
      if (tab === 'todo') body = todo.length ? '<div class="jb-list">' + todo.map(function (x) { return row(x[0], x[1]); }).join('') + '</div>' :
        '<div class="ui-empty">' + UI.icon('check') + '<h3>All caught up</h3><p>Nothing needs you right now. Post a bounty, or find one to do.</p>' +
        '<div class="ui-row" style="justify-content:center"><a class="ui-btn primary" href="#post" data-go="post">' + UI.icon('plus') + 'Post a bounty</a><a class="ui-btn" href="#board" data-go="board">Browse bounties</a></div></div>';
      if (tab === 'posted' || tab === 'doing') {
        var list = tab === 'posted' ? d.posted : d.doing, role = tab === 'posted' ? 'poster' : 'helper';
        var a = list.filter(live), b = list.filter(function (j) { return !live(j); });
        body = list.length ? (a.length ? '<div class="jb-group">In progress</div><div class="jb-list">' + a.map(function (j) { return row(j, role); }).join('') + '</div>' : '') +
          (b.length ? '<div class="jb-group">Finished and closed</div><div class="jb-list">' + b.map(function (j) { return row(j, role); }).join('') + '</div>' : '') :
          '<div class="ui-empty">' + UI.icon(tab === 'posted' ? 'tag' : 'hand') + '<h3>' + (tab === 'posted' ? 'No bounties yet' : 'No jobs yet') + '</h3><p>' +
          (tab === 'posted' ? 'Leaves, snow, a couch to haul? Post it from $20.' : 'Find a bounty near you and send an offer.') + '</p>' +
          '<a class="ui-btn primary" href="#' + (tab === 'posted' ? 'post' : 'board') + '" data-go="' + (tab === 'posted' ? 'post' : 'board') + '">' + (tab === 'posted' ? 'Post a bounty' : 'Browse bounties') + '</a></div>';
      }
      if (tab === 'offers') body = d.offers.length ? '<div class="jb-list">' + d.offers.map(function (o) {
        return '<a class="jb-row" href="#bounty/' + esc(o.bounty) + '" data-go="bounty/' + esc(o.bounty) + '">' + SR.ti(o.task) + '<div><h3>' + esc(o.title) + '</h3><div class="meta">' +
          '<span class="ui-badge ' + (o.status === 'pending' ? 'warn' : '') + '">' + (o.status === 'pending' ? 'Waiting for an answer' : o.status === 'declined' ? 'Not picked' : 'Closed') + '</span>' +
          '<span>' + UI.icon('pin') + esc(o.area) + '</span><span>Sent ' + esc(UI.ago(o.created)) + '</span></div></div><span class="sr-tag sm"><b>' + SR.money(o.ask) + '</b></span></a>';
      }).join('') + '</div>' : '<div class="ui-empty">' + UI.icon('send') + '<h3>No offers sent</h3><p>Offers you make on bounties show up here.</p><a class="ui-btn primary" href="#board" data-go="board">Browse bounties</a></div>';

      var owe = d.posted.filter(function (j) { return j.status === 'validated'; }).reduce(function (s, j) { return s + (j.amount_due || 0); }, 0);
      var owed = d.doing.filter(function (j) { return j.status === 'validated' || j.status === 'paid'; }).reduce(function (s, j) { return s + (j.amount_due || 0); }, 0);
      view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>My jobs</h1><p class="muted">What you posted, what you\'re doing, and what needs you.</p></div>' +
        '<a class="ui-btn primary" href="#post" data-go="post">' + UI.icon('plus') + 'Post a bounty</a></div>' +
        (d.limits.post ? '<div class="ui-note" style="margin-bottom:16px">' + UI.icon('info') + ' ' + esc(d.limits.post) + '</div>' : '') +
        '<div class="jb-sum"><div class="ui-card"><b>' + counts.todo + '</b><span>need you</span></div><div class="ui-card"><b>' + counts.posted + '</b><span>live bounties</span></div>' +
        '<div class="ui-card"><b>' + counts.doing + '</b><span>jobs on the go</span></div>' +
        '<a class="ui-card" href="#ledger" data-go="ledger" style="text-decoration:none"><b>' + SR.money(owed) + '</b><span>coming to you' + (owe ? ' · you owe ' + SR.money(owe) : '') + '</span></a></div>' +
        '<nav class="ui-tabs">' + TABS.map(function (t) {
          return '<a href="#jobs/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + (counts[t[0]] ? ' <span class="count">' + counts[t[0]] + '</span>' : '') + '</a>';
        }).join('') + '</nav>' + body + '</div>';
    }
    return Promise.all([SR.catalog(), UI.api('get_jobs')]).then(function (r) { draw(r[1]); });
  });
})();

/* ===== landing.html ===== */
// Watch section: swap the video's cover for YouTube's player (privacy-enhanced) only when it's pressed.
  if (!window.__ytFilm) {
    window.__ytFilm = true;
    document.addEventListener('click', function (e) {
      var b = e.target && e.target.closest ? e.target.closest('[data-yt-film]') : null;
      if (!b) return;
      var f = document.createElement('iframe');
      f.src = 'https://www.youtube-nocookie.com/embed/' + b.getAttribute('data-yt-film') + '?autoplay=1&rel=0&playsinline=1';
      f.title = b.getAttribute('data-yt-title') || 'Video';
      f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      f.allowFullscreen = true;
      f.referrerPolicy = 'strict-origin-when-cross-origin';
      b.parentNode.replaceChild(f, b);
    });
  }
(function () {
  var COPY = {
    eyebrow: 'Leaves · Snow · Junk · 40 neighbourly jobs',
    title: 'Post a bounty. <em>A neighbour</em> gets it done.',
    lead: 'Need the leaves raked, the driveway shovelled or an old couch gone? Put a price on it (from $20) and people nearby send offers. ' +
          'Pay cash or by Interac e-Transfer once the work checks out, with a bonus for great work.',
    proof: ['From $20', 'No fees, no middleman', 'Photo proof + quality score', 'Built against scams'],
    faq: [
      ['How much does it cost?', 'Nothing. No fees for posting, no cut of the bounty. You pay your helper directly, in cash or by Interac e-Transfer.'],
      ['Why not pay in the app?', 'Moving other people\'s money is regulated in Canada. Until a licensed payment partner is plugged in, you pay each other directly and the app keeps the record: amounts, references, dates.'],
      ['How is the quality bonus decided?', 'With a checklist you write when you post (we suggest one for every task). You tick what was done; the share of ticked items is the score. If you offered "$10 at 80%", 4 of 5 items unlocks it. Unticking needs a reason the helper can read.'],
      ['What if they don\'t pay?', 'Once a job is validated, the poster has 3 days to pay. Until they do, they can\'t post or hire. Helpers can open a dispute; a moderator decides, and a lost dispute is a strike. Three strikes pause the account. Every poster\'s profile shows how fast they pay.'],
      ['Who sees my address?', 'Only the helper you pick, once you pick them. The board shows a neighbourhood name and a circle about 500 m wide.'],
      ['Can teenagers help?', 'Yes, from 16. Shovelling and raking are classic first jobs. We ask anyone under 18 to get a parent\'s OK and to stick to outdoor jobs.'],
      ['What jobs aren\'t allowed?', 'Anything that needs a licence (electrical, plumbing, gas, roofing, tree felling), childcare and rides, hazardous waste, buying things with the helper\'s money, gift cards and packages for strangers. A scanner sends anything risky to a moderator first.']
    ]
  };

  // The hero map: a made-up Montréal block (the street grid tilts like the real one), a park, the river,
  // and bounty pins from the real task catalogue. Pins sit right of the card on desktop, across the top on phones.
  function heroArt(CAT) {
    var streets = '', i;
    for (i = -6; i < 22; i++) streets += '<path d="M' + (i * 110) + ' -200 L' + (i * 110 + 520) + ' 900"/>';
    for (i = -4; i < 14; i++) streets += '<path d="M-300 ' + (i * 86) + ' L1600 ' + (i * 86 - 300) + '"/>';
    var map = '<div class="lp-map" aria-hidden="true"><svg viewBox="0 0 1280 640" preserveAspectRatio="xMidYMid slice">' +
      '<rect width="1280" height="640" fill="var(--land)"/>' +
      '<path d="M1280 470 C1120 520 1010 560 900 640 L1280 640 Z" fill="var(--water)"/>' +
      '<path d="M760 120 L930 60 L990 190 L820 250 Z" fill="var(--park)"/>' +
      '<path d="M1080 300 L1180 262 L1214 350 L1112 388 Z" fill="var(--park)"/>' +
      '<g stroke="var(--casing)" stroke-width="16" fill="none">' + streets + '</g>' +
      '<g stroke="var(--street)" stroke-width="11" fill="none">' + streets + '</g>' +
      '<path d="M560 -40 L1340 520" stroke="var(--casing)" stroke-width="26" fill="none"/><path d="M560 -40 L1340 520" stroke="var(--street)" stroke-width="20" fill="none"/>' +
      '<g fill="var(--label)" font-family="inherit" font-size="13" font-weight="700" letter-spacing="2">' +
        '<text x="820" y="168" transform="rotate(-20 820 168)">PARC</text>' +
        '<text x="1010" y="600" transform="rotate(-14 1010 600)">FLEUVE</text>' +
        '<text x="980" y="300" transform="rotate(35.6 980 300)">BOUL. SAINT-LAURENT</text></g>' +
      '</svg></div>';
    var tasks = [], seen = {};
    ((CAT && CAT.tasks) || []).forEach(function (t) { if (!seen[t.cat] && tasks.length < 7) { seen[t.cat] = 1; tasks.push(t); } });
    var spots = [[58, 30], [72, 22], [86, 36], [66, 58], [80, 66], [92, 54], [74, 86]];
    var pins = tasks.map(function (t, n) {
      var p = (t.prices && t.prices[0]) || 20;
      return '<div class="lp-pin' + (n === 3 ? ' hot' : '') + '" style="left:' + spots[n][0] + '%;top:' + spots[n][1] + '%;animation-delay:' + (n * 0.12) + 's">' +
        SR.ti(t.key, 'sm') + SR.tag({ base: p, bonus: n % 2 ? 10 : 0, bar: 80 }, 'sm') + '</div>';
    }).join('');
    var pop = tasks[3] ? '<div class="lp-pop" style="left:66%;top:58%"><b>' + UI.esc(tasks[3].name) + '</b>Rosemont · about 400 m away' +
      '<div class="ui-row">' + SR.tag({ base: (tasks[3].prices || [35])[0], bonus: 10, bar: 80 }, 'sm') + '<span class="muted">3 offers</span></div></div>' : '';
    return map + '<div class="lp-pins" aria-hidden="true"><span class="lp-you" style="left:76%;top:48%"></span>' + pins + pop + '</div>' +
      '<span class="lp-legend" aria-hidden="true">Bounties near you, right now</span>';
  }

  UI.page('landing', { title: 'Neighbourhood bounties' }, function (view, ctx) {
    var me = ctx.me, C = COPY, esc = UI.esc;
    function draw(CAT) {
      var primary = me ? '<a class="ui-btn primary lg" href="#board" data-go="board">Open the board ' + UI.icon('arrow') + '</a><a class="ui-btn lg" href="#post" data-go="post">' + UI.icon('plus') + 'Post a bounty</a>'
        : '<a class="ui-btn primary lg" href="#auth/signup" data-go="auth/signup">' + UI.icon('plus') + 'Post a bounty, free</a>' +
          '<a class="ui-btn lg" href="#board" data-go="board">' + UI.icon('search') + 'Browse bounties</a>';
      view.innerHTML =
        '<section class="lp-hero">' + heroArt(CAT) + '<div class="ui-wrap"><div class="lp-card"><span class="eyebrow">' + esc(C.eyebrow) + '</span><h1>' + C.title + '</h1><p class="lp-lead">' + esc(C.lead) + '</p>' +
          '<div class="lp-cta">' + primary + '</div>' +
          '<div class="lp-proof">' + C.proof.map(function (p) { return '<span>' + UI.icon('check') + esc(p) + '</span>'; }).join('') + '</div></div></div></section>' +

        '<section class="lp-section ytf" id="watch"><div class="ui-wrap"><div class="ytf-in"><div class="ytf-copy"><div class="eyebrow"><svg viewBox="0 0 28 20" width="20" height="14" aria-hidden="true"><rect width="28" height="20" rx="5" fill="#FF0033"/><path d="M11.2 5.8v8.4l7.3-4.2z" fill="#fff"/></svg>Watch</div><h2>See Service Request in about a minute</h2><p>A short video tour of what Service Request does and how it works.</p><a class="ytf-link" href="https://www.youtube.com/watch?v=_Qj7nniw9cw" target="_blank" rel="noopener">Watch on YouTube &#8599;</a></div><div><div class="ytf-frame"><button type="button" class="ytf-cover" data-yt-film="_Qj7nniw9cw" data-yt-title="Service Request video" aria-label="Play the Service Request video (1:12)"><img src="_/theme/yt-cover.jpg" alt="" loading="lazy" decoding="async" width="960" height="540"><span class="ytf-play" aria-hidden="true"><svg viewBox="0 0 68 48" width="68" height="48"><path d="M66.5 7.7a8.5 8.5 0 0 0-6-6C55.3.3 34 .3 34 .3s-21.3 0-26.5 1.4a8.5 8.5 0 0 0-6 6C.1 13 .1 24 .1 24s0 11 1.4 16.3a8.5 8.5 0 0 0 6 6c5.2 1.4 26.5 1.4 26.5 1.4s21.3 0 26.5-1.4a8.5 8.5 0 0 0 6-6C67.9 35 67.9 24 67.9 24s0-11-1.4-16.3z" fill="#FF0033"/><path d="M45 24 27 14v20z" fill="#fff"/></svg></span><span class="ytf-len">1:12</span></button></div><p class="ytf-note">The video loads from YouTube when you press play.</p></div></div></div></section>' +
        '<section class="lp-section" id="how"><div class="ui-wrap"><div class="lp-head"><h2>Two sides, one board</h2><p>Post what you need, or earn by helping out around the block.</p></div><div class="lp-sides">' +
          '<div class="ui-card lp-side"><h3>' + UI.icon('tag') + 'If you need a hand</h3><ol>' +
            '<li><span><b>Post a bounty</b><span>Pick from 40 jobs, add photos, set a price from $20 and an optional quality bonus.</span></span></li>' +
            '<li><span><b>Pick a helper</b><span>Compare offers, ratings and how often they win the bonus. Only they get your address.</span></span></li>' +
            '<li><span><b>Check the proof</b><span>They send photos. You tick the checklist: that\'s the quality score.</span></span></li>' +
            '<li><span><b>Pay directly</b><span>Cash or e-Transfer, the exact amount. Their e-Transfer email appears only now.</span></span></li></ol></div>' +
          '<div class="ui-card lp-side helper"><h3>' + UI.icon('hand') + 'If you want to earn</h3><ol>' +
            '<li><span><b>Browse the board</b><span>Bounties on a map near you, by distance, price or date. Filter for bonus jobs.</span></span></li>' +
            '<li><span><b>Send an offer</b><span>Say when you can come. Bigger job than described? Counter-offer.</span></span></li>' +
            '<li><span><b>Do it well, snap it</b><span>Tick your checklist and send photos. No answer in 48 h? Your checklist counts.</span></span></li>' +
            '<li><span><b>Get paid, get rated</b><span>Cash or e-Transfer. Build a record, earn badges like Snow warrior and Leaf legend.</span></span></li></ol></div></div></div></section>' +

        '<section class="lp-section"><div class="ui-wrap"><div class="ui-card lp-bonus"><div><span class="eyebrow">The quality bonus</span><h2 style="margin-top:12px">Great work pays more. Fairly.</h2>' +
          '<p class="muted">Every bounty has a checklist anyone can check. The share of ticked items is the score. Set a bonus and a bar, and great helpers go for it.</p>' +
          '<div class="lp-math">$20 bounty + <mark>$10 at 80%</mark></div><p class="small muted" style="margin:0">Unticking an item needs a written reason. Every poster\'s profile shows how often they pay the bonus.</p></div>' +
          '<div><ul class="lp-check">' + [['Lawn raked clear of leaves', 1], ['Garden beds cleared', 1], ['Leaves bagged in paper yard bags', 1], ['Bags placed at the curb', 1], ['Walkway and steps swept', 0]].map(function (c) {
            return '<li class="' + (c[1] ? 'y' : 'n') + '"><i>' + (c[1] ? '✓' : '✕') + '</i>' + esc(c[0]) + '</li>';
          }).join('') + '</ul><p style="font-weight:800;margin:10px 0 0">4 of 5 = 80% → the helper gets <span style="background:#ffd400;color:#111;padding:2px 6px;border:2px solid #111">$30</span></p></div></div></div></section>' +

        '<section class="lp-shield"><div class="ui-wrap" style="padding-top:0;padding-bottom:0"><div class="lp-head"><h2>Built against scams and no-pays</h2><p>Cash jobs attract tricksters. Here\'s what stops them.</p></div><div class="lp-feats">' +
          [['flag', 'A scanner reads every bounty', 'Gift cards, crypto, cheques, "send the rest back", packages for strangers, roofs, wiring: flagged for a moderator before reaching the board.'],
           ['eyeoff', 'Contact details hidden', 'Phone numbers, emails and links are blanked out until you\'re matched, so scammers can\'t pull you off the app.'],
           ['bolt', 'Pay within 3 days', 'Once a job is validated, the poster can\'t post or hire again until they pay. Their pay record is public.'],
           ['ruler', 'Checklists, not vibes', 'The score is what\'s ticked, with reasons for anything missed. No answer in 48 h? The helper\'s checklist counts.'],
           ['shield', 'Strikes and disputes', 'Moderators settle disputes. Upheld reports are strikes; three pause the account. Three reports pull a bounty off the board.'],
           ['star', 'Reputation you can\'t fake', 'Records come from finished jobs only. Reviews are blind until both sides write them, and each neighbour counts once.']].map(function (f) {
            return '<div class="ui-card lp-feat">' + UI.icon(f[0]) + '<h3>' + esc(f[1]) + '</h3><p>' + esc(f[2]) + '</p></div>';
          }).join('') + '</div><p style="text-align:center;margin:26px 0 0"><a class="ui-btn primary" href="#rules" data-go="rules">' + UI.icon('shield') + 'Read the rules &amp; safety guide</a></p></div></section>' +

        '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>40 jobs that need no degree</h2><p>Each with a suggested price and a ready-made checklist. Tap one to post it.</p></div><div class="lp-wall">' +
          CAT.tasks.map(function (t) {
            return '<a href="#post/' + esc(t.key) + '" data-go="' + (me ? 'post/' + esc(t.key) : 'auth/signup') + '">' + SR.ti(t.key, 'sm') + esc(t.name) + ' <small>from ' + SR.money(t.prices[0]) + '</small></a>';
          }).join('') + '</div></div></section>' +

        '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Questions</h2></div><div class="lp-faq">' +
          C.faq.map(function (q) { return '<details><summary>' + esc(q[0]) + '</summary><p>' + esc(q[1]) + '</p></details>'; }).join('') + '</div></div></section>' +

        '<section class="lp-section"><div class="ui-wrap"><div class="lp-band"><div><h2>Got a job that needs doing?</h2><p>Post it in two minutes. The neighbours are ready.</p></div>' +
          (me ? '<a class="ui-btn lg" href="#post" data-go="post">' + UI.icon('plus') + 'Post a bounty</a>' : '<a class="ui-btn lg" href="#auth/signup" data-go="auth/signup">' + UI.icon('plus') + 'Join free</a>') +
        '</div></div></section>';
    }
    return SR.catalog().then(draw);
  });
})();

/* ===== ledger.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('ledger', { title: 'Ledger', nav: 'Ledger', icon: 'wallet', auth: 'user', order: 40 }, function (view) {
    var data = null, filter = 'all';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:300px"></div></div>';
    function draw() {
      var T = data.totals, rows = data.rows.filter(function (r) { return filter === 'all' || r.dir === filter; });
      view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Ledger</h1><p class="muted">Every bounty you earned or paid. The money moves in cash or by e-Transfer; this is the record.</p></div>' +
        (data.rows.length ? '<button class="ui-btn" type="button" data-csv>' + UI.icon('copy') + 'Export CSV</button>' : '') + '</div>' +
        '<div class="lg-tot"><div class="ui-card hi"><b>' + SR.money(T.earned) + '</b><span>earned' + (T.bonus ? ' (' + SR.money(T.bonus) + ' in bonuses)' : '') + '</span></div>' +
        '<div class="ui-card"><b>' + SR.money(T.coming) + '</b><span>coming to you</span></div>' +
        '<div class="ui-card"><b>' + SR.money(T.spent) + '</b><span>paid to neighbours</span></div>' +
        '<div class="ui-card"><b' + (T.owe ? ' style="color:var(--c-bad)"' : '') + '>' + SR.money(T.owe) + '</b><span>you owe</span></div></div>' +
        '<div class="ui-row" style="margin-bottom:14px"><div class="ui-seg">' + [['all', 'All'], ['in', 'Earned'], ['out', 'Paid']].map(function (f) {
          return '<button type="button" data-filter="' + f[0] + '" class="' + (filter === f[0] ? 'on' : '') + '">' + f[1] + '</button>';
        }).join('') + '</div></div>' +
        (rows.length ? '<div class="ui-card" style="padding:6px 16px"><table class="lg-table"><thead><tr><th>Bounty</th><th>With</th><th>How</th><th>State</th><th style="text-align:right">Amount</th></tr></thead><tbody>' +
          rows.map(function (r) {
            return '<tr><td><a href="#bounty/' + esc(r.id) + '" data-go="bounty/' + esc(r.id) + '">' + esc(r.title) + '</a><div class="small muted">' + esc(UI.fmtDate(r.at)) +
              (r.quality != null ? ' · quality ' + r.quality + '%' : '') + (r.bonus ? ' · +' + SR.money(r.bonus) + ' bonus' : '') + '</div></td>' +
              '<td class="who">' + (r.dir === 'in' ? 'From ' : 'To ') + esc(r.other) + '</td><td class="how">' + esc(SR.PAY[r.method] || '') + (r.ref ? ' · ' + esc(r.ref) : '') + '</td>' +
              '<td><span class="st ' + esc(r.state) + '">' + esc({ owed: 'Owed', sent: 'Sent', settled: 'Settled', disputed: 'Disputed' }[r.state]) + '</span></td>' +
              '<td class="amt ' + r.dir + '">' + (r.dir === 'in' ? '+' : '−') + SR.money(r.amount) + '</td></tr>';
          }).join('') + '</tbody></table></div>' :
          '<div class="ui-empty">' + UI.icon('wallet') + '<h3>Nothing here yet</h3><p>Once a job is validated, what\'s owed shows up here, then what was paid.</p><a class="ui-btn primary" href="#board" data-go="board">Find a bounty</a></div>') +
        '<div class="ui-card flat lg-why">' + UI.icon('bank') + '<div><h3 style="margin:0 0 6px">Why doesn\'t the money go through the app?</h3>' +
        '<p class="muted" style="margin:0">Moving other people\'s money is regulated in Canada, so for now you pay each other directly: cash in hand or an Interac e-Transfer. ' +
        'No fees, no wallet to top up. The app keeps the record, the references and the dates, so there\'s a paper trail if anything goes wrong. In-app payments may come later.</p></div></div></div>';
    }
    view.addEventListener('click', function (e) {
      var f = e.target.closest('[data-filter]');
      if (f) { filter = f.getAttribute('data-filter'); draw(); return; }
      if (e.target.closest('[data-csv]')) {
        var q = function (v) { return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'; };
        var csv = [['date', 'bounty', 'direction', 'with', 'method', 'reference', 'state', 'quality', 'bonus', 'amount']].concat(data.rows.map(function (r) {
          return [r.at ? r.at.slice(0, 10) : '', r.title, r.dir === 'in' ? 'earned' : 'paid', r.other, r.method, r.ref, r.state, r.quality, r.bonus, r.amount];
        })).map(function (row) { return row.map(q).join(','); }).join('\n');
        var a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
        a.download = 'service-request-ledger.csv'; document.body.appendChild(a); a.click(); a.remove();
      }
    });
    return UI.api('get_ledger').then(function (d) { data = d; draw(); });
  });
})();

/* ===== neighbour.html ===== */
(function () {
  var esc = UI.esc;
  var BADGE_ICON = { first: 'check', trusted: 'shield', leaf: 'leaf', snow: 'snow', lift: 'box', junk: 'bin', bonus: 'gift', five: 'star', prompt: 'bolt', fair: 'ruler' };
  UI.page('neighbour', { title: 'Neighbour' }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:300px"></div></div>';
    function draw(p) {
      document.title = p.name + ' · ' + UI.config.name;
      var h = p.as_helper, po = p.as_poster;
      var helps = h.jobs > 0 || p.skills.length, posts = po.posted > 0;
      var revs = p.reviews;
      view.innerHTML = '<div class="ui-wrap"><div class="nb-head"><span class="ui-avatar">' + esc(UI.initials(p.name)) + '</span><div><h1>' + esc(p.name) + '</h1><div class="sub">' +
        (p.area ? '<span>' + UI.icon('pin') + esc(p.area) + '</span>' : '') + '<span>' + UI.icon('calendar') + 'Neighbour since ' + esc(UI.fmtDate(p.joined, { month: 'long', year: 'numeric' })) + '</span>' +
        (h.standing === 'good' && (h.jobs || po.completed) ? '<span class="ui-badge good">' + UI.icon('shield') + 'Good standing</span>' : '') +
        (h.standing === 'warned' ? '<span class="ui-badge warn">' + UI.icon('info') + 'Has a moderator warning</span>' : '') + '</div></div>' +
        '<div class="ui-row">' + (p.me ? '<a class="ui-btn" href="#profile" data-go="profile">' + UI.icon('edit') + 'Edit my profile</a>' : '<button class="ui-btn ghost sm" type="button" data-report>' + UI.icon('flag') + 'Report</button>') + '</div></div>' +
        '<div class="nb-stats">' +
        (helps ? '<div class="ui-card"><b>' + h.jobs + '</b><span>jobs done</span></div><div class="ui-card"><b>' + (h.rating ? '★ ' + Number(h.rating).toFixed(1) : '–') + '</b><span>as a helper (' + h.reviews + ')</span></div>' +
          '<div class="ui-card"><b>' + h.bonus_won + '</b><span>quality bonuses won</span></div>' : '') +
        (posts ? '<div class="ui-card"><b>' + po.completed + '</b><span>bounties completed</span></div><div class="ui-card"><b>' + (po.paid ? po.paid_fast + '/' + po.paid : '–') + '</b><span>paid within 2 days</span></div>' +
          (po.bonus_jobs ? '<div class="ui-card"><b>' + po.bonus_paid + '/' + po.bonus_jobs + '</b><span>bonuses paid</span></div>' : '') : '') +
        (!helps && !posts ? '<div class="ui-card"><b>New</b><span>no jobs yet</span></div>' : '') + '</div>' +
        '<div class="nb-grid"><div class="ui-stack">' +
        (p.bio ? '<div class="ui-card"><h3 style="margin-top:0">About</h3><p style="white-space:pre-wrap;margin:0">' + esc(p.bio) + '</p>' +
          (p.skills.length ? '<div class="ui-row" style="margin-top:12px">' + p.skills.map(function (s) { return '<span class="ui-badge brand">' + esc(s) + '</span>'; }).join('') + '</div>' : '') + '</div>' : '') +
        (p.badges.length ? '<div class="ui-card"><h3 style="margin-top:0">Badges</h3><div class="nb-badges">' + p.badges.map(function (b) {
          return '<span class="nb-badge" title="' + esc(b.why) + '"><i>' + UI.icon(BADGE_ICON[b.key] || 'star') + '</i><span><b>' + esc(b.name) + '</b><small>' + esc(b.why) + '</small></span></span>';
        }).join('') + '</div></div>' : '') +
        '<div class="ui-card"><h3 style="margin-top:0">Reviews <span class="ui-badge">' + revs.length + '</span></h3>' + (revs.length ? revs.map(function (r) {
          return '<div class="nb-rev"><div class="top">' + SR.stars(r.stars) + '<b>' + esc(r.author) + '</b><span class="ui-badge">' + (r.role === 'helper' ? 'as a helper' : 'as a poster') + '</span>' +
            '<span class="muted small">' + esc(r.bounty) + ' · ' + esc(UI.ago(r.at)) + '</span></div>' + (r.text ? '<p>' + esc(r.text) + '</p>' : '') +
            (r.tags.length ? '<div class="ui-row" style="margin-top:8px">' + r.tags.map(function (t) { return '<span class="ui-badge">' + esc(t) + '</span>'; }).join('') + '</div>' : '') + '</div>';
        }).join('') : '<p class="muted" style="margin:0">No reviews yet. Reviews appear once both sides have reviewed a job (or a week after it closed).</p>') + '</div></div>' +
        '<div class="ui-stack">' + (p.open.length ? '<div class="ui-card"><h3 style="margin-top:0">Open bounties</h3><div class="ui-stack">' + p.open.map(function (b) {
          return '<a class="ui-row" style="text-decoration:none;flex-wrap:nowrap" href="#bounty/' + esc(b.id) + '" data-go="bounty/' + esc(b.id) + '">' + SR.ti(b.task, 'sm') +
            '<span style="flex:1;min-width:0"><b style="display:block">' + esc(b.title) + '</b><span class="small muted">' + esc(b.area) + '</span></span><span class="sr-tag sm"><b>' + SR.money(b.base) + '</b></span></a>';
        }).join('') + '</div></div>' : '') +
        '<div class="ui-card flat"><h4 style="margin-top:0">' + UI.icon('shield') + ' How records work</h4><p class="small muted" style="margin:0">Numbers come from finished bounties only: nobody can type them in. ' +
        'Each neighbour counts once in a rating, and reviews stay blind until both sides have written theirs.</p></div></div></div></div>';
      view.querySelector('[data-report]') && view.querySelector('[data-report]').addEventListener('click', function () { SR.report({ what: p.name, user: p.id }); });
    }
    return Promise.all([SR.catalog(), UI.api('get_neighbour', ctx.args[0])]).then(function (r) { draw(r[1].person); }, function (e) {
      view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="ui-empty">' + UI.icon('user') + '<h3>Neighbour not found</h3><p>' + esc(e.message) + '</p><a class="ui-btn" href="#board" data-go="board">Back to the board</a></div></div>';
    });
  });
})();

/* ===== post.html ===== */
(function () {
  var esc = UI.esc;
  var STEPS = [['task', 'Task'], ['details', 'Details'], ['where', 'Where'], ['bounty', 'Bounty'], ['review', 'Post']];

  UI.page('post', { title: 'Post a bounty', nav: 'Post', icon: 'plus', auth: 'user', order: 20 }, function (view, ctx) {
    var CAT = null, step = 0, seen = 0, catFilter = 'season', query = '', up = null, map = null, alive = true, limit = null;
    var P = { task: null, title: '', details: '', size: 'medium', when_date: '', when_note: '', lat: null, lng: null, area: '', address: '',
              base: 20, bonus: 10, bar: 80, checklist: [], pay_method: 'either', photo_keys: [] };
    var useBonus = true;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:400px"></div></div>';

    function task() { return CAT.byKey[P.task]; }
    function chooseTask(key) {
      var t = CAT.byKey[key];
      if (!t) return;
      var changed = P.task !== key;
      P.task = key;
      if (changed) {
        P.title = t.key === 'other' ? '' : t.name;
        P.checklist = t.checklist.slice();
        P.base = t.prices[{ small: 0, medium: 1, large: 2 }[P.size]];
        P.bonus = useBonus ? Math.max(5, Math.min(P.base, Math.round(P.base / 4 / 5) * 5 || 5)) : 0;
      }
    }

    function frame() {
      view.innerHTML = '<div class="ui-wrap"><div class="ps-steps" role="tablist">' + STEPS.map(function (s, i) {
        return '<button type="button" data-step="' + i + '" class="' + (i === step ? 'on' : i < seen || i < step ? 'done' : '') + '"' + (i > seen ? ' disabled' : '') + '><b>' + (i < step ? '✓' : i + 1) + '</b><span>' + s[1] + '</span></button>';
      }).join('') + '</div>' + (limit ? '<div class="ui-note" style="margin-bottom:16px">' + UI.icon('info') + ' ' + esc(limit) + ' <a href="#jobs" data-go="jobs">My jobs</a></div>' : '') +
        '<div class="ps-layout"><div data-body></div><aside class="ps-aside" data-aside></aside></div></div>';
      var body = view.querySelector('[data-body]');
      body.innerHTML = [stepTask, stepDetails, stepWhere, stepBounty, stepReview][step]() +
        '<div class="ps-nav">' + (step ? '<button class="ui-btn" type="button" data-prev>' + UI.icon('back') + 'Back</button>' : '<span></span>') +
        (step < 4 ? '<button class="ui-btn primary" type="button" data-next' + (step === 0 && !P.task ? ' disabled' : '') + '>Next ' + UI.icon('arrow') + '</button>'
          : '<button class="ui-btn primary lg" type="button" data-post' + (limit ? ' disabled' : '') + '>' + UI.icon('tag') + 'Post the bounty</button>') + '</div>';
      aside();
      if (step === 1) up = SR.uploader(view.querySelector('[data-up]'), Math.max(0, 4 - P.photo_keys.length), 'Add a photo');
      if (step === 2) spotMap();
      if (step === 3) explain();
      window.scrollTo(0, 0);
    }

    function aside() {
      var box = view.querySelector('[data-aside]');
      if (!P.task) { box.innerHTML = '<div class="ui-card flat"><h4 style="margin-top:0">' + UI.icon('bulb') + ' How it works</h4><ol class="small muted" style="padding-left:18px;margin:0">' +
        '<li>Post a bounty: what, where, how much (from $20).</li><li>Neighbours send offers. You pick one; only they see your address.</li>' +
        '<li>They send photo proof. You tick the checklist: that\'s the quality score.</li><li>You pay cash or e-Transfer. Bonus if the score reaches your bar.</li></ol></div>'; return; }
      var t = task(), preview = { id: 'preview', title: P.title || t.name, task: P.task, area: P.area || 'Your area', dist: null, when_date: P.when_date, when_note: P.when_note,
        pay: P.pay_method, vehicle: t.vehicle, base: P.base, bonus: useBonus ? P.bonus : 0, bar: P.bar, offers: 0, poster: { name: UI.me.short || UI.me.name, record: {} } };
      box.innerHTML = '<div><p class="small" style="font-weight:800;margin:0 0 8px">' + UI.icon('search') + ' How it looks on the board</p><div class="ps-preview">' + SR.card(preview) + '</div></div>' +
        '<div class="ui-card flat"><h4 style="margin-top:0">' + UI.icon('shield') + ' Not allowed</h4><ul class="small muted" style="padding-left:18px;margin:0">' +
        CAT.not_allowed.slice(0, 4).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul><a class="small" href="#rules" data-go="rules">All the rules</a></div>';
    }

    /* ---------------------------------------------------------------- steps */
    function stepTask() {
      var cats = [['season', 'In season', 'sparkle'], ['all', 'All 40', 'grid']].concat(CAT.categories.map(function (c) { return [c.key, c.name, c.icon]; }));
      var q = query.toLowerCase();
      var list = CAT.tasks.filter(function (t) {
        if (q) return (t.name + ' ' + t.blurb + ' ' + CAT.catByKey[t.cat].name).toLowerCase().indexOf(q) >= 0;
        if (catFilter === 'season') return SR.inSeason(t) || t.key === 'other';
        return catFilter === 'all' || t.cat === catFilter;
      });
      return '<div class="ps-head"><h1>What do you need done?</h1><p>Pick the closest task. Each comes with a suggested price and a quality checklist you can edit.</p></div>' +
        '<input type="search" data-q placeholder="Search tasks: leaves, couch, dog, Tempo…" value="' + esc(query) + '" style="margin-bottom:12px" aria-label="Search tasks">' +
        '<div class="ps-cats">' + cats.map(function (c) { return '<button type="button" class="sr-chip' + (catFilter === c[0] && !query ? ' on' : '') + '" data-catf="' + c[0] + '">' + UI.icon(c[2]) + esc(c[1]) + '</button>'; }).join('') + '</div>' +
        '<div class="ps-tasks">' + (list.length ? list.map(function (t) {
          return '<button type="button" class="ps-task' + (P.task === t.key ? ' on' : '') + '" data-task="' + t.key + '">' + SR.ti(t.key, 'sm') + '<b>' + esc(t.name) + '</b><p>' + esc(t.blurb) + '</p>' +
            '<span class="from">From ' + SR.money(t.prices[0]) + (SR.inSeason(t) ? ' <span class="ui-badge good">In season</span>' : '') + (t.vehicle ? ' <span class="ui-badge">Vehicle</span>' : '') + '</span></button>';
        }).join('') : '<p class="muted">No task matches. Try "Another neighbourly task".</p>') + '</div>';
    }
    function stepDetails() {
      var t = task(), today = new Date(), iso = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      return '<div class="ps-head"><h1>' + esc(t.name) + '</h1><p>Say what needs doing. Clear bounties get better offers.</p></div><div class="ui-stack">' +
        '<label class="ui-field"><span>Title</span><input type="text" name="title" maxlength="90" value="' + esc(P.title) + '" placeholder="e.g. Rake & bag the front yard"></label>' +
        '<label class="ui-field"><span>Details</span><textarea name="details" maxlength="1500" rows="5" placeholder="' + esc(t.blurb + ' Where are the tools? Anything to know (dog, gate code, parking)?') + '">' + esc(P.details) + '</textarea></label>' +
        '<p class="ui-hint" style="margin-top:-8px">' + UI.icon('eyeoff') + ' Phone numbers, emails and links are hidden on the board: you\'ll chat with your helper in the app.</p>' +
        '<div><b class="small">How big is it?</b><div class="ps-sizes" style="margin-top:8px">' + CAT.sizes.map(function (s, i) {
          return '<label class="ps-size"><input type="radio" name="size" value="' + s.key + '"' + (P.size === s.key ? ' checked' : '') + '><span><b>' + s.name + '</b><small>' + s.hint + '</small><i>~' + SR.money(t.prices[i]) + '</i></span></label>';
        }).join('') + '</div></div>' +
        '<div class="ui-grid two"><label class="ui-field"><span>Date <em>(optional)</em></span><input type="date" name="when_date" min="' + iso + '" value="' + esc(P.when_date) + '"></label>' +
        '<label class="ui-field"><span>When works <em>(optional)</em></span><input type="text" name="when_note" maxlength="80" value="' + esc(P.when_note) + '" placeholder="e.g. Saturday morning"></label></div>' +
        '<div><b class="small">Photos <span class="muted">(optional, up to 4: helpers love a "before" picture)</span></b>' +
        (P.photo_keys.length ? '<p class="small">' + UI.plural(P.photo_keys.length, 'photo') + ' added. Add more below or keep these.</p>' : '') + '<div data-up style="margin-top:8px"></div></div></div>';
    }
    function stepWhere() {
      var s = UI.me.spot;
      return '<div class="ps-head"><h1>Where is the job?</h1><p>The board shows the area and a circle, never your address.</p></div><div class="ui-stack">' +
        '<div class="ps-spot"><div class="sr-map" data-map><div class="sr-map-msg">' + (P.lat == null ? 'No spot yet: pick it on the map.' : 'Loading the map…') + '</div></div>' +
        '<div class="ui-stack" style="flex:1 1 220px"><button class="ui-btn primary" type="button" data-pick>' + UI.icon('pin') + (P.lat == null ? 'Pick the spot on the map' : 'Move the pin') + '</button>' +
        (s && P.lat == null ? '<button class="ui-btn" type="button" data-myarea>' + UI.icon('home') + 'Use my area (' + esc(s.label) + ')</button>' : '') +
        (P.area ? '<p style="margin:0"><b>Area shown:</b> ' + esc(P.area) + '</p>' : '') + '</div></div>' +
        '<label class="ui-field"><span>Street address ' + UI.icon('lock') + '</span><input type="text" name="address" maxlength="160" value="' + esc(P.address) + '" placeholder="e.g. 1234 rue Fullum, apt 2"></label>' +
        '<p class="ui-hint" style="margin-top:-8px">Only the helper you pick sees it, once you pick them.</p></div>';
    }
    function stepBounty() {
      var t = task();
      return '<div class="ps-head"><h1>Set the bounty</h1><p>The minimum is ' + SR.money(CAT.min_base) + '. Fair bounties get done first.</p></div><div class="ui-stack">' +
        '<div class="ui-card flat"><b>Bounty</b><p class="small muted" style="margin:2px 0 10px">Paid once you validate the work.</p><div class="ps-money">' +
        '<button class="ui-btn" type="button" data-step-base="-5" aria-label="Minus 5 dollars">−</button><input type="number" name="base" min="' + CAT.min_base + '" max="' + CAT.max_base + '" step="1" value="' + P.base + '" aria-label="Bounty in dollars">' +
        '<button class="ui-btn" type="button" data-step-base="5" aria-label="Plus 5 dollars">+</button></div>' +
        '<div class="ps-pills" style="margin-top:10px">' + CAT.sizes.map(function (s, i) { return '<button type="button" class="sr-chip" data-set-base="' + t.prices[i] + '">' + s.name + ' ~' + SR.money(t.prices[i]) + '</button>'; }).join('') + '</div></div>' +
        '<div class="ui-card flat"><label class="ui-check"><input type="checkbox" data-usebonus' + (useBonus ? ' checked' : '') + '> <span><b>Add a quality bonus</b><br><span class="small muted">Paid on top, only if the checklist score reaches the bar you set. Great helpers go for it.</span></span></label>' +
        '<div data-bonusbox' + (useBonus ? '' : ' hidden') + ' style="margin-top:12px"><div class="ui-grid two"><div><b class="small">Bonus</b><div class="ps-pills" style="margin-top:6px">' +
        [5, 10, 15, 20, 30].map(function (n) { return '<button type="button" class="sr-chip' + (P.bonus === n ? ' on' : '') + '" data-bonus="' + n + '">+' + SR.money(n) + '</button>'; }).join('') + '</div></div>' +
        '<div><b class="small">Quality bar</b><div class="ps-pills" style="margin-top:6px">' + [60, 70, 80, 90, 100].map(function (n) {
          return '<button type="button" class="sr-chip' + (P.bar === n ? ' on' : '') + '" data-bar="' + n + '">' + n + '%</button>';
        }).join('') + '</div></div></div></div></div>' +
        '<div class="ui-card flat"><b>Quality checklist</b><p class="small muted" style="margin:2px 0 10px">You tick these when the job is done. Each is worth the same share of the score. Keep 2 to 8 clear, checkable items.</p>' +
        '<div class="ps-checklist" data-checklist>' + P.checklist.map(function (c, i) {
          return '<div class="row"><span>' + (i + 1) + '</span><input type="text" data-ci="' + i + '" maxlength="90" value="' + esc(c) + '"><button class="ui-btn ghost icon" type="button" data-crm="' + i + '" aria-label="Remove item">' + UI.icon('x') + '</button></div>';
        }).join('') + '</div>' + (P.checklist.length < 8 ? '<button class="ui-btn sm" type="button" data-cadd style="margin-top:10px">' + UI.icon('plus') + 'Add an item</button>' : '') +
        '<div class="ps-explain" data-explain style="margin-top:14px"></div></div>' +
        '<div><b class="small">How will you pay?</b><div class="ps-pay" style="margin-top:8px">' + CAT.pay_methods.map(function (m) {
          return '<label class="ui-choice"><input type="radio" name="pay" value="' + m.key + '"' + (P.pay_method === m.key ? ' checked' : '') + '><span>' + SR.payIcon(m.key) + esc(m.name) + '</span></label>';
        }).join('') + '</div><p class="ui-hint">No money goes through the app and there are no fees. You pay your helper directly once the job is validated; their e-Transfer email shows up then.</p></div></div>';
    }
    function stepReview() {
      var t = task();
      return '<div class="ps-head"><h1>Ready to post?</h1><p>Check it over. You can raise the bounty later, but not lower it.</p></div><div class="ui-stack">' +
        '<div class="ui-card flat"><dl class="ps-sum">' +
        '<dt>Task</dt><dd>' + esc(t.name) + '</dd><dt>Title</dt><dd>' + esc(P.title) + '</dd><dt>Details</dt><dd>' + esc(P.details) + '</dd>' +
        '<dt>When</dt><dd>' + esc(SR.when(P)) + '</dd><dt>Size</dt><dd>' + esc(P.size) + '</dd><dt>Where</dt><dd>' + esc(P.area) + ' · ' + esc(P.address) + ' ' + UI.icon('lock') + '</dd>' +
        '<dt>Bounty</dt><dd><b>' + SR.money(P.base) + '</b>' + (useBonus ? ' + ' + SR.money(P.bonus) + ' bonus at ' + P.bar + '%' : '') + '</dd>' +
        '<dt>Payment</dt><dd>' + esc(CAT.pay_methods.filter(function (m) { return m.key === P.pay_method; })[0].name) + '</dd>' +
        '<dt>Checklist</dt><dd>' + P.checklist.map(esc).join(' · ') + '</dd><dt>Photos</dt><dd>' + P.photo_keys.length + '</dd></dl></div>' +
        '<div class="ui-card flat ps-rules"><b>Before you post</b>' + [
          'It\'s a neighbourly job: no licence needed, no roof, nothing hazardous.',
          'I\'ll pay within 3 days of validating, in cash or by e-Transfer, exactly what the score says.',
          'I won\'t ask anyone to pay, buy, or advance money for me.'
        ].map(function (r, i) { return '<label class="ui-check"><input type="checkbox" data-rule="' + i + '"> ' + esc(r) + '</label>'; }).join('') + '</div>' +
        '<div data-err class="ui-error" hidden></div></div>';
    }

    function explain() {
      var box = view.querySelector('[data-explain]');
      if (!box) return;
      var n = P.checklist.filter(function (c) { return c.trim(); }).length || 1, need = Math.ceil(n * P.bar / 100 - 1e-9);
      box.innerHTML = useBonus ? UI.icon('ruler') + ' With ' + n + ' items, each is worth ' + Math.round(100 / n) + '%. Tick <b>' + need + ' of ' + n + '</b> (' + P.bar + '%) and you pay <b>' +
        SR.money(P.base + P.bonus) + '</b>; below that you pay <b>' + SR.money(P.base) + '</b>.' :
        UI.icon('ruler') + ' With ' + n + ' items, each is worth ' + Math.round(100 / n) + '% of the score. You pay <b>' + SR.money(P.base) + '</b> once you validate.';
      aside();
    }
    function spotMap() {
      if (P.lat == null) return;
      SR.leaflet().then(function (L) {
        var box = view.querySelector('[data-map]');
        if (!alive || !box) return;
        box.innerHTML = '';
        if (map) { try { map.remove(); } catch (e) {} }
        map = L.map(box, { scrollWheelZoom: false, zoomControl: false }).setView([P.lat, P.lng], 15);
        SR.tiles(L, map);
        L.marker([P.lat, P.lng], { icon: SR.pricePin(L, { label: 'Job' }, 'me') }).addTo(map);
      });
    }

    /* ---------------------------------------------------------------- reading + checking each step */
    function collect() {
      var b = view.querySelector('[data-body]');
      if (step === 1) {
        P.title = b.querySelector('[name=title]').value.trim(); P.details = b.querySelector('[name=details]').value.trim();
        P.size = (b.querySelector('[name=size]:checked') || {}).value || 'medium';
        P.when_date = b.querySelector('[name=when_date]').value; P.when_note = b.querySelector('[name=when_note]').value.trim();
        if (up) up.keys().forEach(function (k) { if (P.photo_keys.indexOf(k) < 0) P.photo_keys.push(k); });
      }
      if (step === 2) P.address = b.querySelector('[name=address]').value.trim();
      if (step === 3) {
        P.base = Math.round(+b.querySelector('[name=base]').value || 0);
        P.checklist = Array.prototype.map.call(b.querySelectorAll('[data-ci]'), function (i) { return i.value.trim(); });
        P.pay_method = (b.querySelector('[name=pay]:checked') || {}).value || 'either';
      }
    }
    function check() {
      if (step === 0 && !P.task) return 'Pick a task first.';
      if (step === 1) {
        if (up && up.busy()) return 'Wait for the photos to finish uploading.';
        if (P.title.length < 6) return 'Give it a title (at least 6 characters).';
        if (P.details.length < 15) return 'Describe the job in a sentence or two.';
      }
      if (step === 2) {
        if (P.lat == null) return 'Pick the spot on the map.';
        if (P.address.length < 5) return 'Add the street address (only your helper sees it).';
      }
      if (step === 3) {
        if (P.base < CAT.min_base) return 'The minimum bounty is ' + SR.money(CAT.min_base) + '.';
        if (P.base > CAT.max_base) return 'Bounties go up to ' + SR.money(CAT.max_base) + '.';
        if (useBonus && P.bonus > P.base) return 'The bonus can\'t be more than the bounty.';
        if (P.checklist.filter(Boolean).length < 2) return 'Keep at least 2 checklist items.';
      }
      return null;
    }
    function go(n) {
      collect();
      if (n > step) { var err = check(); if (err) { UI.toast(err, 'error'); return; } }
      step = n; seen = Math.max(seen, n); frame();
    }

    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-step]')) && !t.disabled) { go(+t.getAttribute('data-step')); return; }
      if (e.target.closest('[data-next]')) { go(step + 1); return; }
      if (e.target.closest('[data-prev]')) { go(step - 1); return; }
      if ((t = e.target.closest('[data-task]'))) { chooseTask(t.getAttribute('data-task')); seen = Math.max(seen, 1); step = 1; frame(); return; }
      if ((t = e.target.closest('[data-catf]'))) { catFilter = t.getAttribute('data-catf'); query = ''; frame(); return; }
      if (e.target.closest('[data-pick]')) {
        collect();
        SR.pickSpot({ title: 'Where is the job?', ok: 'Use this spot', pinLabel: 'Job', labelTitle: 'Area shown on the board', lat: P.lat, lng: P.lng, label: P.area,
          text: 'Put the pin on the house. The board only shows the area name and a circle about 500 m wide.' }).then(function (p) {
          if (!p) return;
          P.lat = p.lat; P.lng = p.lng; P.area = p.label;
          if (p.street && !P.address) P.address = p.street;
          frame();
        });
        return;
      }
      if (e.target.closest('[data-myarea]')) { var s = UI.me.spot; P.lat = s.lat; P.lng = s.lng; P.area = s.label; frame(); return; }
      if ((t = e.target.closest('[data-step-base]'))) { collect(); P.base = Math.max(CAT.min_base, Math.min(CAT.max_base, P.base + +t.getAttribute('data-step-base'))); view.querySelector('[name=base]').value = P.base; explain(); return; }
      if ((t = e.target.closest('[data-set-base]'))) { P.base = +t.getAttribute('data-set-base'); view.querySelector('[name=base]').value = P.base; explain(); return; }
      if ((t = e.target.closest('[data-bonus]'))) { P.bonus = +t.getAttribute('data-bonus'); view.querySelectorAll('[data-bonus]').forEach(function (x) { x.classList.toggle('on', x === t); }); explain(); return; }
      if ((t = e.target.closest('[data-bar]'))) { P.bar = +t.getAttribute('data-bar'); view.querySelectorAll('[data-bar]').forEach(function (x) { x.classList.toggle('on', x === t); }); explain(); return; }
      if ((t = e.target.closest('[data-crm]'))) { collect(); P.checklist.splice(+t.getAttribute('data-crm'), 1); frame(); return; }
      if (e.target.closest('[data-cadd]')) { collect(); P.checklist.push(''); frame(); var ins = view.querySelectorAll('[data-ci]'); ins[ins.length - 1].focus(); return; }
      if ((t = e.target.closest('[data-post]'))) {
        var boxes = view.querySelectorAll('[data-rule]'), errBox = view.querySelector('[data-err]');
        if (Array.prototype.some.call(boxes, function (x) { return !x.checked; })) { errBox.textContent = 'Tick the three promises first.'; errBox.hidden = false; return; }
        var data = Object.assign({}, P, { bonus: useBonus ? P.bonus : 0, checklist: P.checklist.filter(Boolean) });
        UI.busy(t, UI.api('post_bounty', data)).then(function (r) {
          if (r.status === 'review') {
            UI.modal('<h2>' + UI.icon('shield') + ' Almost there</h2><p>Your bounty goes to a moderator first, because: <b>' + esc(r.flags.join('; ')) + '</b>.</p><p class="muted">Most checks take a few hours. You\'ll see it in My jobs.</p>' +
              '<div class="ui-row end"><button class="ui-btn primary" data-close>OK</button></div>', { onclose: function () { UI.go('bounty', r.id); } });
          } else {
            SR.confetti(); UI.toast(r.hidden_contact ? 'Posted! (We hid contact details: chat in the app.)' : 'Your bounty is on the board!', 'ok'); UI.go('bounty', r.id);
          }
        }, function (err) { errBox.textContent = err.message; errBox.hidden = false; });
      }
    });
    view.addEventListener('input', function (e) {
      if (e.target.matches('[data-q]')) {
        query = e.target.value; var pos = e.target.selectionStart; frame();
        var q = view.querySelector('[data-q]'); q.focus(); try { q.setSelectionRange(pos, pos); } catch (er) {}
      }
      if (e.target.matches('[data-ci]') || e.target.name === 'base') { collect(); explain(); }
    });
    view.addEventListener('change', function (e) {
      if (e.target.matches('[data-usebonus]')) { useBonus = e.target.checked; view.querySelector('[data-bonusbox]').hidden = !useBonus; explain(); }
      if (e.target.name === 'size' && P.task) { var i = { small: 0, medium: 1, large: 2 }[e.target.value]; P.size = e.target.value; P.base = task().prices[i]; }
      if (e.target.name === 'pay') { P.pay_method = e.target.value; aside(); }
    });

    var ready = Promise.all([SR.catalog(), UI.apiQuiet('get_jobs')]).then(function (r) {
      CAT = r[0]; limit = r[1].limits.post;
      if (ctx.args[0] && CAT.byKey[ctx.args[0]]) { chooseTask(ctx.args[0]); step = 1; seen = 1; }
      frame();
    });
    return { ready: ready, destroy: function () { alive = false; if (map) { try { map.remove(); } catch (e) {} } } };
  });
})();

/* ===== profile.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('profile', { title: 'Your profile', auth: 'user' }, function (view, ctx) {
    var me = ctx.me, CAT = null;
    function draw() {
      me = UI.me;
      view.innerHTML = '<div class="ui-wrap ui-narrow" style="max-width:900px"><div class="pf-head"><span class="ui-avatar">' + esc(UI.initials(me.name)) + '</span>' +
        '<div class="grow"><h1>' + esc(me.name) + '</h1><div class="muted">' + esc(me.email) + (me.joined ? ' · member since ' + esc(UI.fmtDate(me.joined, { month: 'long', year: 'numeric' })) : '') + '</div>' +
        '<div class="small muted">Neighbours see you as <b>' + esc(me.short) + '</b>.' + (me.strikes ? ' <span class="ui-badge warn">' + UI.plural(me.strikes, 'strike') + '</span>' : '') + '</div></div>' +
        '<a class="ui-btn" href="#neighbour/' + esc(me.id) + '" data-go="neighbour/' + esc(me.id) + '">' + UI.icon('star') + 'See my public page</a></div>' +
        '<div class="pf-grid">' +
        '<form class="ui-card ui-stack" data-helper style="grid-column:1/-1"><h3>Helper profile</h3><p class="muted small" style="margin-top:-6px">What posters see when you send an offer.</p>' +
          '<label class="ui-check"><input type="checkbox" name="helper_on"' + (me.helper_on ? ' checked' : '') + '> I\'m open to jobs (show me as a helper)</label>' +
          '<label class="ui-field"><span>About you</span><textarea name="bio" maxlength="400" placeholder="e.g. Student, early riser, I own a good shovel and a car.">' + esc(me.bio) + '</textarea></label>' +
          '<div><b class="small">What you bring</b><div class="pf-skills" style="margin-top:8px">' + CAT.skills.map(function (s) {
            return '<label><input type="checkbox" name="skill" value="' + esc(s) + '"' + (me.skills.indexOf(s) >= 0 ? ' checked' : '') + '><span>' + esc(s) + '</span></label>';
          }).join('') + '</div></div>' +
          '<label class="ui-field"><span>Your Interac e-Transfer email <em>(optional)</em></span><input type="email" name="payout_email" maxlength="200" value="' + esc(me.payout_email) + '" placeholder="the email your bank uses for e-Transfers"></label>' +
          '<p class="ui-hint" style="margin-top:-8px">' + UI.icon('eyeoff') + ' Never shown on your profile. A poster sees it only after validating a job you did for them.</p>' +
          '<div><button class="ui-btn primary" type="submit">Save helper profile</button></div></form>' +
        '<div class="ui-card ui-stack"><h3>Your area</h3><div class="pf-area"><div>' + (me.spot ? '<b>' + esc(me.spot.label) + '</b><div class="small muted">Bounties are sorted by distance from here.</div>' :
          '<b>Not set</b><div class="small muted">Set it to see bounties by distance.</div>') + '</div><button class="ui-btn" type="button" data-area>' + UI.icon('pin') + (me.spot ? 'Change' : 'Set my area') + '</button></div>' +
          '<p class="ui-hint">' + UI.icon('lock') + ' Others only see the area name.</p></div>' +
        '<form class="ui-card ui-stack" data-name><h3>Your name</h3><label class="ui-field"><span>Your full name (others see "' + esc(me.short) + '")</span>' +
          '<input type="text" name="name" value="' + esc(me.name) + '" maxlength="60" required></label><div><button class="ui-btn primary" type="submit">Save</button></div></form>' +
        '<div class="ui-card ui-stack"><h3>Appearance</h3><p class="muted small">Follow your device, or pick one.</p><div data-theme-box></div></div>' +
        '<div class="ui-card ui-stack"><h3>Password</h3><p class="muted small">We\'ll email you a link to choose a new one.</p>' +
          '<div><button class="ui-btn" data-reset>' + UI.icon('mail') + 'Email me a reset link</button></div></div></div>' +
        '<div class="ui-card" style="margin-top:16px"><div class="pf-links">' +
        (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
        '<a href="#ledger" data-go="ledger">' + UI.icon('wallet') + 'Your ledger</a>' +
        '<a href="#rules" data-go="rules">' + UI.icon('flag') + 'Rules &amp; safety</a>' +
        '<button data-feedback>' + UI.icon('chat') + 'Submit feedback</button>' +
        '<button data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms, and your data</button>' +
        '<button data-signout-here>' + UI.icon('logout') + 'Sign out</button></div></div></div>';
      themeBox();
    }
    function themeBox() {
      var t = UI.theme(), box = view.querySelector('[data-theme-box]');
      if (box) box.innerHTML = '<div class="ui-seg">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
        return '<button type="button" data-theme-pick="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
      }).join('') + '</div>';
    }
    view.addEventListener('click', function (e) {
      var t = e.target.closest('[data-theme-pick]');
      if (t) { UI.setTheme(t.getAttribute('data-theme-pick')); themeBox(); UI.renderChrome(); return; }
      if (e.target.closest('[data-reset]')) {
        UI.busy(e.target.closest('[data-reset]'), UI.auth('reset', { email: me.email })).then(function (r) { UI.toast(r.message, 'ok'); });
      }
      if (e.target.closest('[data-area]')) SR.editArea().then(function (m) { if (m) draw(); });
      if (e.target.closest('[data-signout-here]')) UI.auth('logout');
    });
    view.addEventListener('submit', function (e) {
      var f = e.target, v = UI.formData(f);
      e.preventDefault();
      if (f.matches('[data-name]')) {
        UI.busy(f.querySelector('[type=submit]'), UI.api('update_profile', v.name)).then(function (r) { UI.setMe(r.me); UI.toast('Saved', 'ok'); draw(); });
      }
      if (f.matches('[data-helper]')) {
        var skills = Array.prototype.slice.call(f.querySelectorAll('[name=skill]:checked')).map(function (x) { return x.value; });
        UI.busy(f.querySelector('[type=submit]'), UI.api('update_helper_profile', v.bio, skills, v.payout_email, !!v.helper_on)).then(function (r) { UI.setMe(r.me); UI.toast('Helper profile saved', 'ok'); draw(); });
      }
    });
    return SR.catalog().then(function (c) { CAT = c; draw(); });
  });
})();

/* ===== rules.html ===== */
(function () {
  var esc = UI.esc;
  var SCAMS = [
    ['The overpayment trick', 'Someone "accidentally" sends more than the bounty and asks you to send the difference back. The first payment bounces or gets reversed; yours doesn\'t. Never send money back.'],
    ['Fake e-Transfer emails', 'A real Interac e-Transfer shows up in your bank app. Don\'t click "deposit" links in emails or texts you weren\'t expecting, and never type your bank password on a link.'],
    ['Pay to get the job', 'No real poster asks for a deposit, a fee, a uniform or a "registration". The app never asks you for money either.'],
    ['Gift cards, crypto, cheques', 'Buying gift cards and sending the codes, crypto, or cashing a cheque for someone are classic scams. They\'re not allowed and the scanner flags them.'],
    ['Carrying packages', 'Picking up or delivering sealed packages for a stranger can make you part of a fraud or worse. Not allowed.'],
    ['Moving off the app too early', 'Scammers want your number before you\'re matched. Contact details are hidden until the poster picks you, so reports and the paper trail keep working.']
  ];
  var SAFE = ['Meet outside, in daylight, when you can. Tell someone where you\'re going.', 'You never have to go inside a home. If it feels wrong, leave and report it.',
              'Under 18? Get a parent\'s OK first and let them see the bounty. (The app is for 16 and up.)', 'Use the poster\'s tools when the bounty says so, and take photos before and after.'];

  UI.page('rules', { title: 'Rules & safety' }, function (view) {
    function draw(C) {
      var byCat = {};
      C.tasks.forEach(function (t) { (byCat[t.cat] = byCat[t.cat] || []).push(t); });
      view.innerHTML = '<div class="ui-wrap"><section class="rl-hero"><div><span class="eyebrow">Rules &amp; safety</span><h1>Fair pay, real neighbours, no scams.</h1>' +
        '<p>Service Request is a bounty board for neighbourly jobs. Here\'s how paying works, how quality is judged, and how the app protects both sides.</p></div>' +
        '<div class="sr-tag big"><b>$' + C.min_base + '+</b><i>every bounty</i></div></section>' +
        '<nav class="rl-toc">' + [['pay', 'Paying', 'cash'], ['quality', 'Quality & bonus', 'ruler'], ['scams', 'Scams', 'flag'], ['allowed', 'What\'s allowed', 'check'],
          ['privacy', 'Privacy', 'eyeoff'], ['disputes', 'Disputes', 'shield'], ['tasks', 'All 40 tasks', 'grid']].map(function (s) {
          return '<a class="sr-chip" href="#rules/' + s[0] + '" data-jump="' + s[0] + '">' + UI.icon(s[2]) + esc(s[1]) + '</a>';
        }).join('') + '</nav>' +
        '<div class="rl-grid">' +
        '<section class="ui-card rl-sec" id="rl-pay"><h2>' + UI.icon('cash') + 'Paying</h2><ul class="rl-no rl-yes">' + [
          'You pay the helper directly: cash in hand, or an Interac e-Transfer from your bank. No money goes through the app and there are no fees.',
          'The amount is set before the job: the bounty (at least $' + C.min_base + '), plus the quality bonus if the checklist score reaches the bar.',
          'You pay after you validate the work, within 3 days. Until then, you can\'t post or hire again.',
          'The helper\'s e-Transfer email is shown to you only after you validate their work, and only on that bounty.',
          'Both sides confirm: you mark it paid (with the bank reference for e-Transfers), the helper confirms they got it.'
        ].map(function (x) { return '<li>' + UI.icon('check') + '<span>' + esc(x) + '</span></li>'; }).join('') + '</ul></section>' +
        '<section class="ui-card rl-sec" id="rl-quality"><h2>' + UI.icon('ruler') + 'Quality &amp; bonus</h2><p>Every bounty has a checklist of 2 to 8 things anyone can check: "bags at the curb", "plow ridge cleared". ' +
          'When the job is done, the helper sends photos and ticks what they did. The poster then ticks what they see.</p>' +
          '<p><b>The score is the share of items ticked.</b> 4 of 5 is 80%. If the poster set a bonus, say $10 at 80%, the helper gets it from 80% up.</p>' +
          '<ul class="rl-no rl-yes">' + ['Unticking an item needs a written reason the helper can read.', 'If the poster doesn\'t check within 48 hours, the helper\'s own checklist counts.',
            'Every poster\'s profile shows how often they pay the bonus, so tough graders are easy to spot.'].map(function (x) { return '<li>' + UI.icon('check') + '<span>' + esc(x) + '</span></li>'; }).join('') + '</ul></section>' +
        '</div>' +
        '<section class="ui-card rl-sec" id="rl-scams" style="margin-top:16px"><h2>' + UI.icon('flag') + 'Six scams to know</h2><div class="rl-scams">' + SCAMS.map(function (s, i) {
          return '<div class="rl-scam"><span class="n">' + (i + 1) + '</span><div><b>' + esc(s[0]) + '</b><p>' + esc(s[1]) + '</p></div></div>';
        }).join('') + '</div></section>' +
        '<div class="rl-grid" style="margin-top:16px">' +
        '<section class="ui-card rl-sec" id="rl-allowed"><h2>' + UI.icon('check') + 'What\'s allowed</h2><p>Neighbourly jobs that need no degree and no licence: yard, snow, junk, lifting, outdoor cleaning, errands, pets and plants, seasonal help. ' +
          'Bounties from $' + C.min_base + ' to $' + C.max_base + '.</p><h4>Never allowed</h4><ul class="rl-no">' +
          C.not_allowed.map(function (x) { return '<li>' + UI.icon('x') + '<span>' + esc(x) + '</span></li>'; }).join('') + '</ul>' +
          '<p class="small muted" style="margin:12px 0 0">A scanner reads every new bounty. Anything that looks risky waits for a moderator before it reaches the board.</p></section>' +
        '<section class="ui-card rl-sec" id="rl-safe"><h2>' + UI.icon('hand') + 'Staying safe</h2><ul class="rl-no rl-yes">' + SAFE.map(function (x) { return '<li>' + UI.icon('check') + '<span>' + esc(x) + '</span></li>'; }).join('') + '</ul></section>' +
        '<section class="ui-card rl-sec" id="rl-privacy"><h2>' + UI.icon('eyeoff') + 'Privacy</h2><ul class="rl-no rl-yes">' + [
          'The board shows an area name and a circle about 500 m wide, never your address.',
          'Your street address goes only to the helper you pick, once you pick them.',
          'Profiles show a first name and an initial. Emails are never shown to anyone.',
          'Phone numbers, emails and links in bounties and offers are hidden automatically.'
        ].map(function (x) { return '<li>' + UI.icon('check') + '<span>' + esc(x) + '</span></li>'; }).join('') + '</ul></section>' +
        '<section class="ui-card rl-sec" id="rl-disputes"><h2>' + UI.icon('shield') + 'Disputes &amp; strikes</h2><ul class="rl-no rl-yes">' + [
          'Can\'t sort it out in the chat? Either side can ask a moderator. The job is frozen until they decide what is owed.',
          'An upheld report or a lost dispute is a strike. Three strikes pause the account.',
          'New accounts can have 2 live bounties and 2 jobs on the go until they finish one.',
          'Three reports from different neighbours take a bounty off the board until it\'s checked.',
          'Reviews are blind until both sides write theirs, and each neighbour counts once in a rating.'
        ].map(function (x) { return '<li>' + UI.icon('check') + '<span>' + esc(x) + '</span></li>'; }).join('') + '</ul></section></div>' +
        '<section class="ui-card rl-sec" id="rl-tasks" style="margin-top:16px"><h2>' + UI.icon('grid') + 'All 40 tasks, with suggested bounties</h2><p class="muted">Suggested prices for a small, medium and large job. Posters can always offer more.</p>' +
        '<table class="rl-tasks"><thead><tr><th>Task</th><th class="blurb">What it is</th><th>Small · Medium · Large</th></tr></thead><tbody>' +
        C.categories.map(function (c) {
          return '<tr class="cat"><td colspan="3">' + UI.icon(c.icon) + ' ' + esc(c.name) + '</td></tr>' + (byCat[c.key] || []).map(function (t) {
            return '<tr><td><a href="#post/' + esc(t.key) + '" data-go="post/' + esc(t.key) + '">' + esc(t.name) + '</a>' + (t.vehicle ? ' <span class="ui-badge">Vehicle</span>' : '') + '</td>' +
              '<td class="blurb muted">' + esc(t.blurb) + '</td><td class="p">' + t.prices.map(SR.money).join(' · ') + '</td></tr>';
          }).join('');
        }).join('') + '</tbody></table></section></div>';
    }
    view.addEventListener('click', function (e) {
      var j = e.target.closest('[data-jump]');
      if (!j) return;
      e.preventDefault();
      var el = view.querySelector('#rl-' + j.getAttribute('data-jump'));
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    });
    return SR.catalog().then(draw);
  });
})();
