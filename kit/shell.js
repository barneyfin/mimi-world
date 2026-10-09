/* MeeMee World kit: the shell around every game.
   Screens, full screen and landscape on the first tap, "turn me sideways", the buttons the player taps,
   and the grown-ups lock (press and hold for 3 seconds). */
(function () {
  'use strict';
  const MW = window.MW;
  const S = MW.shell = { screen: null, paused: false };
  MW.device = { full: 'Not tried yet', fullOk: null, orient: '', loadMs: null };

  // ---------------------------------------------------------------- screens
  S.show = function (id) {
    Array.prototype.forEach.call(document.querySelectorAll('.mw-screen'), function (s) {
      s.classList.toggle('is-shown', s.id === id);
    });
    S.screen = id;
    MW.log('screen', id);
    S.reloadIfIdle();
  };
  S.reloadIfIdle = function () {
    // a new version takes over only on a screen where nothing is lost: the start screen or the home map
    if (S.updateReady && (S.screen === 'screen-start' || S.screen === 'screen-map') && !(MW.grownups && MW.grownups.open)) location.reload();
  };

  // ---------------------------------------------------------------- full screen and landscape (needs a tap)
  S.fullscreen = function () {
    const el = document.documentElement;
    const isFull = document.fullscreenElement || document.webkitFullscreenElement;
    const mm = window.matchMedia;
    const app = mm && (mm('(display-mode: fullscreen)').matches || mm('(display-mode: standalone)').matches);
    if (isFull || app) { MW.device.full = app ? 'Opened as an app (already full screen)' : 'Already full screen'; MW.device.fullOk = true; lock(); return; }
    const req = el.requestFullscreen || el.webkitRequestFullscreen;
    if (!req) { MW.device.full = 'Not available in this browser'; MW.device.fullOk = false; return; }
    try {
      const p = req.call(el, { navigationUI: 'hide' });
      const ok = function () { MW.device.full = 'Worked'; MW.device.fullOk = true; lock(); };
      if (p && p.then) p.then(ok).catch(function (err) { MW.device.full = 'Refused (' + err.name + ')'; MW.device.fullOk = false; });
      else setTimeout(ok, 300);
    } catch (err) { MW.device.full = 'Failed: ' + err.message; MW.device.fullOk = false; }
  };
  function lock() {
    if (screen.orientation && screen.orientation.lock) {
      screen.orientation.lock('landscape').then(function () { MW.device.orient = 'locked to landscape'; })
        .catch(function (err) { MW.device.orient = 'could not lock (' + err.name + ')'; });
    } else { MW.device.orient = 'lock not available'; }
  }

  // ---------------------------------------------------------------- buttons the player taps (pictures, never words)
  // Positions from the design system: Home top-left, Music and Hear-again top-right.
  S.buttons = function (parent, which, handlers) {
    const out = {};
    if (which.indexOf('home') >= 0) {
      out.home = button(parent, 'mw-btn mw-btn--nav', 24, 20, 'Home', 'icon-home', 44);
      MW.onTap(out.home, function () { if (handlers.home) handlers.home(); });
    }
    if (which.indexOf('music') >= 0) {
      out.music = button(parent, 'mw-btn mw-btn--nav mw-music', which.indexOf('hear') >= 0 ? 1052 : 1172, 26, 'Music', null, 40);
      MW.onTap(out.music, function () { MW.audio.music.setOn(!MW.audio.music.isOn()); });
      paintMusic(out.music);
    }
    if (which.indexOf('hear') >= 0) {
      out.hear = button(parent, 'mw-btn mw-btn--main', 1160, 20, 'Hear it again', 'icon-hear', 54);
      MW.onTap(out.hear, function () { if (handlers.hear) handlers.hear(); });
    }
    return out;
  };
  function button(parent, cls, x, y, label, icon, size) {
    const b = MW.make('button', cls + ' mw-abs', { type: 'button', 'aria-label': label });
    b.style.left = x + 'px'; b.style.top = y + 'px';
    if (icon) { const i = MW.art(icon); i.setAttribute('width', size); i.setAttribute('height', size); b.appendChild(i); }
    b.setAttribute('data-icon-size', size);
    parent.appendChild(b);
    return b;
  }
  function paintMusic(b) {
    const on = MW.audio.music.isOn();
    const size = +b.getAttribute('data-icon-size');
    b.innerHTML = '';
    const i = MW.art(on ? 'icon-music' : 'icon-music-off');
    i.setAttribute('width', size); i.setAttribute('height', size);
    b.appendChild(i);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.setAttribute('aria-label', on ? 'Music on' : 'Music off');
  }
  document.addEventListener('mw-music', function () {
    Array.prototype.forEach.call(document.querySelectorAll('.mw-music'), paintMusic);
  });

  // ---------------------------------------------------------------- the grown-ups lock
  // A quick tap does nothing and shows nothing. Holding fills a mint ring over 3 s, then opens the grown-ups area.
  S.gate = function (parent, onOpen) {
    const HOLD = 3000;
    const b = MW.make('button', 'mw-btn mw-btn--grownups mw-gate mw-abs', { type: 'button', 'aria-label': 'Grown-ups (press and hold)' });
    b.style.left = '24px'; b.style.top = '732px';
    const ring = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ring, 'svg');
    svg.setAttribute('class', 'mw-gate-ring'); svg.setAttribute('viewBox', '0 0 64 64'); svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML = '<circle class="s-night-button" fill="none" stroke-width="5" cx="32" cy="32" r="29"/>'
      + '<circle class="mw-gate-fill s-mint" fill="none" stroke-width="5" cx="32" cy="32" r="29" stroke-dasharray="182.2" stroke-dashoffset="182.2" transform="rotate(-90 32 32)"/>';
    b.appendChild(svg);
    const icon = MW.art('icon-lock'); icon.setAttribute('width', 24); icon.setAttribute('height', 24);
    b.appendChild(icon);
    parent.appendChild(b);
    // One finger only, held still on the lock: a palm, two fingers or a thumb sliding off don't count.
    let timer = 0, hold = null;
    const fill = svg.querySelector('.mw-gate-fill');
    function start(e) {
      e.preventDefault();
      if (hold) { stop(); return; }                      // a second finger cancels
      hold = { id: e.pointerId, x: e.clientX, y: e.clientY };
      b.classList.add('is-holding');
      fill.style.transition = 'stroke-dashoffset ' + HOLD + 'ms linear';
      fill.style.strokeDashoffset = '0';
      clearTimeout(timer);
      timer = setTimeout(function () { stop(); onOpen(); }, HOLD);
    }
    function stop() {
      hold = null;
      clearTimeout(timer);
      b.classList.remove('is-holding');
      fill.style.transition = 'none';
      fill.style.strokeDashoffset = '182.2';
    }
    function moved(e) {
      if (!hold || e.pointerId !== hold.id) return;
      if (Math.hypot(e.clientX - hold.x, e.clientY - hold.y) > 25) stop();
    }
    b.addEventListener('pointerdown', start);
    b.addEventListener('pointermove', moved);
    b.addEventListener('pointerup', stop);
    b.addEventListener('pointercancel', stop);
    b.addEventListener('pointerleave', stop);
    b.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    return b;
  };

  // ---------------------------------------------------------------- turn me sideways
  S.watchSideways = function (onPortrait, onLandscape) {
    const mq = window.matchMedia('(orientation: portrait)');
    let was = mq.matches;
    const check = function () {
      if (mq.matches === was) return;
      was = mq.matches;
      if (was) onPortrait(); else onLandscape();
    };
    if (mq.addEventListener) mq.addEventListener('change', check); else mq.addListener(check);
    return function () { return mq.matches; };
  };

  // No long-press menus, no double-tap zoom.
  document.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  document.addEventListener('dblclick', function (e) { e.preventDefault(); });

  // ---------------------------------------------------------------- offline copy
  S.offline = { text: 'Checking…', ok: null };
  S.registerOffline = function () {
    if (!('serviceWorker' in navigator) || !window.isSecureContext) {
      S.offline = { text: window.isSecureContext ? 'Not available in this browser' : 'Needs the https address', ok: false };
      return;
    }
    const controlled = !!navigator.serviceWorker.controller;
    // A new version has been saved: switch to it the next time the start screen shows, never mid-round.
    navigator.serviceWorker.addEventListener('message', function (e) {
      if (e.data && e.data.type === 'mw-updated') { S.updateReady = true; MW.log('update', e.data.version); S.reloadIfIdle(); }
    });
    navigator.serviceWorker.register('sw.js').then(function (reg) {
      // Ask for a newer version a few seconds after opening (and hourly while open), so updates arrive on the first visit.
      const check = function () { if (navigator.onLine) reg.update().catch(function () {}); };
      setTimeout(check, 8000);
      setInterval(check, 3600 * 1000);
      return navigator.serviceWorker.ready;
    }).then(function () {
      S.offline = controlled ? { text: 'Opened from the saved copy', ok: true } : { text: 'Saved for offline; works from the next visit', ok: true };
    }).catch(function (err) { S.offline = { text: 'Could not save (' + err.name + ')', ok: false }; });
  };
})();
