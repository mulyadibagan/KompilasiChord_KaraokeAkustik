#!/usr/bin/env python3
"""Static and executable checks for the shared Tab Musik audio engine."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABS = ROOT / "tabs"


def run_node_check(path: Path) -> None:
    subprocess.run(["node", "--check", str(path)], cwd=ROOT, check=True)


def check_inline_scripts(path: Path) -> None:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", path.read_text())
    for index, script in enumerate(scripts):
        if not script.strip():
            continue
        result = subprocess.run(
            ["node", "--check", "-"],
            cwd=ROOT,
            input=script,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, f"{path.name} inline script {index}: {result.stderr}"


def check_harmony_parser() -> None:
    test = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const sandbox = {window: {}, localStorage: {getItem() { return null; }, setItem() {}}};
vm.runInNewContext(fs.readFileSync('tabs/harmony-engine.js', 'utf8'), sandbox);
const harmony = sandbox.window.KCHarmony;
const cases = {
  'Bb': {root: 10, tones: [10, 2, 5]},
  'G#m7b5': {root: 8, tones: [8, 11, 2, 6]},
  'E#dim': {root: 5, tones: [5, 8, 11]},
  'C/E': {root: 0, bass: 4, tones: [0, 4, 7]},
  'F#7': {root: 6, tones: [6, 10, 1, 4]}
};
for (const [name, expected] of Object.entries(cases)) {
  const actual = harmony.chordInfo(name);
  assert.strictEqual(actual.root, expected.root, `${name} root`);
  if ('bass' in expected) assert.strictEqual(actual.bass, expected.bass, `${name} slash bass`);
  assert.strictEqual(JSON.stringify(actual.tones), JSON.stringify(expected.tones), `${name} tones`);
}
assert.strictEqual(harmony.snapMidi('bass', 47, 'Bb', 0, 2), 46, 'B must resolve to Bb');
assert.strictEqual(harmony.snapMidi('bass', 45, 'Bb', 4, 2), 46, 'A must resolve to Bb');
assert.strictEqual(harmony.snapMidi('lead', 64, 'C', 2, 1), 64, 'off-beat passing tone must remain');
"""
    subprocess.run(["node", "-e", test], cwd=ROOT, check=True)


def check_sampler_runtime() -> None:
    test = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

class Param {
  constructor(value = 0) { this.value = value; }
  setValueAtTime(value) { this.value = value; }
  exponentialRampToValueAtTime(value) { this.value = value; }
}
class Node {
  connect(target) { this.target = target; return target; }
  start() { this.started = true; }
  stop() { this.stopped = true; if (this.onended) this.onended(); }
}
class Source extends Node {
  constructor() { super(); this.playbackRate = new Param(1); this.detune = new Param(0); this.loop = false; }
}
class Filter extends Node {
  constructor() { super(); this.frequency = new Param(); this.Q = new Param(); this.gain = new Param(); }
}
class Compressor extends Node {
  constructor() {
    super(); this.threshold = new Param(); this.knee = new Param(); this.ratio = new Param();
    this.attack = new Param(); this.release = new Param();
  }
}
class FakeBuffer {
  constructor(channels = 1, length = 52920, rate = 44100) {
    this.duration = length / rate; this.sampleRate = rate;
    this.data = Array.from({length: channels}, () => new Float32Array(length));
  }
  getChannelData(channel) { return this.data[channel]; }
}
class Context {
  constructor() { this.currentTime = 2; this.sampleRate = 44100; this.baseLatency = .08; this.outputLatency = .1; this.destination = new Node(); this.sources = []; }
  decodeAudioData() { return Promise.resolve(new FakeBuffer()); }
  createGain() { const node = new Node(); node.gain = new Param(1); return node; }
  createBiquadFilter() { return new Filter(); }
  createDynamicsCompressor() { return new Compressor(); }
  createBufferSource() { const source = new Source(); this.sources.push(source); return source; }
  createStereoPanner() { const node = new Node(); node.pan = new Param(); return node; }
  createConvolver() { return new Node(); }
  createDelay() { const node = new Node(); node.delayTime = new Param(); return node; }
  createWaveShaper() { return new Node(); }
  createOscillator() { const node = new Source(); node.frequency = new Param(); this.sources.push(node); return node; }
  createBuffer(channels, length, rate) { return new FakeBuffer(channels, length, rate); }
}

