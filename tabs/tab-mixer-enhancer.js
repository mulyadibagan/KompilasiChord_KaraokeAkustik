(function () {
  'use strict';

  const root = document.querySelector('.kc-player-page');
  const playerbar = document.querySelector('.playerbar');
  const mixer = document.querySelector('.instrument-tabs');
  if (!root || !playerbar || !mixer) return;

  const rows = Array.from(mixer.querySelectorAll('.track-row'));
  const tracks = rows.map((row) => ({
    row,
    key: row.querySelector('[data-mix]')?.dataset.mix,
    enabled: row.querySelector('[data-mix]'),
    volume: row.querySelector('[data-volume]'),
    label: row.querySelector('.view-track')?.textContent.trim() || 'Instrumen'
  })).filter((track) => track.key && track.enabled);
  if (!tracks.length) return;

  const songKey = location.pathname.split('/').pop().replace(/\.html$/i, '');
  const storageKey = `kcBandMixer:${songKey}:v1`;
  let soloSnapshot = null;

  const classify = (track) => {
    const value = `${track.key} ${track.label}`.toLowerCase();
    if (/drum|perkusi/.test(value)) return 'drums';
    if (/bass/.test(value)) return 'bass';
    if (/piano|keyboard|string|pad/.test(value)) return 'keys';
    if (/gitar|guitar|lead|melod/.test(value)) return 'guitar';
    return 'other';
  };

  const presets = {
    full: { guitar: 58, bass: 50, drums: 36, keys: 42, other: 40 },
    guitar: { guitar: 82, bass: 27, drums: 20, keys: 24, other: 20 },
    bass: { guitar: 24, bass: 82, drums: 24, keys: 20, other: 18 },
    silent: { guitar: 0, bass: 0, drums: 0, keys: 0, other: 0 }
  };

  const fire = (element, type) => element?.dispatchEvent(new Event(type, { bubbles: true }));
  const setTrack = (track, enabled, level) => {
    if (track.enabled.checked !== enabled) {
      track.enabled.checked = enabled;
      fire(track.enabled, 'change');
    }
    if (track.volume && Number(track.volume.value) !== level) {
      track.volume.value = String(level);
      fire(track.volume, 'input');
      fire(track.volume, 'change');
    }
  };

  const save = () => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(tracks.map((track) => ({
        key: track.key,
        enabled: track.enabled.checked,
        volume: track.volume ? Number(track.volume.value) : 100
      }))));
    } catch (_) {}
  };

  const restore = () => {
    try {
      const values = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (!Array.isArray(values)) return false;
      values.forEach((value) => {
        const track = tracks.find((item) => item.key === value.key);
        if (track) setTrack(track, Boolean(value.enabled), Number(value.volume));
      });
      return true;
    } catch (_) { return false; }
  };

  const clearActive = () => document.querySelectorAll('.kc-mix-preset.is-active').forEach((button) => button.classList.remove('is-active'));
  const applyPreset = (name, button) => {
    const levels = presets[name];
    tracks.forEach((track) => {
      const level = levels[classify(track)];
      setTrack(track, name !== 'silent', level);
    });
    soloSnapshot = null;
    tracks.forEach((track) => track.row.classList.remove('is-solo'));
    clearActive();
    button?.classList.add('is-active');
    save();
  };

  const presetBar = document.createElement('div');
  presetBar.className = 'kc-mix-presets';
  presetBar.setAttribute('aria-label', 'Preset mixer');
  [['full', 'Full Band'], ['guitar', 'Latihan Gitar'], ['bass', 'Latihan Bass'], ['silent', 'Tab Saja']].forEach(([name, label]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'kc-mix-preset';
    button.dataset.preset = name;
    button.textContent = label;
    button.addEventListener('click', () => applyPreset(name, button));
    presetBar.appendChild(button);
  });
  playerbar.insertAdjacentElement('afterend', presetBar);

  tracks.forEach((track) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'kc-solo';
    button.textContent = 'S';
    button.title = `Solo ${track.label}`;
    button.setAttribute('aria-label', `Solo ${track.label}`);
    button.addEventListener('click', () => {
      if (track.row.classList.contains('is-solo')) {
        (soloSnapshot || []).forEach((value) => {
          const item = tracks.find((candidate) => candidate.key === value.key);
          if (item) setTrack(item, value.enabled, value.volume);
        });
        soloSnapshot = null;
        track.row.classList.remove('is-solo');
      } else {
        soloSnapshot = tracks.map((item) => ({ key: item.key, enabled: item.enabled.checked, volume: item.volume ? Number(item.volume.value) : 100 }));
        tracks.forEach((item) => {
          item.row.classList.toggle('is-solo', item === track);
          setTrack(item, item === track, item === track ? Math.max(72, Number(item.volume?.value || 72)) : Number(item.volume?.value || 0));
        });
      }
      clearActive();
      save();
    });
    track.row.appendChild(button);
    track.enabled.addEventListener('change', () => { clearActive(); save(); });
    track.volume?.addEventListener('change', () => { clearActive(); save(); });
  });

  const style = document.createElement('style');
  style.textContent = `
    .kc-mix-presets{display:flex;gap:8px;align-items:center;padding:9px 16px;background:#172235;border-top:1px solid #34445d;border-bottom:1px solid #34445d;overflow-x:auto}
    .kc-mix-preset,.kc-solo{border:1px solid #53647e;background:#26344a;color:#fff;border-radius:8px;font-weight:800;cursor:pointer;white-space:nowrap}
    .kc-mix-preset{padding:7px 12px}.kc-mix-preset:hover,.kc-mix-preset.is-active{background:#ef233c;border-color:#ef233c}
    .kc-solo{width:30px;height:30px;padding:0;flex:0 0 30px}.track-row.is-solo .kc-solo{background:#f5b700;border-color:#f5b700;color:#111827}
    .track-row{gap:7px}.track-volume{min-width:54px}
    @media(max-width:720px){.kc-mix-presets{padding:8px 10px}.kc-mix-preset{padding:7px 10px;font-size:12px}.kc-solo{width:28px;height:28px;flex-basis:28px}}
  `;
  document.head.appendChild(style);

  if (!restore()) applyPreset('full', presetBar.querySelector('[data-preset="full"]'));
})();
