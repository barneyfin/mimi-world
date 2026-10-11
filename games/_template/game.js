/* The starter game (games/_template): copy this folder to start a new MeeMee World game, and change every
   'starter' in every file to the new game's id (the meemee-world skill says how).
   It shows every part a game needs: joining the world, a screen of its own, speaking, the world's token and pausing,
   saving, Home, and a section in the grown-ups area. The play itself is a placeholder: tap the big star three times. */
(function () {
  'use strict';
  const MW = window.MW;
  const W = MW.world;
  const ID = 'starter';
  const SCREEN = 'screen-starter-play';
  let star = null, taps = 0;

  // Join the world. Its name, planet, badge and spoken name come from game.json.
  W.game({
    id: ID,
    build: build,                       // once, when the page opens: make the screens
    start: start,                       // its planet was tapped (and its name said)
    sections: [{ id: ID + '-progress', title: 'Star game', render: renderProgress }],   // grown-ups area tabs
    onPause: function () {},            // grown-ups area open, tablet upright or screen off: stop anything moving
    onResume: function () {             // carry on: usually, ask again
      if (MW.shell.screen === SCREEN && W.st.phase === 'starter-play') W.speak([['starter-tap']]);
    },
    onHome: function () { taps = 0; }   // the player went home (from any screen): put things away
  });

  function build() {
    const s = W.screen(SCREEN, 'Star game');
    star = MW.make('button', 'mw-abs starter-star', { type: 'button', 'aria-label': 'The star', style: 'left:520px;top:280px' });
    const pic = MW.art('starter-star'); pic.setAttribute('width', 240); pic.setAttribute('height', 240);
    star.appendChild(pic);
    MW.onTap(star, tapStar);
    s.appendChild(star);
    // Hear-again repeats the current instruction, only while there is one
    MW.shell.buttons(s, ['home', 'music', 'hear'], { home: W.home, hear: function () { if (W.st.phase === 'starter-play') W.speak([['starter-tap']]); } });
  }

  async function start() {
    // The world has just moved the token on (opening a planet does). To start again from inside the game
    // (an "another round" button), move it on yourself first: const token = ++W.st.token;
    W.st.phase = 'starter-play';
    taps = 0;
    MW.shell.show(SCREEN);
    await W.speak([['starter-tap']]);
  }

  async function tapStar() {
    if (W.st.paused || W.st.phase !== 'starter-play') return;
    const token = W.st.token;           // if the player leaves while we wait, the world changes the token
    taps++;
    MW.audio.sfx('pop');
    star.classList.remove('is-hop'); void star.offsetWidth; star.classList.add('is-hop');
    MW.log('starter', 'tap ' + taps);
    if (taps < 3) return;
    W.st.phase = 'starter-done';
    const saved = MW.store.game(ID);    // this game's own saved data on the tablet
    saved.rounds = (saved.rounds || 0) + 1;
    MW.store.save();
    MW.audio.sfx('chime');
    await W.speak([['starter-done']]);
    if (!(await W.ok(token))) return;   // left meanwhile: do nothing more
    W.home();
  }

  function renderProgress(el) {
    const saved = MW.store.peek(ID);    // reading only: peek never creates anything (game(ID) is for changing it)
    MW.grownups.p(el, 'Rounds finished on this tablet: ' + (saved.rounds || 0) + '.', 'gu-lead');
  }
})();