const sandbox = {
  window: {},
  document: {currentScript: {src: 'https://example.test/tabs/cc0-sampler.js'}},
  URL, Float32Array, Math, Promise,
  fetch: async () => ({ok: true, arrayBuffer: async () => new ArrayBuffer(16)})
};
vm.runInNewContext(fs.readFileSync('tabs/cc0-sampler.js', 'utf8'), sandbox);
const sampler = sandbox.window.KCSampler;
const context = new Context();
(async () => {
  assert.strictEqual(await sampler.load(context, ['guitar', 'bass', 'drums']), true);
  assert.strictEqual(sampler.status(['guitar', 'bass', 'drums']).loaded, true);
  const before = context.sources.length;
  assert.strictEqual(sampler.playNote(context, 'guitar', 'C6', 2.2, .1, .2, {profile: 'lead', vibrato: 4}), true);
  assert.strictEqual(context.sources[before].loop, true, 'long note must use prepared sustain loop');
  assert.strictEqual(sampler.playStrum(context, ['C3', 'E3', 'G3'], .4, .08, .2, {profile: 'crunch'}), true);
  assert.strictEqual(sampler.playDrum(context, 'kick', .2, .2, {velocity: .9}), true);
  const timing = sampler.timing(context);
  assert(timing.lookAhead >= .34 && timing.startDelay >= .22 && timing.interval === 40);
  sampler.stopAll();
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    subprocess.run(["node", "-e", test], cwd=ROOT, check=True)


def main() -> None:
    shared = [TABS / "cc0-sampler.js", TABS / "harmony-engine.js", TABS / "tab-mixer-enhancer.js"]
    for path in shared:
        run_node_check(path)

    catalog = json.loads((ROOT / "tab-catalog.json").read_text())
    pages = [ROOT / song["path"] for song in catalog["songs"]]
    assert len(pages) == 7, "audio validation must cover all seven published players"

    forbidden = [
        "function fallbackDrum",
        "function filteredNoise",
        "function synthKick",
        "mode sintesis cadangan",
        "fallback aktif",
        "currentTime+.045",
        "currentTime+.12",
        "setTimeout(scheduler,25)",
    ]
    for path in pages:
        source = path.read_text()
        assert "cc0-sampler.js?v=guitarpro-1" in source, path
        assert "harmony-engine.js?v=guitarpro-1" in source, path
        assert "KCSampler.timing" in source, path
        assert "latencyHint:'playback'" in source, path
        assert "{force:true,kinds:['bass'],mode:'anchor'}" in source, path
        assert "if(!ready)" in source, path
        for text in forbidden:
            assert text not in source, f"{path.name} still contains {text!r}"
        check_inline_scripts(path)

    sampler = (TABS / "cc0-sampler.js").read_text()
    for required in ["source.loop = true", "function prewarm", "function driveCurve", "function instrumentBus", "lateTolerance"]:
        assert required in sampler, f"sampler missing {required}"

    mixer = (TABS / "tab-mixer-enhancer.js").read_text()
    enhanced_songs = {path.stem for path in pages if path.name != "exists-dirantai-digelangi-rindu.html"}
    for slug in enhanced_songs:
        assert f"'{slug}'" in mixer, f"missing Full Band profile for {slug}"
    exists = (TABS / "exists-dirantai-digelangi-rindu.html").read_text()
    assert "Full Band HQ" in exists and "kcExistsBandProfile" in exists

    check_harmony_parser()
    check_sampler_runtime()
    print(f"Validated GuitarPro-class audio safeguards on {len(pages)} Tab Musik players")


if __name__ == "__main__":
    main()
