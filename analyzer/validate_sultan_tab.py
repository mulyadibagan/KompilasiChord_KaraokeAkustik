#!/usr/bin/env python3
"""Regression checks for the Sultan MP3-aligned interactive tab."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tabs" / "sultan-transcription-data.js"
HTML_PATH = ROOT / "tabs" / "sultan-terpaksa-aku-lakukan.html"
CATALOG_PATH = ROOT / "tab-musik.html"
PREFIX = "window.KC_SULTAN_TRANSCRIPTION="
DRUM_KEYS = {"h", "s", "k", "c", "t"}
SOURCE_SHA256 = "6f4b416bdfef0fe4c16b42834a6006e56aace655501133f5cf63305a3f380ae7"


def load_transcription() -> dict:
    source = DATA_PATH.read_text(encoding="utf-8").strip()
    assert source.startswith(PREFIX) and source.endswith(";"), DATA_PATH
    return json.loads(source[len(PREFIX) : -1])


def validate_note_track(
    name: str,
    bars: list[list[list[int]]],
    midi_range: tuple[int, int],
) -> int:
    assert len(bars) == 158, (name, len(bars))
    total = 0
    for bar_index, events in enumerate(bars):
        starts = []
        for event in events:
            assert len(event) == 3, (name, bar_index, event)
            slot, duration, midi = event
            assert 0 <= slot < 16, (name, bar_index, event)
            assert 1 <= duration <= 16 - slot, (name, bar_index, event)
            assert midi_range[0] <= midi <= midi_range[1], (name, bar_index, event)
            starts.append(slot)
        assert starts == sorted(set(starts)), (name, bar_index, starts)
        total += len(events)
    return total


def validate_data(data: dict) -> tuple[int, int, dict[str, int]]:
    assert set(data) == {"meta", "sections", "chords", "lead", "bass", "drums"}
    meta = data["meta"]
    assert meta["bpm"] == 125
    assert meta["start"] == 1.590567
    assert meta["duration"] == 304.436825
    assert meta["grid"] == "1/16" and meta["bars"] == 158
    assert meta["preservePitch"] is True
    assert meta["silencePolicy"] == "preserve"
    assert meta["vocalTrack"] is False
    assert "htdemucs_6s" in meta["method"]
    assert "beat-warped pitch/onset analysis" in meta["method"]
    assert "no generated fallback" in meta["method"]
    assert meta["sourceSha256"] == SOURCE_SHA256
    assert re.fullmatch(r"[0-9a-f]{64}", meta["sourceSha256"])

    sections = data["sections"]
    assert sum(section["length"] for section in sections) == 158
    assert len({section["key"] for section in sections}) == len(sections)
    assert all(set(section) == {"key", "label", "length"} for section in sections)

    chords = data["chords"]
    assert len(chords) == 158
    assert all(1 <= len(bar) <= 2 and all(isinstance(chord, str) for chord in bar) for bar in chords)

    lead_total = validate_note_track("lead", data["lead"], (52, 76))
    bass_total = validate_note_track("bass", data["bass"], (29, 50))
    assert lead_total == 493
    assert bass_total == 258

    drums = data["drums"]
    assert len(drums) == 158
    drum_totals = {key: 0 for key in DRUM_KEYS}
    for bar_index, hits in enumerate(drums):
        assert set(hits) == DRUM_KEYS, (bar_index, set(hits))
        for name, slots in hits.items():
            assert slots == sorted(set(slots)), (bar_index, name, slots)
            assert all(0 <= slot < 16 for slot in slots), (bar_index, name, slots)
            drum_totals[name] += len(slots)
    assert drum_totals == {"h": 634, "s": 141, "k": 328, "c": 12, "t": 42}
    assert all(not any(drums[bar].values()) for bar in (152, 153, 154, 156, 157))
    return lead_total, bass_total, drum_totals


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
        "guitarTab",
        "rhythmTrack",
        "electricGuitarTone",
        "variation=",
        "vibrato:vibrato",
        "state.enabled.guitar",
        'data-instrument="guitar"',
        'data-mix="guitar"',
        "TRANSCRIPTION.guitar",
        "— diam",
        "Diam ·",
    )
    for marker in forbidden:
        assert marker not in html, marker
    assert "Dicocokkan ke stem MP3 · tanpa pola buatan" in html
    assert "birama tanpa event dibiarkan kosong" in html
    assert "Track vokal tidak disertakan" in html
    assert "sultan-transcription-data.js?v=2" in html

    catalog = CATALOG_PATH.read_text(encoding="utf-8")
    card = re.search(
        r'<a class="song" href="tabs/sultan-terpaksa-aku-lakukan\.html\?embed=1"[\s\S]*?</a>',
        catalog,
    )
    assert card
    assert "Lagu lengkap · 158 birama" in card.group(0)
    assert "Gitar/lead" in card.group(0)

    check_javascript(DATA_PATH.read_text(encoding="utf-8"))
    inline_scripts = [
        match.group(1)
        for match in re.finditer(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html)
        if match.group(1).strip()
    ]
    assert inline_scripts
    for script in inline_scripts:
        check_javascript(script)


def main() -> None:
    lead_total, bass_total, drum_totals = validate_data(load_transcription())
    validate_html()
    print(
        "Sultan tab validated:",
        f"{lead_total} lead events,",
        f"{bass_total} bass events,",
        f"{sum(drum_totals.values())} drum hits",
    )


if __name__ == "__main__":
    main()
