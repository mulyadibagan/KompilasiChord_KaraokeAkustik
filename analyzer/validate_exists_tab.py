#!/usr/bin/env python3
"""Regression checks for the Exists MP3-aligned interactive tab."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tabs" / "exists-dirantai-digelangi-rindu-data.js"
HTML_PATH = ROOT / "tabs" / "exists-dirantai-digelangi-rindu.html"
CATALOG_PATH = ROOT / "tab-catalog.json"
PREFIX = "window.KC_EXISTS_TRANSCRIPTION="
DRUM_KEYS = {"h", "s", "k", "c", "t"}


def load_transcription() -> dict:
    source = DATA_PATH.read_text(encoding="utf-8").strip()
    assert source.startswith(PREFIX) and source.endswith(";"), DATA_PATH
    return json.loads(source[len(PREFIX) : -1])


def validate_note_track(
    name: str, bars: list[list[list[int]]], *, polyphonic: bool = False
) -> int:
    assert len(bars) == 100, (name, len(bars))
    total = 0
    for bar_index, events in enumerate(bars):
        starts = []
        for event in events:
            assert len(event) == 3, (name, bar_index, event)
            slot, duration, midi = event
            assert 0 <= slot < 16, (name, bar_index, event)
            assert 1 <= duration <= 16, (name, bar_index, event)
            assert 20 <= midi <= 96, (name, bar_index, event)
            starts.append(slot)
        if not polyphonic:
            assert len(starts) == len(set(starts)), (name, bar_index, starts)
        total += len(events)
    return total


def validate_data(data: dict) -> dict[str, int]:
    assert set(data) == {"meta", "lead", "clean", "bass", "drums", "strings", "synth"}, set(data)
    meta = data["meta"]
    assert meta["bars"] == 100 and meta["grid"] == "1/16"
    assert meta["preservePitch"] is True
    assert meta["silencePolicy"] == "preserve"
    assert meta["vocalTrack"] is False
    assert "no generated fallback" in meta["method"]
    assert re.fullmatch(r"[0-9a-f]{64}", meta["sourceSha256"])
    assert meta["detectedInstruments"] == [
        "guitar_clean", "guitar_lead", "bass", "drums", "strings", "synth"
    ]
    assert "Basic Pitch per rendered karaoke stem" in meta["missingInstrumentMethod"]

    lead_total = validate_note_track("lead", data["lead"])
    clean_total = validate_note_track("clean", data["clean"], polyphonic=True)
    bass_total = validate_note_track("bass", data["bass"])
    strings_total = validate_note_track("strings", data["strings"], polyphonic=True)
    synth_total = validate_note_track("synth", data["synth"], polyphonic=True)
    drums = data["drums"]
    assert len(drums) == 100
    drum_total = 0
    for bar_index, hits in enumerate(drums):
        assert set(hits) == DRUM_KEYS, (bar_index, set(hits))
        for name, slots in hits.items():
            assert slots == sorted(set(slots)), (bar_index, name, slots)
            assert all(0 <= slot < 16 for slot in slots), (bar_index, name, slots)
            drum_total += len(slots)

    assert all(not data["bass"][bar] for bar in (0, 1, 2))
    assert all(not any(drums[bar].values()) for bar in (0, 1, 2, 98, 99))
    return {
        "lead": lead_total,
        "clean": clean_total,
        "bass": bass_total,
        "drums": drum_total,
        "strings": strings_total,
        "synth": synth_total,
    }


def validate_html() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    forbidden = (
        "BASS_PARTS",
        "RHYTHM_POWER",
        "MELODY=",
        "guitarSlots",
        "rhythmTrack",
        "usesRide",
        "isOpenHat",
        "drumVariation",
        'data-instrument="guitar"',
        'data-mix="guitar"',
        "TRANSCRIPTION.guitar",
    )
    for marker in forbidden:
        assert marker not in html, marker
    assert "Track vokal tidak disertakan" not in html
    assert "Dicocokkan ke stem MP3" not in html
    assert "Audio Karaoke HQ" not in html
    assert "Full band tanpa vokal tetap tersinkron saat berpindah tab instrumen." not in html
    for instrument in ("lead", "clean", "bass", "drums", "strings", "synth"):
        assert f'data-instrument="{instrument}"' in html
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entry = next(song for song in catalog["songs"] if song["slug"] == "exists-dirantai-digelangi-rindu")
    assert "Gitar/lead" in entry["instruments"]

    inline_scripts = [
        match.group(1)
        for match in re.finditer(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html)
        if match.group(1).strip()
    ]
    assert inline_scripts
    for script in inline_scripts:
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
            handle.write(script)
            handle.flush()
            subprocess.run(["node", "--check", handle.name], check=True)


def main() -> None:
    totals = validate_data(load_transcription())
    validate_html()
    print(
        "Exists tab validated:",
        ", ".join(f"{count} {name} events" for name, count in totals.items()),
    )


if __name__ == "__main__":
    main()
