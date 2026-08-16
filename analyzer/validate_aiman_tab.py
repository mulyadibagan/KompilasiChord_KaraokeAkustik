#!/usr/bin/env python3
"""Regression checks for the Aiman MP3-derived multi-instrument tab."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tabs" / "aiman-transcription-data.js"
HTML_PATH = ROOT / "tabs" / "aiman-tino-berakhirlah-sudah.html"
SAMPLER_PATH = ROOT / "tabs" / "cc0-sampler.js"
CATALOG_PATH = ROOT / "tab-catalog.json"
PREFIX = "window.KC_AIMAN_TRANSCRIPTION="
SOURCE_SHA256 = "521615370a3ee79b42f1b649c4abb9fe84204f93b54362b20fa020bcebf546e6"
DRUM_KEYS = {"h", "s", "k", "c", "t"}


def load_transcription() -> dict:
    source = DATA_PATH.read_text(encoding="utf-8").strip()
    assert source.startswith(PREFIX) and source.endswith(";"), DATA_PATH
    return json.loads(source[len(PREFIX) : -1])


def validate_guitar(bars: list[list[list[int]]]) -> int:
    open_strings = (64, 59, 55, 50, 45, 40)
    assert len(bars) == 66
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
    assert total == 1531
    assert all(bars), "The detected guitar remains active through the final bar"
    return total


def validate_piano(bars: list[list[list[int]]]) -> int:
    assert len(bars) == 66
    total = 0
    for bar_index, events in enumerate(bars):
        assert events == sorted(events, key=lambda event: (event[0], -event[2]))
        starts_and_pitches = set()
        starts: dict[int, int] = {}
        for event in events:
            assert len(event) == 3, (bar_index, event)
            slot, duration, midi = event
            assert 0 <= slot < 16 and 1 <= duration <= 16 - slot
            assert 33 <= midi <= 84
            assert (slot, midi) not in starts_and_pitches
            starts_and_pitches.add((slot, midi))
            starts[slot] = starts.get(slot, 0) + 1
        assert max(starts.values(), default=0) <= 6
        total += len(events)
    assert total == 526
    silent = [index for index, events in enumerate(bars) if not events]
    assert silent == [21, 24, 25, 26, 27, 28, 29, 30, 31, 32, 43, 44, 51, 61, 65]
    return total


def validate_bass(bars: list[list[list[int]]]) -> int:
    open_strings = (43, 38, 33, 28)
    assert len(bars) == 66
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
    assert total == 431
    silent = [index for index, events in enumerate(bars) if not events]
    assert silent == [5, 6, 7, 8, 9, 10, 65]
    return total


def validate_drums(bars: list[dict[str, list[int]]]) -> dict[str, int]:
    assert len(bars) == 66
    totals = {key: 0 for key in DRUM_KEYS}
    for bar_index, hits in enumerate(bars):
        assert set(hits) == DRUM_KEYS, (bar_index, set(hits))
        for key, slots in hits.items():
            assert slots == sorted(set(slots)), (bar_index, key, slots)
            assert all(0 <= slot < 16 for slot in slots)
            totals[key] += len(slots)
    assert totals == {"h": 305, "s": 119, "k": 249, "c": 1, "t": 0}
    silent = [index for index, hits in enumerate(bars) if not any(hits.values())]
    assert silent == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 55, 56, 57]
    return totals


def validate_data(data: dict) -> tuple[int, int, int, dict[str, int]]:
    assert set(data) == {"meta", "sections", "chords", "guitar", "piano", "bass", "drums"}
    meta = data["meta"]
    assert meta["bpm"] == 73
    assert meta["start"] == 3.482993
    assert meta["duration"] == 220.914649
    assert meta["grid"] == "1/16" and meta["bars"] == 66
    assert meta["preservePitch"] is True
    assert meta["silencePolicy"] == "preserve"
    assert meta["vocalTrack"] is False
    assert meta["detectedInstruments"] == ["guitar", "piano", "bass", "drums"]
    assert meta["guitarTracks"] == 1
    assert meta["drumComponents"] == ["hi-hat", "snare", "kick", "cymbal"]
    assert "htdemucs_6s stem separation" in meta["method"]
    assert "Basic Pitch polyphonic note analysis" in meta["method"]
    assert "DrumScript onset classification" in meta["method"]
    assert "no generated fallback" in meta["method"]
    assert meta["sourceSha256"] == SOURCE_SHA256
    assert re.fullmatch(r"[0-9a-f]{64}", meta["sourceSha256"])

    sections = data["sections"]
    assert sum(section["length"] for section in sections) == 66
    assert len({section["key"] for section in sections}) == len(sections)
    assert all(set(section) == {"key", "label", "length"} for section in sections)
    assert len(data["chords"]) == 66
    assert all(1 <= len(bar) <= 2 for bar in data["chords"])

    guitar_total = validate_guitar(data["guitar"])
    piano_total = validate_piano(data["piano"])
    bass_total = validate_bass(data["bass"])
    drum_totals = validate_drums(data["drums"])
    return guitar_total, piano_total, bass_total, drum_totals


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
        "TRANSCRIPTION.lead",
        "TRANSCRIPTION.vocal",
        'data-instrument="melody"',
        'data-instrument="guitar2"',
        'data-mix="guitar2"',
        "— diam",
        "Diam ·",
    )
    for marker in forbidden:
        assert marker not in html, marker
    assert html.count('data-instrument="guitar"') == 1
    for instrument in ("guitar", "piano", "bass", "drums"):
        assert f'data-instrument="{instrument}"' in html
        assert f'data-mix="{instrument}"' in html
    for instrument in ("guitar", "piano", "bass"):
        assert f"decodedEvents('{instrument}'" in html
    assert "TRANSCRIPTION.drums" in html
    assert "4 instrumen terdeteksi · 66 birama" in html
    assert "satu gitar, piano/keyboard, bass, dan drum" in html
    assert "tidak diduplikasi menjadi “Gitar 2”" in html
    assert "Vokal dan stem residual tidak ditampilkan" in html
    assert "tidak ada pola buatan dari chord" in html
    assert "birama tanpa event tetap kosong" in html
    assert "aiman-transcription-data.js?v=2" in html
    assert "cc0-sampler.js?v=guitarpro-1" in html
    assert "harmony-engine.js?v=guitarpro-1" in html
    assert "{force:true,kinds:['bass'],mode:'anchor'}" in html
    assert "humanize:false" in html

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entry = next(song for song in catalog["songs"] if song["slug"] == "aiman-tino-berakhirlah-sudah")
    card_html = json.dumps(entry, ensure_ascii=False)
    for marker in ("4 instrumen · 66 birama", "73 BPM", "Gitar", "Piano/keyboard", "Bass", "Drum"):
        assert marker in card_html, marker

    sampler = SAMPLER_PATH.read_text(encoding="utf-8")
    assert "options.humanize === false ? 0" in sampler
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
    guitar, piano, bass, drums = validate_data(load_transcription())
    validate_html()
    print(
        "Aiman tab validated:",
        f"{guitar} guitar notes,",
        f"{piano} piano notes,",
        f"{bass} bass notes,",
        f"{sum(drums.values())} drum hits",
    )


if __name__ == "__main__":
    main()
