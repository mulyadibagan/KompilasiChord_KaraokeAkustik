(function () {
  'use strict';
  var data = window.KC_TAB_DATA;
  if (!data || !data.tracks || !data.tracks.length) return;
  var tabs = document.getElementById('instrument-tabs');
  var bars = document.getElementById('bars');
  var seek = document.getElementById('seek');
  var firstMelodyTrack = data.tracks.reduce(function (best, item, index) {
    if (item.percussion) return best;
    var count = item.measures.reduce(function (sum, measure) { return sum + measure.events.length; }, 0);
    return best.index < 0 || count > best.count ? {index:index,count:count} : best;
  }, {index:-1,count:-1}).index;
  var state = { track: firstMelodyTrack < 0 ? 0 : firstMelodyTrack, tick: 0, running: false, timer: 0, last: performance.now() };

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function track() { return data.tracks[state.track]; }
  function maxTick() { return Math.max(0, data.measureCount * 16 - 1); }
  function stringLabel(item, index) {
    if (track().percussion) return item && item.name ? item.name : 'Drum ' + (index + 1);
    return item && item.name ? item.name.replace(/\d+$/, '') : 'S' + (index + 1);
  }
  function measureTab(measure) {
    var strings = track().strings.length ? track().strings : [{name:'Drum'}];
    var grid = strings.map(function () { return Array(16).fill('--'); });
    measure.events.forEach(function (event) {
      var row = Math.min(grid.length - 1, Math.max(0, event.string));
      var noteText = track().percussion ? '●' : String(event.fret).padStart(2, '-');
      grid[row][event.slot] = '<span class="tab-note" data-slot="' + event.slot + '">' + noteText + '</span>';
      for (var i = 1; i < event.duration && event.slot + i < 16; i++) {
        if (!track().percussion && grid[row][event.slot + i] === '--') grid[row][event.slot + i] = '<span class="tab-hold" data-slot="' + (event.slot + i) + '">~~</span>';
      }
    });
    return strings.map(function (item, index) {
      return stringLabel(item, index).padEnd(2, ' ') + ' |' + grid[index].join('') + '|';
    }).join('\n');
  }
  function renderTabs() {
    tabs.innerHTML = data.tracks.map(function (item, index) {
      return '<button class="view-track" type="button" data-track="' + index + '" aria-selected="' + (index === state.track) + '">♫ ' + escapeHtml(item.name) + '</button>';
    }).join('');
  }
  function renderScore() {
    var current = track();
    document.getElementById('score-title').textContent = current.name + ' · Full Lagu';
    document.getElementById('tuning').textContent = current.percussion ? 'Track perkusi' : 'Tuning ' + current.strings.map(function (s) { return s.name; }).join(' ');
    bars.innerHTML = current.measures.map(function (measure, index) {
      return '<article class="bar-card" data-bar="' + index + '"><div class="bar-label"><strong>' + escapeHtml(measure.section || '') + '</strong><span>Birama ' + measure.number + '</span></div><pre>' + measureTab(measure) + '</pre></article>';
    }).join('');
    seek.max = maxTick();
    seek.value = Math.min(state.tick, Number(seek.max));
    highlight(false);
  }
  function highlight(autoScroll) {
    var barIndex = Math.floor(state.tick / 16), slot = state.tick % 16;
    document.querySelectorAll('.current').forEach(function (el) { el.classList.remove('current'); });
    var activeCard = null;
    document.querySelectorAll('.bar-card').forEach(function (card) {
      var active = Number(card.dataset.bar) === barIndex;
      card.classList.toggle('active', active);
      if (active) {
        activeCard = card;
        card.style.setProperty('--cursor', (2 + slot * 6) + '%');
        card.querySelectorAll('[data-slot="' + slot + '"]').forEach(function (el) { el.classList.add('current'); });
      }
    });
    document.getElementById('position').textContent = 'Birama ' + (barIndex + 1) + '/' + data.measureCount + ' · 1/16 ' + (slot + 1);
    document.getElementById('position-time').textContent = 'Birama ' + (barIndex + 1);
    seek.value = state.tick;
    if (autoScroll && activeCard && slot === 0) activeCard.scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  function frame(now) {
    if (!state.running) return;
    var interval = 60000 / Math.max(30, data.tempo) / 4;
    if (now - state.last >= interval) {
      var steps = Math.max(1, Math.floor((now - state.last) / interval));
      state.last += steps * interval;
      state.tick += steps;
      if (state.tick > maxTick()) {
        if (document.getElementById('loop').checked) state.tick = state.tick % (maxTick() + 1);
        else { state.tick = maxTick(); highlight(true); return stop(); }
      }
      highlight(true);
    }
    state.timer = requestAnimationFrame(frame);
  }
  function stop() {
    state.running = false;
    cancelAnimationFrame(state.timer);
    document.getElementById('play').textContent = '▶ Putar';
  }
  function togglePlay() {
    if (state.running) return stop();
    if (state.tick >= maxTick()) state.tick = 0;
    state.running = true;
    state.last = performance.now();
    document.getElementById('play').textContent = '⏸ Jeda';
    state.timer = requestAnimationFrame(frame);
  }
  tabs.addEventListener('click', function (event) {
    var button = event.target.closest('[data-track]'); if (!button) return;
    state.track = Number(button.dataset.track);
    renderTabs();
    renderScore();
  });
  document.getElementById('play').addEventListener('click', togglePlay);
  document.getElementById('stop').addEventListener('click', function () { stop(); state.tick = 0; highlight(false); });
  document.getElementById('rewind').addEventListener('click', function () { state.tick = 0; highlight(false); });
  seek.addEventListener('input', function () { state.tick = Number(this.value); state.last = performance.now(); highlight(false); });
  document.addEventListener('keydown', function (event) {
    if (event.code !== 'Space' || /INPUT|TEXTAREA|BUTTON/.test(document.activeElement && document.activeElement.tagName)) return;
    event.preventDefault(); togglePlay();
  });
  document.getElementById('song-meta').textContent = data.tempo + ' BPM · ' + data.measureCount + ' birama · ' + data.tracks.length + ' instrumen';
  renderTabs(); renderScore();
})();
