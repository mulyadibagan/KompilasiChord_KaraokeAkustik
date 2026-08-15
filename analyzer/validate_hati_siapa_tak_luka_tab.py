#!/usr/bin/env python3
"""Regression checks for the MP3-derived Hati Siapa Tak Luka tab."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tabs" / "anie-carera-hati-siapa-tak-luka-data.js"
HTML_PATH = ROOT / "tabs" / "anie-carera-hati-siapa-tak-luka.html"
SAMPLER_PATH = ROOT / "tabs" / "cc0-sampler.js"
CATALOG_PATH = ROOT / "tab-catalog.json"
GENERATOR_PATH = ROOT / "analyzer" / "rebuild_hati_siapa_tak_luka_tab.py"
PREFIX = "window.KC_HATI_SIAPA_TAK_LUKA_TRANSCRIPTION="
SOURCE_SHA256 = "f4819f91d08cf21ec16c84db3eac949012e2be7326a45ca93a48cdb62c4745ca"
DRUM_KEYS = {"h", "s", "k", "c", "t"}


def load_transcription() -> dict:
    source = DATA_PATH.read_text(encoding="utf-8").strip()
    assert source.startswith(PREFIX) and source.endswith(";"), DATA_PATH
    return json.loads(source[len(PREFIX) : -1])


def validate_guitar(bars: list[list[list[int]]], expected: int) -> int:
    open_strings = (64, 59, 55, 50, 45, 40)
    assert len(bars) == 96
    total = 0
    for bar_index, events in enumerate(bars):
        assert events == sorted(events, key=lambda event: (event[0], event[3], event[2]))
        starts_and_pitches = set()
        starts_and_strings = set()
        polyphony: dict[int, int] = {}
        for event in events:
            assert len(event) == 5, (bar_index, event)
            slot, duration, midi, string, fret = event
            assert 0 <= slot < 16 and 1 <= duration <= 16 - slot
            assert 40 <= midi <= 84
            assert 0 <= string < 6 and 0 <= fret <= 20
            assert midi == open_strings[string] + fret, (bar_index, event)
            assert (slot, midi) not in starts_and_pitches, (bar_index, event)
            assert (slot, string) not in starts_and_strings, (bar_index, event)
            starts_and_pitches.add((slot, midi))
            starts_and_strings.add((slot, string))
            polyphony[slot] = polyphony.get(slot, 0) + 1
        assert max(polyphony.values(), default=0) <= 6
        total += len(events)
    assert total == expected
    assert [index for index, events in enumerate(bars) if not events] == [95]
    return total


def validate_distinct_guitars(left: list, right: list) -> None:
    assert left != right
    left_onsets = {
        (bar, event[0], event[2])
        for bar, events in enumerate(left)
        for event in events
    }
    right_onsets = {
        (bar, event[0], event[2])
        for bar, events in enumerate(right)
        for event in events
    }
    intersection = left_onsets & right_onsets
    union = left_onsets | right_onsets
    assert 0.30 < len(intersection) / len(union) < 0.50
    assert sum(left[bar] != right[bar] for bar in range(96)) >= 90


def validate_synth(bars: list[list[list[int]]]) -> int:
    assert len(bars) == 96
    total = 0
    for bar_index, events in enumerate(bars):
        assert events == sorted(events, key=lambda event: (event[0], -event[2]))
        starts_and_pitches = set()
        starts: dict[int, int] = {}
        for event in events:
            assert len(event) == 3, (bar_index, event)
            slot, duration, midi = event
            assert 0 <= slot < 16 and 1 <= duration <= 16 - slot
            assert 36 <= midi <= 96
            assert (slot, midi) not in starts_and_pitches
            starts_and_pitches.add((slot, midi))
            starts[slot] = starts.get(slot, 0) + 1
        assert max(starts.values(), default=0) <= 6
        total += len(events)
    assert total == 531
    assert [index for index, events in enumerate(bars) if not events] == [
        0, 1, 2, 9, 10, 16, 18, 24, 25, 26, 27, 34, 35, 36, 37, 38,
        39, 40, 41, 42, 46, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60,
        61, 62, 63, 64, 65, 66, 67, 68, 83, 84, 92, 93, 94, 95,
    ]
    return total


def validate_bass(bars: list[list[list[int]]]) -> int:
    open_strings = (43, 38, 33, 28)
    assert len(bars) == 96
    total = 0
    for bar_index, events in enumerate(bars):
        starts = []
        for event in events:
            assert len(event) == 5, (bar_index, event)
            slot, duration, midi, string, fret = event
            assert 0 <= slot < 16 and 1 <= duration <= 16 - slot
            assert 28 <= midi <= 55
            assert 0 <= string < 4 and 0 <= fret <= 20
            assert midi == open_strings[string] + fret, (bar_index, event)
            starts.append(slot)
        assert starts == sorted(set(starts)), (bar_index, starts)
        total += len(events)
    assert total == 446
    assert [index for index, events in enumerate(bars) if not events] == [94, 95]
    return total


def validate_drums(bars: list[dict[str, list[int]]]) -> dict[str, int]:
    assert len(bars) == 96
    totals = {key: 0 for key in DRUM_KEYS}
    for bar_index, hits in enumerate(bars):
        assert set(hits) == DRUM_KEYS, (bar_index, set(hits))
        for key, slots in hits.items():
            assert slots == sorted(set(slots)), (bar_index, key, slots)
            assert all(0 <= slot < 16 for slot in slots)
            totals[key] += len(slots)
    assert totals == {"h": 580, "s": 82, "k": 122, "c": 53, "t": 0}
    assert [index for index, hits in enumerate(bars) if not any(hits.values())] == [94, 95]
    return totals


def validate_data(data: dict) -> tuple[int, int, int, int, dict[str, int]]:
    assert set(data) == {
        "meta", "sections", "chords", "guitar1", "guitar2", "synth", "bass", "drums"
    }
    meta = data["meta"]
    assert meta["bpm"] == 73
    assert meta["start"] == 2.066576
    assert meta["duration"] == 317.788299
    assert meta["grid"] == "1/16" and meta["bars"] == 96
    assert meta["preservePitch"] is True
    assert meta["silencePolicy"] == "preserve"
    assert meta["vocalTrack"] is False
    assert meta["detectedInstruments"] == [
        "guitar_left", "guitar_right", "synth", "bass", "drums"
    ]
    assert meta["excludedStems"] == ["vocals", "piano_residual"]
    assert meta["guitarTracks"] == 2
    assert meta["guitarChannelOnsetPitchJaccard"] == 0.375979
    assert meta["drumComponents"] == ["hi-hat", "snare", "kick", "cymbal"]
    assert "htdemucs_6s stem separation" in meta["method"]
    assert "per-channel Basic Pitch polyphonic note analysis" in meta["method"]
    assert "DrumScript onset and spectral classification" in meta["method"]
    assert "no generated fallback" in meta["method"]
    assert meta["sourceSha256"] == SOURCE_SHA256
    assert re.fullmatch(r"[0-9a-f]{64}", meta["sourceSha256"])

    sections = data["sections"]
    assert sum(section["length"] for section in sections) == 96
    assert len({section["key"] for section in sections}) == len(sections) == 12
    assert all(set(section) == {"key", "label", "length"} for section in sections)
    assert len(data["chords"]) == 96
    assert all(1 <= len(bar) <= 2 for bar in data["chords"])

    guitar1_total = validate_guitar(data["guitar1"], 2681)
    guitar2_total = validate_guitar(data["guitar2"], 2573)
    validate_distinct_guitars(data["guitar1"], data["guitar2"])
    synth_total = validate_synth(data["synth"])
    bass_total = validate_bass(data["bass"])
    drum_totals = validate_drums(data["drums"])
    return guitar1_total, guitar2_total, synth_total, bass_total, drum_totals


def check_javascript(source: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
        handle.write(source)
        handle.flush()
        subprocess.run(["node", "--check", handle.name], check=True)


def validate_html() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    forbidden = (
        "BASS_VOICING",
        "rhythmSlots",
        "chordNotes",
        "rhythmTrack",
        "variation=",
        "TRANSCRIPTION.vocal",
        'data-instrument="piano"',
        'data-mix="piano"',
        "— diam",
        "Diam ·",
    )
    for marker in forbidden:
        assert marker not in html, marker
    for instrument in ("guitar1", "guitar2", "synth", "bass", "drums"):
        assert html.count(f'data-instrument="{instrument}"') == 1
        assert html.count(f'data-mix="{instrument}"') == 1
    assert "TRANSCRIPTION.drums" in html
    assert "5 instrumen terdeteksi · 96 birama" in html
    assert "dua take gitar yang berbeda, keyboard/synth, bass, dan drum" in html
    assert "keduanya ditranskripsi terpisah, bukan salinan data yang sama" in html
    assert "Vokal serta stem piano yang hanya berisi residu tidak ditampilkan" in html
    assert "tidak ada pola buatan dari chord" in html
    assert "birama tanpa event tetap kosong" in html
    assert "anie-carera-hati-siapa-tak-luka-data.js?v=1" in html
    assert "cc0-sampler.js?v=guitar-library-4" in html
    assert "humanize:false" in html
    assert "sampleKeys()" in html
    assert "guitarTrack('guitar1'" in html and "guitarTrack('guitar2'" in html

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entry = next(song for song in catalog["songs"] if song["slug"] == "anie-carera-hati-siapa-tak-luka")
    card_html = json.dumps(entry, ensure_ascii=False)
    for marker in (
        "5 instrumen · 96 birama", "73 BPM", "Gitar 1", "Gitar 2",
        "Keyboard/Synth", "Bass", "Drum",
    ):
        assert marker in card_html, marker

    generator = GENERATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(generator)
    builders = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("build_")
    }
    for name in ("build_guitar", "build_synth", "build_bass", "build_drums"):
        assert not any(
            isinstance(node, ast.Name) and node.id == "CHORDS"
            for node in ast.walk(builders[name])
        ), name

    sampler = SAMPLER_PATH.read_text(encoding="utf-8")
    assert "options.humanize===false?0" in sampler
    check_javascript(DATA_PATH.read_text(encoding="utf-8"))
    check_javascript(sampler)
    inline_scripts = [
        match.group(1)
        for match in re.finditer(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html)
        if match.group(1).strip()
    ]
    assert inline_scripts
    for script in inline_scripts:
        check_javascript(script)


def main() -> None:
    guitar1, guitar2, synth, bass, drums = validate_data(load_transcription())
    validate_html()
    print(
        "Hati Siapa Tak Luka tab validated:",
        f"{guitar1} guitar-1 notes,",
        f"{guitar2} guitar-2 notes,",
        f"{synth} synth notes,",
        f"{bass} bass notes,",
        f"{sum(drums.values())} drum hits",
    )


if __name__ == "__main__":
    main()
