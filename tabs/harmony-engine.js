(function () {
  'use strict';
  if (window.KCHarmony) return;

  var PITCH = {
    C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4, Fb: 4, 'E#': 5,
    F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10,
    Bb: 10, B: 11, Cb: 11
  };
  var RANGE = { lead: [52, 81, 64], vocal: [48, 76, 61], bass: [28, 55, 40] };

  function unique(values) {
    return values.filter(function (value, index) { return values.indexOf(value) === index; });
  }

  function chordInfo(name) {
    var raw = String(name || '').replace(/♯/g, '#').replace(/♭/g, 'b').trim();
    var match = /^([A-G](?:#|b)?)([^/]*?)(?:\/([A-G](?:#|b)?))?$/.exec(raw);
    if (!match || typeof PITCH[match[1]] !== 'number') return null;
    var root = PITCH[match[1]], suffix = (match[2] || '').replace(/[()\s]/g, ''), lower = suffix.toLowerCase();
    var minor = (/^(m(?!aj)|min)/.test(lower) || /dim|°|ø/.test(lower));
    var third = /sus2/.test(lower) ? 2 : /sus(?:4)?/.test(lower) ? 5 : minor ? 3 : 4;
    var fifth = /dim|b5|ø/.test(lower) ? 6 : /aug|#5|\+/.test(lower) ? 8 : 7;
    var intervals = [0, third, fifth];
    if (/dim7|°7/.test(lower)) intervals.push(9);
    else if (/maj7|ma7|Δ7/.test(suffix)) intervals.push(11);
    else if (/7/.test(lower)) intervals.push(10);
    if (/(^|[^0-9])6/.test(lower) || /13/.test(lower)) intervals.push(9);
    if (/add9|(^|[^0-9])9/.test(lower)) intervals.push(2);
    if (/11/.test(lower)) intervals.push(5);
    var bass = match[3] && typeof PITCH[match[3]] === 'number' ? PITCH[match[3]] : root;
    var tones = unique(intervals.map(function (interval) { return (root + interval) % 12; }));
    return {
      name: raw,
      root: root,
      bass: bass,
      intervals: unique(intervals),
      tones: tones,
      stableTones: unique([bass, root, (root + fifth) % 12])
    };
  }

  function inRangeCandidates(midi, range) {
    var out = [];
    for (var note = midi - 36; note <= midi + 36; note += 12) if (note >= range[0] && note <= range[1]) out.push(note);
    return out.length ? out : [Math.max(range[0], Math.min(range[1], midi))];
  }

  function octaveSmooth(midi, previous, range) {
    var target = previous == null ? range[2] : previous, candidates = inRangeCandidates(midi, range);
    return candidates.reduce(function (best, note) { return Math.abs(note - target) < Math.abs(best - target) ? note : best; }, candidates[0]);
  }

  function nearestTone(midi, tones, range) {
    var best = midi, distance = 99;
    for (var note = range[0]; note <= range[1]; note += 1) {
      if (tones.indexOf(((note % 12) + 12) % 12) >= 0 && Math.abs(note - midi) < distance) {
        best = note;
        distance = Math.abs(note - midi);
      }
    }
    return { midi: best, distance: distance };
  }

  function harmonize(kind, midi, chord, slot, duration, range) {
    var info = chordInfo(chord);
    if (!info) return midi;
    var pitch = ((midi % 12) + 12) % 12;
    if (info.tones.indexOf(pitch) >= 0) return midi;
    var strong = slot % 4 === 0 || duration >= 4;
    if (!strong) return midi;
    if (kind === 'bass') {
      var bassTarget = nearestTone(midi, info.stableTones, range);
      var threshold = slot % 16 === 0 ? 5 : 3;
      return bassTarget.distance <= threshold ? bassTarget.midi : midi;
    }
    var melodicTarget = nearestTone(midi, info.tones, range);
    var melodicThreshold = duration >= 6 ? 2 : 1;
    return melodicTarget.distance <= melodicThreshold ? melodicTarget.midi : midi;
  }

  function bassPosition(midi) {
    var tuning = [43, 38, 33, 28], best = null;
    tuning.forEach(function (open, string) {
      var fret = midi - open;
      if (fret >= 0 && fret <= 20 && (!best || fret < best.fret)) best = { string: string, fret: fret };
    });
    return best || { string: 3, fret: Math.max(0, midi - 28) };
  }

  function removePitchSpikes(events) {
    return events.filter(function (event, index) {
      if (event[1] > 1 || index === 0 || index === events.length - 1) return true;
      var before = events[index - 1][2], after = events[index + 1][2], note = event[2];
      return !(Math.abs(before - after) <= 4 && Math.abs(note - before) >= 8 && Math.abs(note - after) >= 8);
    });
  }

  function limitDensity(events, kind) {
    var maximum = kind === 'bass' ? 12 : kind === 'vocal' ? 10 : 12;
    if (events.length <= maximum) return events;
    var ranked = events.map(function (event, index) {
      return { event: event, index: index, score: event[1] * 3 + (event[0] % 4 === 0 ? 4 : 0) };
    });
    ranked.sort(function (left, right) { return right.score - left.score || left.index - right.index; });
    var keep = ranked.slice(0, maximum).map(function (item) { return item.index; });
    return events.filter(function (_, index) { return keep.indexOf(index) >= 0; });
  }

  function cleanBar(raw, kind, barIndex, chordAt, previous, options, report) {
    var range = RANGE[kind], events = (raw || []).filter(function (event) {
      return event && event.length >= 3 && isFinite(event[0]) && isFinite(event[1]) && isFinite(event[2]);
    }).map(function (event) {
      var copy = event.slice();
      copy[0] = Math.max(0, Math.min(15, Number(copy[0])));
      copy[1] = Math.max(.125, Number(copy[1]));
      copy[2] = Math.round(copy[2]);
      return copy;
    });
    events.sort(function (left, right) { return left[0] - right[0] || right[1] - left[1]; });
    events.forEach(function (event) {
      var original = event[2], midi = options.mode === 'anchor' ? original : octaveSmooth(original, previous.value, range);
      midi = harmonize(kind, midi, chordAt(barIndex, event[0]), event[0], event[1], range);
      if (options.mode !== 'anchor') midi = octaveSmooth(midi, previous.value, range);
      event[2] = midi;
      previous.value = midi;
      if (midi !== original) report.corrections += 1;
      report.events += 1;
      if (kind === 'bass' && event.length >= 5 && midi !== original) {
        var position = bassPosition(midi);
        event[3] = position.string;
        event[4] = position.fret;
      }
    });
    if (options.simplify) {
      events = removePitchSpikes(events);
      events = limitDensity(events, kind);
      events = events.filter(function (event, index) { return index === 0 || event[0] !== events[index - 1][0]; });
      events.forEach(function (event, index) {
        var next = index + 1 < events.length ? events[index + 1][0] : 16;
        event[1] = Math.max(.125, Math.min(event[1], next - event[0], 16 - event[0]));
      });
    }
    return events;
  }

  function clean(transcription, chordAt, options) {
    options = options || {};
    if (!transcription || typeof chordAt !== 'function') return transcription;
    if (transcription.meta && transcription.meta.preservePitch && !options.force) return transcription;
    var kinds = options.kinds || ['lead', 'vocal', 'bass'];
    var marker = [options.force ? 'force' : 'normal', options.mode || 'clean', kinds.join(',')].join(':');
    var completed = transcription.__harmonyCleaned || {};
    if (completed[marker]) return transcription;
    var report = { mode: options.mode || 'clean', kinds: kinds.slice(), events: 0, corrections: 0 };
    kinds.forEach(function (kind) {
      var bars = transcription[kind] || [], previous = { value: null };
      transcription[kind] = bars.map(function (events, barIndex) {
        return cleanBar(events, kind, barIndex, chordAt, previous, options, report);
      });
    });
    completed[marker] = true;
    try {
      Object.defineProperty(transcription, '__harmonyCleaned', { value: completed, configurable: true });
      Object.defineProperty(transcription, '__harmonyReport', { value: report, configurable: true });
    } catch (_) {
      transcription.__harmonyCleaned = completed;
      transcription.__harmonyReport = report;
    }
    return transcription;
  }

  function snapMidi(kind, midi, chord, slot, duration) {
    var range = RANGE[kind] || RANGE.lead;
    return harmonize(kind, Math.round(midi), chord, Number(slot) || 0, Number(duration) || 1, range);
  }

  function resetMix(storageKey, defaults) {
    try {
      if (localStorage.getItem('kcTabMixVersion') !== storageKey) {
        localStorage.setItem('kcTabVolumes', JSON.stringify(defaults));
        localStorage.setItem('kcTabMixVersion', storageKey);
        return true;
      }
    } catch (_) {}
    return false;
  }

  window.KCHarmony = { clean: clean, snapMidi: snapMidi, chordInfo: chordInfo, resetMix: resetMix };
})();
