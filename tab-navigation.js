(function () {
  'use strict';

  var script = document.currentScript;
  var base = script && script.getAttribute('data-base') || '.';
  var isEmbed = new URLSearchParams(window.location.search).get('embed') === '1' || window.self !== window.top;
  if (isEmbed) document.documentElement.classList.add('embed');
  var catalogUrl = base.replace(/\/$/, '') + '/tab-catalog.json?v=20260815';
  var catalogPageUrl = withEmbed(base.replace(/\/$/, '') + '/tab-musik.html');
  var homeUrl = 'https://www.kompilasichord.com/';
  var playerPage = document.body.classList.contains('kc-player-page');
  var libraryPage = document.body.classList.contains('kc-library-page');
  var playerControls = null;

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[character];
    });
  }

  function normalize(value) {
    var text = String(value == null ? '' : value).toLowerCase();
    return typeof text.normalize === 'function'
      ? text.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      : text;
  }

  function withEmbed(url) {
    if (!isEmbed) return url;
    return url + (url.indexOf('?') === -1 ? '?' : '&') + 'embed=1';
  }

  function songUrl(song) {
    var url = base.replace(/\/$/, '') + '/' + song.path;
    url += (url.indexOf('?') === -1 ? '?' : '&') + 'v=20260817-note-label-removed';
    return withEmbed(url);
  }

  function searchText(song) {
    return normalize([
      song.title,
      song.artist,
      song.key,
      song.bpmLabel,
      (song.instruments || []).join(' '),
      (song.searchTerms || []).join(' ')
    ].join(' '));
  }

  function currentFile() {
    var parts = window.location.pathname.split('/');
    return decodeURIComponent(parts[parts.length - 1] || '');
  }

  function currentSongFrom(songs) {
    var file = currentFile();
    return songs.filter(function (song) {
      var pieces = song.path.split('/');
      return pieces[pieces.length - 1] === file;
    })[0] || null;
  }

  function playerFallback() {
    var heading = document.querySelector('.songline h1');
    var details = document.querySelector('.songline p');
    var artist = details ? details.textContent.split('·')[0].trim() : '';
    return {
      title: heading ? heading.textContent.trim() : 'Pilih lagu',
      artist: artist
    };
  }

  function buildPlayerHeader() {
    var header = document.querySelector('.topbar');
    if (!header) return null;
    var fallback = playerFallback();
    header.className = 'topbar kc-topbar';
    header.innerHTML =
      '<a class="kc-brand" href="' + homeUrl + '" target="_top" aria-label="KompilasiChord, kembali ke beranda">' +
        '<svg aria-hidden="true" class="kc-brand-mark" focusable="false" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">' +
          '<rect fill="#D71920" height="64" rx="14" width="64"></rect>' +
          '<path d="M32 9C43 9 50 14 50 24c0 14-8 25-18 31C22 49 14 38 14 24 14 14 21 9 32 9Z" fill="none" stroke="#fff" stroke-linejoin="round" stroke-width="4"></path>' +
          '<path d="M27 20v24M27 32l12-12M27 32l12 12" fill="none" stroke="#fff" stroke-linecap="round" stroke-linejoin="round" stroke-width="4"></path>' +
        '</svg>' +
        '<span class="kc-brand-copy">' +
          '<span class="kc-brand-name">Kompilasi<span>Chord</span></span>' +
          '<span class="kc-brand-sub">Tab Musik Interaktif</span>' +
        '</span>' +
      '</a>' +
      '<div class="kc-song-picker">' +
        '<button class="kc-picker-trigger" type="button" aria-haspopup="dialog" aria-expanded="false" aria-controls="kc-picker-panel">' +
          '<span class="kc-picker-icon" aria-hidden="true">♫</span>' +
          '<span class="kc-picker-copy">' +
            '<span class="kc-picker-label">Pilih Tab Musik</span>' +
            '<strong class="kc-picker-current">' + escapeHtml(fallback.title + (fallback.artist ? ' · ' + fallback.artist : '')) + '</strong>' +
          '</span>' +
          '<span class="kc-picker-chevron" aria-hidden="true">⌄</span>' +
        '</button>' +
        '<div class="kc-picker-panel" id="kc-picker-panel" role="dialog" aria-label="Pilih tab musik" hidden>' +
          '<label class="kc-picker-search-label" for="kc-picker-search">Cari judul lagu atau artis</label>' +
          '<input class="kc-picker-search" id="kc-picker-search" type="search" placeholder="Contoh: Kahitna atau Cerita Cinta" autocomplete="off" role="combobox" aria-controls="kc-picker-results" aria-expanded="false">' +
          '<div class="kc-picker-summary" id="kc-picker-summary" aria-live="polite">Memuat katalog lagu…</div>' +
          '<div class="kc-picker-results" id="kc-picker-results" role="listbox"></div>' +
          '<a class="kc-picker-all" href="' + escapeHtml(catalogPageUrl) + '">Lihat semua tab musik →</a>' +
        '</div>' +
      '</div>';

    var picker = header.querySelector('.kc-song-picker');
    var trigger = header.querySelector('.kc-picker-trigger');
    var panel = header.querySelector('.kc-picker-panel');
    var input = header.querySelector('.kc-picker-search');
    var summary = header.querySelector('.kc-picker-summary');
    var results = header.querySelector('.kc-picker-results');
    var currentLabel = header.querySelector('.kc-picker-current');
    var songs = [];
    var current = null;

    function render(query) {
      var needle = normalize(query).trim();
      var matches = songs.filter(function (song) {
        return !needle || searchText(song).indexOf(needle) !== -1;
      });
      if (!needle && current) {
        matches = [current].concat(matches.filter(function (song) {
          return song.slug !== current.slug;
        }));
      }
      var visible = matches.slice(0, 10);
      summary.textContent = matches.length
        ? (matches.length > visible.length
          ? 'Menampilkan ' + visible.length + ' dari ' + matches.length + ' lagu. Ketik lebih spesifik.'
          : matches.length + ' lagu ditemukan.')
        : 'Tidak ada lagu yang cocok.';
      results.innerHTML = visible.length
        ? visible.map(function (song) {
            var selected = current && song.slug === current.slug;
            return '<a class="kc-picker-result" href="' + escapeHtml(songUrl(song)) + '" role="option" aria-selected="' + (selected ? 'true' : 'false') + '">' +
              '<strong>' + escapeHtml(song.title) + (selected ? ' · Sedang dibuka' : '') + '</strong>' +
              '<span class="kc-result-artist">' + escapeHtml(song.artist) + '</span>' +
              '<span class="kc-result-meta">' + escapeHtml(song.key + ' · ' + song.bpmLabel) + '</span>' +
            '</a>';
          }).join('')
        : '<div class="kc-picker-empty">Coba judul atau nama artis yang lain.</div>';
    }

    function openPicker() {
      panel.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      input.setAttribute('aria-expanded', 'true');
      input.value = '';
      render('');
      window.setTimeout(function () { input.focus(); }, 0);
    }

    function closePicker(restoreFocus) {
      if (panel.hidden) return;
      panel.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
      input.setAttribute('aria-expanded', 'false');
      if (restoreFocus) trigger.focus();
    }

    trigger.addEventListener('click', function () {
      if (panel.hidden) openPicker();
      else closePicker(false);
    });
    input.addEventListener('input', function () { render(input.value); });
    document.addEventListener('click', function (event) {
      if (!panel.hidden && !picker.contains(event.target)) closePicker(false);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !panel.hidden) {
        event.preventDefault();
        closePicker(true);
      }
    });

    return {
      setSongs: function (loadedSongs) {
        songs = loadedSongs;
        current = currentSongFrom(songs);
        if (current) currentLabel.textContent = current.title + ' · ' + current.artist;
        render('');
      },
      setError: function () {
        summary.textContent = 'Katalog belum dapat dimuat.';
        results.innerHTML = '<div class="kc-picker-empty">Gunakan tombol “Lihat semua tab musik” untuk kembali ke katalog.</div>';
      }
    };
  }

  function initLibrary(songs) {
    var input = document.getElementById('search');
    var grid = document.getElementById('songs');
    var count = document.getElementById('count');
    var empty = document.getElementById('empty');
    var loadMore = document.getElementById('load-more');
    if (!input || !grid || !count || !empty || !loadMore) return;
    var pageSize = 12;
    var limit = pageSize;

    function card(song) {
      var meta = [song.key, song.bpmLabel].concat(song.instruments || []);
      return '<a class="song" href="' + escapeHtml(songUrl(song)) + '">' +
        '<span class="status">' + escapeHtml(song.status) + '</span>' +
        '<h2>' + escapeHtml(song.title) + '</h2>' +
        '<p class="artist">' + escapeHtml(song.artist) + '</p>' +
        '<div class="meta">' + meta.map(function (item) {
          return '<span>' + escapeHtml(item) + '</span>';
        }).join('') + '</div>' +
        '<span class="open">Buka player tab →</span>' +
      '</a>';
    }

    function render(resetLimit) {
      if (resetLimit) limit = pageSize;
      var needle = normalize(input.value).trim();
      var matches = songs.filter(function (song) {
        return !needle || searchText(song).indexOf(needle) !== -1;
      });
      var visible = matches.slice(0, limit);
      grid.innerHTML = visible.map(card).join('');
      count.textContent = matches.length + (needle ? ' tab ditemukan' : ' tab tersedia');
      empty.style.display = matches.length ? 'none' : 'block';
      loadMore.hidden = visible.length >= matches.length;
      if (!loadMore.hidden) {
        loadMore.textContent = 'Tampilkan ' + Math.min(pageSize, matches.length - visible.length) + ' lagu berikutnya';
      }
    }

    input.addEventListener('input', function () { render(true); });
    loadMore.addEventListener('click', function () {
      limit += pageSize;
      render(false);
    });

    var initialQuery = new URLSearchParams(window.location.search).get('q');
    if (initialQuery) input.value = initialQuery;
    render(true);
  }

  function showLibraryError() {
    var grid = document.getElementById('songs');
    var count = document.getElementById('count');
    if (grid) grid.innerHTML = '<div class="catalog-error">Katalog belum dapat dimuat. Muat ulang halaman untuk mencoba kembali.</div>';
    if (count) count.textContent = 'Katalog tidak tersedia';
  }

  function openRequestedSong(songs) {
    var params = new URLSearchParams(window.location.search);
    var requested = params.get('lagu') || params.get('t') || params.get('song') || params.get('slug');
    if (!requested) return false;

    var aliases = {
      'bunga-terakhir': 'romeo-bunga-terakhir',
      'hati-siapa-tak-luka': 'anie-carera-hati-siapa-tak-luka',
      'cerita-cinta': 'kahitna-cerita-cinta'
    };
    var targetSlug = aliases[requested] || requested;
    var target = songs.filter(function (song) { return song.slug === targetSlug; })[0];
    if (!target) return false;

    window.location.replace(songUrl(target));
    return true;
  }

  if (playerPage) playerControls = buildPlayerHeader();

  fetch(catalogUrl, { cache: 'no-cache' })
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (catalog) {
      var songs = Array.isArray(catalog.songs) ? catalog.songs : [];
      if (playerControls) playerControls.setSongs(songs);
      if (libraryPage && !openRequestedSong(songs)) initLibrary(songs);
    })
    .catch(function () {
      if (playerControls) playerControls.setError();
      if (libraryPage) showLibraryError();
    });
})();
