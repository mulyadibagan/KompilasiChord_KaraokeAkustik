#!/usr/bin/env python3
"""Regression checks for the MP3-derived Kahitna "Cerita Cinta" tab."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tabs" / "kahitna-cerita-cinta-data.js"
HTML_PATH = ROOT / "tabs" / "kahitna-cerita-cinta.html"
SAMPLER_PATH = ROOT / "tabs" / "cc0-sampler.js"
CATALOG_PATH = ROOT / "tab-catalog.json"
GENERATOR_PATH = ROOT / "analyzer" / "rebuild_kahitna_cerita_cinta_tab.py"
PREFIX = "window.KC_KAHITNA_CERITA_CINTA_TRANSCRIPTION="
SOURCE_SHA256 = "7e27a19edfa84e3778ff9547a8aea44d4e5410f41ed141d0f21996ae5acb3735"
DRUM_KEYS = {"h", "s", "k", "c", "t"}


def load_transcription() -> dict:
    source = DATA_PATH.read_text(encoding="utf-8").strip()
    assert source.startswith(PREFIX) and source.endswith(";"), DATA_PATH
    return json.loads(source[len(PREFIX) : -1])


def validate_guitar(bars: list[list[list[int]]]) -> int:
    open_strings = (64, 59, 55, 50, 45, 40)
    assert len(bars) == 121
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
    assert total == 668
    assert [index for index, events in enumerate(bars) if not events] == [
        8, 9, 81, 86, 87, 88, 89, 118, 119, 120,
    ]
    return total


def validate_bass(bars: list[list[list[int]]]) -> int:
    open_strings = (43, 38, 33, 28)
    assert len(bars) == 121
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
    assert total == 348
    silent = [index for index, events in enumerate(bars) if not events]
    assert silent == [0, 1, 2, 3, 11, 42, 120]
    return total


def validate_drums(bars: list[dict[str, list[int]]]) -> dict[str, int]:
    assert len(bars) == 121
    totals = {key: 0 for key in DRUM_KEYS}
    for bar_index, hits in enumerate(bars):
        assert set(hits) == DRUM_KEYS, (bar_index, set(hits))
        for key, slots in hits.items():
            assert slots == sorted(set(slots)), (bar_index, key, slots)
            assert all(0 <= slot < 16 for slot in slots)
            totals[key] += len(slots)
    assert totals == {"h": 1058, "s": 202, "k": 190, "c": 21, "t": 0}
    silent = [index for index, hits in enumerate(bars) if not any(hits.values())]
    assert silent == []
    return totals


def validate_data(data: dict) -> tuple[int, int, dict[str, int]]:
    assert set(data) == {"meta", "sections", "chords", "guitar", "bass", "drums"}
    meta = data["meta"]
    assert meta["bpm"] == 113.238888
    assert meta["start"] == 8.218379
    assert meta["duration"] == 264.568163
    assert meta["grid"] == "1/16" and meta["bars"] == 121
    assert meta["preservePitch"] is True
    assert meta["silencePolicy"] == "preserve"
    assert meta["vocalTrack"] is False
    assert meta["detectedInstruments"] == ["guitar_electric", "bass", "drums"]
    assert meta["excludedStems"] == ["vocals", "piano_residual", "other_residual"]
    assert meta["guitarTracks"] == 1
    assert meta["mixStereoCorrelation"] == 0.998701
    assert meta["guitarStereoCorrelation"] == 0.999287
    assert meta["pianoResidualRmsDb"] == -94.76
    assert meta["otherResidualRmsDb"] == -89.43
    assert meta["drumComponents"] == ["hi-hat", "snare", "kick", "cymbal"]
    assert "htdemucs_6s stem separation" in meta["method"]
    assert "Basic Pitch polyphonic note analysis" in meta["method"]
    assert "DrumScript onset and spectral classification" in meta["method"]
    assert "no generated fallback" in meta["method"]
    assert meta["sourceSha256"] == SOURCE_SHA256
    assert re.fullmatch(r"[0-9a-f]{64}", meta["sourceSha256"])

    sections = data["sections"]
    assert sum(section["length"] for section in sections) == 121
    assert len({section["key"] for section in sections}) == len(sections) == 14
    assert all(set(section) == {"key", "label", "length"} for section in sections)
    assert len(data["chords"]) == 121
    assert all(1 <= len(bar) <= 2 for bar in data["chords"])

    guitar_total = validate_guitar(data["guitar"])
    bass_total = validate_bass(data["bass"])
    drum_totals = validate_drums(data["drums"])
    return guitar_total, bass_total, drum_totals


def check_javascript(source: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
        handle.write(source)
        handle.flush()
        subprocess.run(["node", "--check", handle.name], check=True)


def validate_html() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    forbidden = (
        "BASS_VOICING",
        "var GUITAR=",
        "var MELODY=",
        "rhythmSlots",
        "chordNotes",
        "rhythmTrack",
        "electricGuitarTone",
        "variation=",
        "KCHarmony",
        "TRANSCRIPTION.lead",
        "TRANSCRIPTION.vocal",
        "TRANSCRIPTION.piano",
        'data-instrument="melody"',
        'data-instrument="piano"',
        'data-mix="piano"',
        'data-instrument="guitar2"',
        'data-mix="guitar2"',
        "— diam",
        "Diam ·",
    )
    for marker in forbidden:
        assert marker not in html, marker
    assert html.count('data-instrument="guitar"') == 1
    for instrument in ("guitar", "bass", "drums"):
        assert html.count(f'data-instrument="{instrument}"') == 1
        assert html.count(f'data-mix="{instrument}"') == 1
    for instrument in ("guitar", "bass"):
        assert f"decodedEvents('{instrument}'" in html
    assert "TRANSCRIPTION.drums" in html
    assert "3 instrumen terdeteksi · 121 birama" in html
    assert "satu gitar elektrik, bass, dan drum" in html
    assert "satu jalur gitar" in html
    assert "tidak diduplikasi menjadi “Gitar 2”" in html
    assert "stem piano dan other hanya berisi residu" in html
    assert "tidak ada pola buatan dari chord" in html
    assert "birama tanpa event tetap kosong" in html
    assert "kahitna-cerita-cinta-data.js?v=1" in html
    assert "cc0-sampler.js?v=band-mix-5" in html
    assert "humanize:false" in html

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entry = next(song for song in catalog["songs"] if song["slug"] == "kahitna-cerita-cinta")
    card_html = json.dumps(entry, ensure_ascii=False)
    for marker in ("3 instrumen · 121 birama", "113,24 BPM", "Gitar elektrik", "Bass", "Drum"):
        assert marker in card_html, marker

    generator = GENERATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(generator)
    builders = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("build_")
    }
    for name in ("build_guitar", "build_bass", "build_drums"):
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
    guitar, bass, drums = validate_data(load_transcription())
    validate_html()
    print(
        "Cerita Cinta tab validated:",
        f"{guitar} guitar notes,",
        f"{bass} bass notes,",
        f"{sum(drums.values())} drum hits",
    )


if __name__ == "__main__":
    main()
