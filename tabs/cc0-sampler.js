(function (global) {
  'use strict';

  if (global.KCSampler) return;

  var scriptBase = new URL('.', document.currentScript.src);
  function asset(path) { return new URL('../samples/cc0/' + path, scriptBase).href; }

  var manifest = {
    acoustic: [
      { note: 'E2', url: asset('freepats-nylon/e2.mp3') }, { note: 'A2', url: asset('freepats-nylon/a2.mp3') },
      { note: 'D3', url: asset('freepats-nylon/d3.mp3') }, { note: 'G3', url: asset('freepats-nylon/g3.mp3') },
      { note: 'B3', url: asset('freepats-nylon/b3.mp3') }, { note: 'E4', url: asset('freepats-nylon/e4.mp3') },
      { note: 'A4', url: asset('freepats-nylon/a4.mp3') }, { note: 'D5', url: asset('freepats-nylon/d5.mp3') },
      { note: 'G5', url: asset('freepats-nylon/g5.mp3') }
    ],
    guitar: [
      { note: 'C2', url: asset('freepats-clean/c2.mp3') }, { note: 'F2', url: asset('freepats-clean/f2.mp3') },
      { note: 'A2', url: asset('freepats-clean/a2.mp3') }, { note: 'C3', url: asset('freepats-clean/c3.mp3') },
      { note: 'E3', url: asset('freepats-clean/e3.mp3') }, { note: 'G3', url: asset('freepats-clean/g3.mp3') },
      { note: 'B3', url: asset('freepats-clean/b3.mp3') }, { note: 'E4', url: asset('freepats-clean/e4.mp3') },
      { note: 'G4', url: asset('freepats-clean/g4.mp3') }, { note: 'B4', url: asset('freepats-clean/b4.mp3') },
      { note: 'D5', url: asset('freepats-clean/d5.mp3') }, { note: 'G#5', url: asset('freepats-clean/gs5.mp3') },
      { note: 'C#6', url: asset('freepats-clean/cs6.mp3') }
    ],
    bass: [
      { note: 'E2', url: asset('big-little-bass/e2.wav') }, { note: 'A2', url: asset('big-little-bass/a2.wav') },
      { note: 'D3', url: asset('big-little-bass/d3.wav') }, { note: 'G3', url: asset('big-little-bass/g3.wav') },
      { note: 'C4', url: asset('big-little-bass/c4.wav') }
    ],
    piano: [
      { note: 'C2', url: asset('vcsl-kawai-piano/c2.mp3') }, { note: 'C3', url: asset('vcsl-kawai-piano/c3.mp3') },
      { note: 'G3', url: asset('vcsl-kawai-piano/g3.mp3') }, { note: 'D4', url: asset('vcsl-kawai-piano/d4.mp3') },
      { note: 'A4', url: asset('vcsl-kawai-piano/a4.mp3') }, { note: 'C5', url: asset('vcsl-kawai-piano/c5.mp3') },
      { note: 'C6', url: asset('vcsl-kawai-piano/c6.mp3') }
    ],
    strings: [
      { note: 'D2', url: asset('vsco2-strings/d2.mp3') }, { note: 'C3', url: asset('vsco2-strings/c3.mp3') },
      { note: 'F#3', url: asset('vsco2-strings/fs3.mp3') }, { note: 'C4', url: asset('vsco2-strings/c4.mp3') },
      { note: 'G4', url: asset('vsco2-strings/g4.mp3') }, { note: 'D5', url: asset('vsco2-strings/d5.mp3') },
      { note: 'C6', url: asset('vsco2-strings/c6.mp3') }
    ],
    drums: {
      kick: [asset('virtuosity-drums/browser/kick-soft.mp3'), asset('virtuosity-drums/browser/kick-hard-1.mp3'), asset('virtuosity-drums/browser/kick-hard-2.mp3')],
      snare: [asset('virtuosity-drums/browser/snare-soft.mp3'), asset('virtuosity-drums/browser/snare-mid.mp3'), asset('virtuosity-drums/browser/snare-hard.mp3')],
      rimshot: [asset('virtuosity-drums/browser/snare-rim.mp3')],
      hihat: [asset('virtuosity-drums/browser/hihat-closed-1.mp3'), asset('virtuosity-drums/browser/hihat-closed-2.mp3'), asset('virtuosity-drums/browser/hihat-closed-3.mp3')],
      openhat: [asset('virtuosity-drums/browser/hihat-open.mp3')], ride: [asset('virtuosity-drums/browser/ride.mp3')],
      ridebell: [asset('virtuosity-drums/browser/ride-bell.mp3')],
      tomhigh: [asset('virtuosity-drums/browser/tom-high-soft.mp3'), asset('virtuosity-drums/browser/tom-high-hard.mp3')],
      tomlow: [asset('virtuosity-drums/browser/tom-low-soft.mp3'), asset('virtuosity-drums/browser/tom-low-hard.mp3')],
      crash: [asset('virtuosity-drums/browser/crash.mp3')]
    }
  };

  var profiles = {
    acoustic: { attack: .012, sustain: .90, release: .075, highpass: 72, presence: 2550, presenceGain: 1.8, cabinet: 7800, drive: 0, room: .10, delay: 0 },
    clean: { attack: .008, sustain: .84, release: .070, highpass: 82, presence: 2100, presenceGain: 1.4, cabinet: 6800, drive: 0, room: .07, delay: .018 },
    lead: { attack: .006, sustain: .89, release: .085, highpass: 86, presence: 2350, presenceGain: 1.6, cabinet: 6200, drive: .58, room: .08, delay: .055 },
    crunch: { attack: .006, sustain: .76, release: .060, highpass: 94, presence: 1650, presenceGain: 2.0, cabinet: 4750, drive: 2.15, room: .045, delay: .025 },
    distortion: { attack: .004, sustain: .70, release: .055, highpass: 105, presence: 1450, presenceGain: 2.6, cabinet: 4050, drive: 3.75, room: .035, delay: .032 },
    bass: { attack: .006, sustain: .88, release: .075 }, piano: { attack: .006, sustain: .84, release: .095 },
    strings: { attack: .070, sustain: .92, release: .140 }
  };

  function emptyBuffers() { return { acoustic: [], guitar: [], bass: [], piano: [], strings: [], drums: {} }; }
  var state = {
    context: null, buffers: emptyBuffers(), jobs: null, groupLoads: {}, loaded: false, failures: 0,
    active: [], guitarIndex: {}, drumIndex: {}, masterBus: null, guitarBus: null, drumBus: null,
    instrumentBuses: {}, openHats: [], curves: {}
  };

  function noteMidi(note) {
    var match = /^([A-G])([#b]?)(-?\d)$/.exec(note || '');
    if (!match) return 69;
    var semis = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
    return (Number(match[3]) + 1) * 12 + semis[match[1]] + (match[2] === '#' ? 1 : match[2] === 'b' ? -1 : 0);
  }
  function midiName(midi) {
    var names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    return names[((midi % 12) + 12) % 12] + (Math.floor(midi / 12) - 1);
  }
  function requestedGroups(requested) {
    if (!Array.isArray(requested)) return ['acoustic', 'guitar', 'bass', 'piano', 'strings', 'drums'];
    var groups = [];
    requested.forEach(function (name) {
      var wanted = name === 'melody' ? ['acoustic', 'guitar']
        : /^(guitar|guitar1|guitar2)$/.test(name) ? ['guitar'] : name === 'bass' ? ['bass']
        : /^(piano|synth|keyboard)$/.test(name) ? ['piano']
        : /^(other|strings|orchestra)$/.test(name) ? ['strings'] : name === 'drums' ? ['drums'] : [];
      wanted.forEach(function (group) { if (groups.indexOf(group) < 0) groups.push(group); });
    });
    return groups;
  }
  function groupReady(group) {
    if (group !== 'drums') return (state.buffers[group] || []).length > 0;
    return ['kick', 'snare', 'hihat'].every(function (name) { return (state.buffers.drums[name] || []).some(Boolean); });
  }
  function stopAll() {
    state.active.slice().forEach(function (item) { try { item.source.stop(); } catch (_) {} });
    state.active = []; state.openHats = [];
  }
  function resetContext(context) {
    stopAll(); state.context = context; state.buffers = emptyBuffers(); state.jobs = null; state.groupLoads = {};
    state.loaded = false; state.failures = 0; state.masterBus = null; state.guitarBus = null; state.drumBus = null;
    state.instrumentBuses = {}; state.curves = {};
  }
  function ensureJobs(context) {
    if (state.context && state.context !== context) resetContext(context);
    if (state.jobs) return;
    state.context = context; state.jobs = { acoustic: [], guitar: [], bass: [], piano: [], strings: [], drums: {} };
    Object.keys(manifest.drums).forEach(function (name) { state.buffers.drums[name] = []; state.jobs.drums[name] = []; });
  }
  function decode(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.arrayBuffer();
    }).then(function (data) { return state.context.decodeAudioData(data); });
  }
  function nearestZero(buffer, targetSeconds, radiusSeconds) {
    var data = buffer.getChannelData(0), target = Math.max(1, Math.min(data.length - 2, Math.floor(targetSeconds * buffer.sampleRate)));
    var radius = Math.max(32, Math.floor(radiusSeconds * buffer.sampleRate)), start = Math.max(1, target - radius);
    var end = Math.min(data.length - 2, target + radius), best = target, bestScore = Infinity;
    for (var index = start; index <= end; index += 2) {
      if ((data[index - 1] <= 0 && data[index] >= 0) || (data[index - 1] >= 0 && data[index] <= 0)) {
        var score = Math.abs(index - target) / radius + Math.abs(data[index] - data[index - 1]) * 5;
        if (score < bestScore) { best = index; bestScore = score; }
      }
    }
    return best / buffer.sampleRate;
  }
  function loopRegion(buffer) {
    if (!buffer || buffer.duration < .9) return null;
    var start = nearestZero(buffer, Math.max(.22, buffer.duration * .34), .035);
    var end = nearestZero(buffer, Math.min(buffer.duration - .10, buffer.duration * .68), .035);
    return end - start >= .16 ? { start: start, end: end } : null;
  }
  function noteJob(group, index) {
    if (state.jobs[group][index]) return state.jobs[group][index];
    var item = manifest[group][index];
    var job = decode(item.url).then(function (buffer) {
      state.buffers[group].push({ note: item.note, midi: noteMidi(item.note), buffer: buffer, loop: loopRegion(buffer) });
      state.buffers[group].sort(function (left, right) { return left.midi - right.midi; });
      return true;
    }).catch(function () { state.failures += 1; return false; });
    state.jobs[group][index] = job; return job;
  }
  function drumJob(name, index) {
    if (state.jobs.drums[name][index]) return state.jobs.drums[name][index];
    var job = decode(manifest.drums[name][index]).then(function (buffer) {
      state.buffers.drums[name][index] = buffer; return true;
    }).catch(function () { state.failures += 1; return false; });
    state.jobs.drums[name][index] = job; return job;
  }
  function allJobs(group) {
    var jobs = [];
    if (group !== 'drums') manifest[group].forEach(function (_, index) { jobs.push(noteJob(group, index)); });
    else Object.keys(manifest.drums).forEach(function (name) { manifest.drums[name].forEach(function (_, index) { jobs.push(drumJob(name, index)); }); });
    return jobs;
  }
  function seededImpulse(context, seconds, decay, seed) {
    var length = Math.floor(context.sampleRate * seconds), impulse = context.createBuffer(2, length, context.sampleRate), random = seed >>> 0;
    for (var channel = 0; channel < 2; channel += 1) {
      var data = impulse.getChannelData(channel);
      for (var index = 0; index < length; index += 1) {
        random = (1664525 * random + 1013904223) >>> 0;
        data[index] = (random / 4294967296 * 2 - 1) * Math.pow(1 - index / length, decay);
      }
    }
    return impulse;
  }
  function masterBus(context) {
    if (state.masterBus && state.context === context) return state.masterBus;
    var input = context.createGain(), lowCut = context.createBiquadFilter(), compressor = context.createDynamicsCompressor();
    var limiter = context.createDynamicsCompressor(), output = context.createGain();
    lowCut.type = 'highpass'; lowCut.frequency.value = 28;
    compressor.threshold.value = -17; compressor.knee.value = 16; compressor.ratio.value = 2.2; compressor.attack.value = .014; compressor.release.value = .22;
    limiter.threshold.value = -2.5; limiter.knee.value = 1.5; limiter.ratio.value = 18; limiter.attack.value = .002; limiter.release.value = .09;
    output.gain.value = .72; input.connect(lowCut); lowCut.connect(compressor); compressor.connect(limiter); limiter.connect(output); output.connect(context.destination);
    state.masterBus = { input: input, output: output }; return state.masterBus;
  }
  function guitarBus(context) {
    if (state.guitarBus && state.context === context) return state.guitarBus;
    var input = context.createGain(), compressor = context.createDynamicsCompressor(), master = context.createGain(), room = context.createGain();
    var convolver = context.createConvolver(), roomGain = context.createGain(), echo = context.createGain(), delay = context.createDelay(.5);
    var feedback = context.createGain(), echoGain = context.createGain();
    compressor.threshold.value = -19; compressor.knee.value = 14; compressor.ratio.value = 2.4; compressor.attack.value = .009; compressor.release.value = .17;
    master.gain.value = .70; roomGain.gain.value = .105; delay.delayTime.value = .225; feedback.gain.value = .12; echoGain.gain.value = .095;
    convolver.buffer = seededImpulse(context, .52, 3.2, 19790317);
    input.connect(compressor); room.connect(convolver); convolver.connect(roomGain); roomGain.connect(compressor);
    echo.connect(delay); delay.connect(feedback); feedback.connect(delay); delay.connect(echoGain); echoGain.connect(compressor);
    compressor.connect(master); master.connect(masterBus(context).input);
    state.guitarBus = { input: input, room: room, echo: echo }; return state.guitarBus;
  }
  function instrumentBus(context, group) {
    if (state.instrumentBuses[group] && state.context === context) return state.instrumentBuses[group];
    var settings = {
      bass: { hp: 30, lp: 3800, freq: 105, gain: 1.8, threshold: -20, ratio: 3, output: .78 },
      piano: { hp: 58, lp: 11800, freq: 260, gain: -1.8, threshold: -18, ratio: 2, output: .65 },
      strings: { hp: 95, lp: 9200, freq: 2200, gain: -1.2, threshold: -17, ratio: 1.8, output: .56 }
    }[group] || { hp: 45, lp: 12000, freq: 1000, gain: 0, threshold: -18, ratio: 2, output: .68 };
    var input = context.createGain(), highpass = context.createBiquadFilter(), tone = context.createBiquadFilter(), lowpass = context.createBiquadFilter();
    var compressor = context.createDynamicsCompressor(), output = context.createGain();
    highpass.type = 'highpass'; highpass.frequency.value = settings.hp;
    tone.type = group === 'bass' ? 'lowshelf' : 'peaking'; tone.frequency.value = settings.freq; tone.Q.value = .75; tone.gain.value = settings.gain;
    lowpass.type = 'lowpass'; lowpass.frequency.value = settings.lp; lowpass.Q.value = .55;
    compressor.threshold.value = settings.threshold; compressor.knee.value = 12; compressor.ratio.value = settings.ratio;
    compressor.attack.value = group === 'bass' ? .012 : .020; compressor.release.value = group === 'bass' ? .16 : .24;
    output.gain.value = settings.output; input.connect(highpass); highpass.connect(tone); tone.connect(lowpass); lowpass.connect(compressor);
    compressor.connect(output); output.connect(masterBus(context).input); state.instrumentBuses[group] = { input: input }; return state.instrumentBuses[group];
  }
  function drumBus(context) {
    if (state.drumBus && state.context === context) return state.drumBus;
    var input = context.createGain(), compressor = context.createDynamicsCompressor(), master = context.createGain(), room = context.createGain();
    var convolver = context.createConvolver(), roomGain = context.createGain();
    compressor.threshold.value = -18; compressor.knee.value = 14; compressor.ratio.value = 3; compressor.attack.value = .005; compressor.release.value = .15;
    master.gain.value = .66; roomGain.gain.value = .065; convolver.buffer = seededImpulse(context, .58, 2.9, 8675309);
    input.connect(compressor); room.connect(convolver); convolver.connect(roomGain); roomGain.connect(compressor); compressor.connect(master); master.connect(masterBus(context).input);
    state.drumBus = { input: input, room: room }; return state.drumBus;
  }
  function driveCurve(amount) {
    var key = amount.toFixed(2); if (state.curves[key]) return state.curves[key];
    var curve = new Float32Array(1024), normalizer = Math.tanh(amount);
    for (var index = 0; index < curve.length; index += 1) { var value = index * 2 / (curve.length - 1) - 1; curve[index] = Math.tanh(value * amount) / normalizer; }
    state.curves[key] = curve; return curve;
  }
  function prewarm(context, groups) {
    masterBus(context);
    if (groups.indexOf('guitar') >= 0 || groups.indexOf('acoustic') >= 0) {
      guitarBus(context); driveCurve(profiles.lead.drive); driveCurve(profiles.crunch.drive); driveCurve(profiles.distortion.drive);
    }
    if (groups.indexOf('bass') >= 0) instrumentBus(context, 'bass');
    if (groups.indexOf('piano') >= 0) instrumentBus(context, 'piano');
    if (groups.indexOf('strings') >= 0) instrumentBus(context, 'strings');
    if (groups.indexOf('drums') >= 0) drumBus(context);
    return true;
  }
  function load(context, requested) {
    var groups = requestedGroups(requested); if (Array.isArray(requested) && !groups.length) return Promise.resolve(false); ensureJobs(context);
    var requestedLoads = groups.map(function (group) {
      if (!state.groupLoads[group]) state.groupLoads[group] = Promise.all(allJobs(group)).then(function () { return groupReady(group); });
      return state.groupLoads[group];
    });
    return Promise.all(requestedLoads).then(function () { state.loaded = groups.some(groupReady); prewarm(context, groups); return groups.every(groupReady); });
  }
  function remember(source, group) {
    var item = { source: source, group: group }; state.active.push(item);
    source.onended = function () {
      var index = state.active.indexOf(item); if (index >= 0) state.active.splice(index, 1);
      var hatIndex = state.openHats.indexOf(source); if (hatIndex >= 0) state.openHats.splice(hatIndex, 1);
    };
  }
  function nearest(group, note) {
    var list = state.buffers[group] || [], target = noteMidi(note), distance = Infinity, candidates = [];
    list.forEach(function (sample) { var next = Math.abs(sample.midi - target); if (next < distance) { distance = next; candidates = [sample]; } else if (next === distance) candidates.push(sample); });
    if (!candidates.length) return null; if (group !== 'guitar' && group !== 'acoustic') return candidates[0];
    var key = group + String(candidates[0].midi), index = state.guitarIndex[key] || 0; state.guitarIndex[key] = index + 1; return candidates[index % candidates.length];
  }
  function connectGuitar(context, source, gain, voice, profileName, options) {
    var bus = guitarBus(context), highpass = context.createBiquadFilter(), presence = context.createBiquadFilter(), cabinet = context.createBiquadFilter();
    var pan = context.createStereoPanner ? context.createStereoPanner() : context.createGain(), roomSend = context.createGain(), echoSend = context.createGain(), last = source;
    highpass.type = 'highpass'; highpass.frequency.value = voice.highpass; presence.type = 'peaking'; presence.frequency.value = voice.presence;
    presence.Q.value = .8; presence.gain.value = options.muted ? -1.5 : voice.presenceGain; cabinet.type = 'lowpass';
    cabinet.Q.value = profileName === 'acoustic' ? .55 : .82; cabinet.frequency.value = voice.cabinet;
    if (voice.drive > 0) { var drive = context.createWaveShaper(), amount = voice.drive * (options.strong ? 1.15 : 1); drive.curve = driveCurve(amount); drive.oversample = '2x'; last.connect(drive); last = drive; }
    last.connect(highpass); highpass.connect(presence); presence.connect(cabinet); cabinet.connect(pan);
    if (pan.pan) pan.pan.value = Math.max(-1, Math.min(1, options.pan || 0)); pan.connect(gain); gain.connect(bus.input);
    roomSend.gain.value = typeof options.room === 'number' ? options.room : voice.room; echoSend.gain.value = typeof options.delay === 'number' ? options.delay : voice.delay;
    gain.connect(roomSend); roomSend.connect(bus.room); gain.connect(echoSend); echoSend.connect(bus.echo);
  }
  function playNote(context, group, note, duration, volume, offset, options) {
    options = options || {}; var sample = nearest(group, note);
    if (!sample) { load(context, [group]); return false; }
    var source = context.createBufferSource(), gain = context.createGain(), requestedTime = context.currentTime + (offset || 0);
    var start = Math.max(context.currentTime + .002, requestedTime), rate = Math.pow(2, (noteMidi(note) - sample.midi) / 12);
    var wanted = options.muted ? Math.min(duration, .14) : Math.max(.05, duration), available = sample.buffer.duration / rate;
    var shouldLoop = !options.muted && wanted > available - .08 && sample.loop;
    var audibleDuration = shouldLoop ? wanted : Math.max(.05, Math.min(wanted, available - .015)), end = start + audibleDuration;
    var profileName = options.profile || (group === 'acoustic' ? 'acoustic' : group === 'bass' ? 'bass' : group === 'piano' ? 'piano'
      : group === 'strings' ? 'strings' : (options.drive || options.style === 'rhythm') ? 'crunch' : 'clean');
    var voice = profiles[profileName] || profiles.clean;
    var humanize = options.humanize === false ? 0 : ((group === 'guitar' || group === 'acoustic') ? (Math.random() - .5) * (profileName === 'acoustic' ? 2.2 : profileName === 'lead' ? 1.8 : 3.2) : 0);
    var attack = options.muted ? .003 : Math.min(voice.attack, audibleDuration * .3), release = options.muted ? .025 : Math.min(voice.release, audibleDuration * .38);
    var peak = Math.max(.0002, volume), sustain = Math.max(.0002, volume * (options.muted ? .5 : voice.sustain));
    source.buffer = sample.buffer; source.playbackRate.value = rate; source.detune.value = (options.pitch || 0) + humanize;
    if (shouldLoop) { source.loop = true; source.loopStart = sample.loop.start; source.loopEnd = sample.loop.end; }
    gain.gain.setValueAtTime(.0001, start); gain.gain.exponentialRampToValueAtTime(peak, start + attack);
    gain.gain.setValueAtTime(sustain, Math.max(start + attack + .002, end - release)); gain.gain.exponentialRampToValueAtTime(.0001, end);
    if (group === 'guitar' || group === 'acoustic') connectGuitar(context, source, gain, voice, profileName, options);
    else {
      var pan = context.createStereoPanner ? context.createStereoPanner() : context.createGain();
      if (pan.pan) pan.pan.value = Math.max(-1, Math.min(1, options.pan || 0)); source.connect(pan); pan.connect(gain); gain.connect(instrumentBus(context, group).input);
    }
    if (options.vibrato) {
      var lfo = context.createOscillator(), depth = context.createGain(); lfo.frequency.value = 5.1; depth.gain.value = options.vibrato === true ? 7 : options.vibrato;
      lfo.connect(depth); depth.connect(source.detune); lfo.start(start + Math.min(.2, wanted * .32)); lfo.stop(end); remember(lfo, 'modulation');
    }
    remember(source, group); source.start(start); source.stop(end + .02); return true;
  }
  function playFreq(context, group, freq, duration, volume, offset, options) {
    return playNote(context, group, midiName(Math.round(69 + 12 * Math.log(freq / 440) / Math.LN2)), duration, volume, offset, options);
  }
  function playStrum(context, notes, duration, volume, offset, options) {
    options = options || {}; if (!Array.isArray(notes) || !notes.length) return false; var ordered = notes.slice(); if (options.direction === 'up') ordered.reverse();
    var spread = typeof options.spread === 'number' ? options.spread : (options.muted ? .009 : .014), played = false;
    ordered.forEach(function (note, index) {
      var position = ordered.length > 1 ? index / (ordered.length - 1) : .5, pan = (position - .5) * .34 * (options.direction === 'up' ? -1 : 1);
      var level = volume * (.7 + .25 * Math.sin((position + .15) * Math.PI));
      played = playNote(context, 'guitar', typeof note === 'number' ? midiName(note) : note, duration, level, (offset || 0) + index * spread, {
        style: options.style || 'rhythm', profile: options.profile || 'crunch', strong: Boolean(options.strong), muted: Boolean(options.muted),
        room: typeof options.room === 'number' ? options.room : undefined, delay: typeof options.delay === 'number' ? options.delay : undefined,
        pan: pan, pitch: index % 2 ? 1.5 : -1.5
      }) || played;
    });
    return played;
  }
  function chooseDrum(name, velocity) {
    var list = (state.buffers.drums[name] || []).filter(Boolean); if (!list.length) return null;
    var counter = state.drumIndex[name] || 0, index = counter % list.length;
    if (/^(kick|snare|tomhigh|tomlow)$/.test(name) && list.length > 1) index = velocity < .55 ? 0 : velocity > .82 ? list.length - 1 : Math.min(1, list.length - 1);
    else if (name === 'hihat') index = (counter + (velocity > .78 ? 2 : 0)) % list.length;
    state.drumIndex[name] = counter + 1; return list[index];
  }
  function playDrum(context, name, volume, offset, options) {
    options = options || {}; var velocity = typeof options.velocity === 'number' ? options.velocity : .75, buffer = chooseDrum(name, velocity);
    if (!buffer) { load(context, ['drums']); return false; }
    var bus = drumBus(context), source = context.createBufferSource(), filter = context.createBiquadFilter();
    var pan = context.createStereoPanner ? context.createStereoPanner() : context.createGain(), gain = context.createGain(), send = context.createGain();
    var start = Math.max(context.currentTime + .002, context.currentTime + (offset || 0));
    var durations = { kick: .62, snare: .72, rimshot: .55, hihat: .16, openhat: .85, ride: 1.25, ridebell: .95, tomhigh: .72, tomlow: .88, crash: 3.1 };
    var duration = Math.min(buffer.duration, options.duration || durations[name] || .8); source.buffer = buffer; source.playbackRate.value = Math.pow(2, (options.pitch || 0) / 1200);
    if (name === 'kick') { filter.type = 'lowshelf'; filter.frequency.value = 95; filter.gain.value = 3; }
    else if (/^(hihat|openhat|ride|ridebell|crash)$/.test(name)) { filter.type = 'highpass'; filter.frequency.value = name === 'hihat' ? 3200 : 900; }
    else { filter.type = 'peaking'; filter.frequency.value = name.indexOf('tom') === 0 ? 180 : 210; filter.Q.value = .85; filter.gain.value = 1.6; }
    if (pan.pan) pan.pan.value = Math.max(-1, Math.min(1, options.pan || 0));
    gain.gain.setValueAtTime(Math.max(.0001, volume), start); gain.gain.setValueAtTime(Math.max(.0001, volume * .86), Math.max(start + .01, start + duration - .08));
    gain.gain.exponentialRampToValueAtTime(.0001, start + duration); send.gain.value = typeof options.room === 'number' ? options.room : (name === 'kick' ? .02 : name === 'hihat' ? .04 : .08);
    source.connect(filter); filter.connect(pan); pan.connect(gain); gain.connect(bus.input); gain.connect(send); send.connect(bus.room);
    if (name === 'hihat') { state.openHats.slice().forEach(function (open) { try { open.stop(start + .025); } catch (_) {} }); state.openHats = []; }
    if (name === 'openhat') state.openHats.push(source); remember(source, 'drums'); source.start(start); source.stop(start + duration + .02); return true;
  }
  function timing(context) {
    var latency = Math.max(Number(context && context.baseLatency) || 0, Number(context && context.outputLatency) || 0);
    return { lookAhead: Math.min(.55, Math.max(.34, latency * 4 + .18)), startDelay: Math.min(.42, Math.max(.22, latency * 3 + .14)), interval: 40, lateTolerance: .09 };
  }
  function status(requested) {
    var groups = requestedGroups(requested), ready = groups.filter(groupReady), missing = groups.filter(function (group) { return !groupReady(group); });
    return { loaded: groups.length ? missing.length === 0 : state.loaded, failures: state.failures, readyGroups: ready, missingGroups: missing };
  }

  global.KCSampler = { load: load, prewarm: prewarm, playNote: playNote, playFreq: playFreq, playStrum: playStrum, playDrum: playDrum, stopAll: stopAll, status: status, timing: timing };
})(window);
