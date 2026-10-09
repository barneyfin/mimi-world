/* MeeMee World kit: the grown-ups area.
   Opened by holding the lock for 3 seconds. Written for adults: British English, sentence case, no exclamation marks.
   The kit provides "Checks" (this tablet, every voice clip, music, effects); a game adds its own sections. */
(function () {
  'use strict';
  const MW = window.MW;
  const G = MW.grownups = { open: false, sections: [] };
  let root, body, tabs, current = null, onClose = null;

  G.init = function (stageEl, opts) {
    onClose = opts.onClose;
    G.sections = (opts.sections || []).concat([checksSection(), soundSection()]);
    root = MW.make('div', 'mw-grownups', { role: 'dialog', 'aria-label': 'Grown-ups', id: 'grownups' });
    const panel = MW.make('div', 'mw-panel gu-panel');
    const head = MW.make('div', 'gu-head');
    head.appendChild(MW.make('h2', 'title gu-title', null, MW.esc(opts.title || 'Grown-ups')));
    tabs = MW.make('div', 'gu-tabs', { role: 'tablist' });
    G.sections.forEach(function (s) {
      const t = MW.make('button', 'gu-tab button-label', { type: 'button', role: 'tab', 'data-tab': s.id }, MW.esc(s.title));
      MW.onTap(t, function () { G.show(s.id); });
      tabs.appendChild(t);
    });
    head.appendChild(tabs);
    const close = MW.make('button', 'gu-btn gu-close button-label', { type: 'button' }, 'Close');
    MW.onTap(close, G.close);
    head.appendChild(close);
    panel.appendChild(head);
    body = MW.make('div', 'gu-body body');
    panel.appendChild(body);
    root.appendChild(panel);
    stageEl.appendChild(root);
  };
  G.show = function (id) {
    current = id;
    Array.prototype.forEach.call(tabs.children, function (t) {
      t.classList.toggle('is-on', t.getAttribute('data-tab') === id);
      t.setAttribute('aria-selected', t.getAttribute('data-tab') === id ? 'true' : 'false');
    });
    const s = G.sections.filter(function (x) { return x.id === id; })[0];
    body.innerHTML = '';
    body.scrollTop = 0;
    s.render(body);
  };
  G.openPanel = function () {
    G.open = true;
    root.classList.add('is-open');
    G.show(current || G.sections[0].id);
    MW.log('grownups', 'open');
  };
  G.close = function () {
    G.open = false;
    root.classList.remove('is-open');
    MW.audio.hush();
    MW.log('grownups', 'close');
    if (onClose) onClose();
  };

  // ---------------------------------------------------------------- small builders for sections
  G.h3 = function (el, text) { el.appendChild(MW.make('h3', 'gu-h3', null, MW.esc(text))); };
  G.p = function (el, text, cls) { el.appendChild(MW.make('p', 'gu-p ' + (cls || ''), null, text)); };
  G.btn = function (el, label, fn, cls) {
    const b = MW.make('button', 'gu-btn button-label ' + (cls || ''), { type: 'button' }, MW.esc(label));
    MW.onTap(b, function () { fn(b); });
    el.appendChild(b);
    return b;
  };
  G.row = function (el) { const r = MW.make('div', 'gu-row'); el.appendChild(r); return r; };
  G.table = function (el, rows) {
    const t = MW.make('table', 'gu-table label');
    t.innerHTML = rows.map(function (r) {
      const cls = r[2] === true ? 'ok' : r[2] === false ? 'warn' : '';
      return '<tr><td>' + MW.esc(r[0]) + '</td><td class="' + cls + '">' + MW.esc(r[1]) + '</td></tr>';
    }).join('');
    el.appendChild(t);
    return t;
  };

  // ---------------------------------------------------------------- Checks: this tablet
  function browserName() {
    const ua = navigator.userAgent; let m;
    if ((m = ua.match(/Silk\/([\d.]+)/))) return 'Silk ' + m[1];
    if ((m = ua.match(/(?:Chrome|CriOS)\/([\d.]+)/))) return 'Chrome ' + m[1];
    if ((m = ua.match(/Firefox\/([\d.]+)/))) return 'Firefox ' + m[1];
    if ((m = ua.match(/Version\/([\d.]+).*Safari/))) return 'Safari ' + m[1];
    return 'Unknown';
  }
  // Read once, as the page opens: after the first tap the page is full screen, which looks the same.
  const openedAs = (function () {
    const mm = window.matchMedia;
    if (!mm) return 'Unknown';
    if (mm('(display-mode: fullscreen)').matches) return 'Opened from the home screen (full screen)';
    if (mm('(display-mode: standalone)').matches) return 'Opened from the home screen';
    return 'Opened in the browser (bookmark or address)';
  })();
  function installed() { return openedAs; }
  G.deviceRows = function () {
    const dpr = window.devicePixelRatio || 1, sc = MW.stage.scale;
    const d = MW.dragStats && MW.dragStats.last;
    const a = MW.audio.status();
    const andr = (navigator.userAgent.match(/Android\s([\d.]+)/) || [])[1];
    return [
      ['Page version', MW.VERSION],
      ['Browser', browserName() + (andr ? ' · Android ' + andr : '')],
      ['Screen', screen.width + '×' + screen.height + ' at ' + (Math.round(dpr * 100) / 100) + 'x · page ' + innerWidth + '×' + innerHeight],
      ['MeeMee size', Math.round(80 * sc * dpr) + ' screen pixels wide (scale ' + sc.toFixed(2) + ')'],
      ['Touch', (navigator.maxTouchPoints || 0) + ((navigator.maxTouchPoints || 0) === 1 ? ' touch point' : ' touch points') + ' · last input ' + (MW.lastInput || '—')],
      ['Drag smoothness', d ? d.fps + ' frames a second; slowest frame ' + d.worst + ' ms; ' + d.slow + ' slow of ' + d.n : 'Drag a MeeMee first',
        d ? (d.fps >= 50 && d.slow <= Math.max(2, d.n * 0.05)) : null],
      ['Opened in', MW.device.loadMs === null ? '—' : (MW.device.loadMs < 100 ? 'under 0.1 s' : (MW.device.loadMs / 1000).toFixed(1) + ' s'), MW.device.loadMs === null ? null : MW.device.loadMs <= 3000],
      ['Sound', a.state === 'running' ? 'On (' + a.rate + ' Hz)' : a.state, a.state === 'running'],
      ['Sound files', a.decoded + ' of ' + a.total + ' ready' + (a.failed.length ? '; failed: ' + a.failed.join(', ') : ''), a.decoded === a.total && !a.failed.length],
      ['Full screen', MW.device.full + (MW.device.orient ? ' · ' + MW.device.orient : ''), MW.device.fullOk],
      ['Home screen', installed()],
      ['Offline copy', MW.shell.offline.text + (navigator.onLine ? ' · online now' : ' · offline now'), MW.shell.offline.ok],
      ['Saving progress', MW.store.check() ? 'Works' : 'Blocked', MW.store.ok],
      ['Reduce motion', MW.reduceMotion ? 'On' : 'Off']
    ];
  };
  function checksSection() {
    return {
      id: 'checks', title: 'Checks',
      render: function (el) {
        G.p(el, 'Photograph this table on each tablet and send it to Claude.', 'gu-lead');
        const t = G.table(el, G.deviceRows());
        const again = G.btn(el, 'Refresh', function () { const n = G.table(MW.make('div'), G.deviceRows()); t.innerHTML = n.innerHTML; });
        again.classList.add('gu-small');
      }
    };
  }

  // ---------------------------------------------------------------- Checks: voice, music and effects
  const SAMPLES = [
    ['Three and four make seven', [['num-mid-3', 'and', 'num-mid-4', 'make', 'num-end-7']]],
    ['Missing part question (7, given 3)', [['q-lets-make', 'num-end-7'], ['q-weve-got', 'num-end-3'], ['q-how-many-more']]],
    ['Missing whole question (2 and 5)', [['q-weve-got', 'num-mid-2', 'and', 'num-end-5'], ['q-how-many-altogether']]],
    ['Counting-on hint (3 up to 7)', [['q-count-on-from', 'num-end-3'], ['num-mid-4'], ['num-mid-5'], ['num-mid-6'], ['num-end-7']]],
    ['Ten and zero make ten', [['num-mid-10', 'and', 'num-mid-0', 'make', 'num-end-10']]]
  ];
  function soundSection() {
    return {
      id: 'sound', title: 'Sound',
      render: function (el) {
        const status = MW.make('p', 'gu-p gu-lead', null, MW.audio.running() ? 'Tap any line to hear it.' : 'Sound starts after the first tap on Play.');
        el.appendChild(status);
        G.h3(el, 'Sentences built from the pieces');
        let r = G.row(el);
        SAMPLES.forEach(function (s) { G.btn(r, s[0], function () { MW.audio.say(s[1]); }); });
        G.btn(r, 'Every clip in turn', function () {
          const ids = Object.keys(MW.audio.manifest.voice);
          MW.audio.say(ids.map(function (id) { return [id]; }));
        });
        G.btn(r, 'Stop', function () { MW.audio.hush(); }, 'gu-quiet');

        G.h3(el, 'Music');
        r = G.row(el);
        const tog = G.btn(r, MW.audio.music.isOn() ? 'Music is on: turn off' : 'Music is off: turn on', function (b) {
          MW.audio.music.setOn(!MW.audio.music.isOn());
          b.textContent = MW.audio.music.isOn() ? 'Music is on: turn off' : 'Music is off: turn on';
        });
        G.btn(r, 'Hear the loop join', function () {
          if (!MW.audio.music.isOn()) { MW.audio.music.setOn(true); tog.textContent = 'Music is on: turn off'; }
          MW.audio.music.jumpToJoin();
        });
        G.btn(r, 'Hear the dip under a line', function () { MW.audio.say(SAMPLES[1][1]); });
        G.p(el, 'The loop join starts 6 seconds before the end of the track: listen for a smooth fade into the start. During a spoken line the music should drop, then come back.', 'gu-note');

        G.h3(el, 'Sound effects');
        r = G.row(el);
        [['Drop chime', 'chime'], ['Pop', 'pop'], ['Whoosh', 'whoosh'], ['Star', 'twinkle'], ['End of round', 'tune']].forEach(function (e) {
          G.btn(r, e[0], function () { MW.audio.sfx(e[1]); });
        });

        G.h3(el, 'Every clip');
        const groups = {};
        (window.MW_SCRIPT || []).forEach(function (c) { (groups[c.group] = groups[c.group] || []).push(c); });
        Object.keys(groups).forEach(function (g) {
          el.appendChild(MW.make('div', 'gu-group label', null, MW.esc(g)));
          const gr = G.row(el);
          groups[g].forEach(function (c) {
            const b = G.btn(gr, c.words, function () { MW.audio.say([[c.id]]); }, 'gu-clip');
            b.title = c.id;
          });
        });
      }
    };
  }
})();
