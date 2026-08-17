#!/usr/bin/env python3
"""Regression checks for the Exists YouTube-synchronized interactive tab."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "tabs" / "exists-dirantai-digelangi-rindu-data.js"
HTML_PATH = ROOT / "tabs" / "exists-dirantai-digelangi-rindu.html"
PREFIX = "window.KC_EXISTS_TRANSCRIPTION="
NOTE_TRACKS = ("lead", "bass", "clean", "strings", "synth")
DRUM_KEYS = {"h", "s", "k", "c", "t"}


def load_transcription() -> dict:
    source = DATA_PATH.read_text(encoding="utf-8").strip()
    assert source.startswith(PREFIX) and source.endswith(";"), DATA_PATH
    return json.loads(source[len(PREFIX) : -1])


def validate_note_track(name: str, bars: list[list[list[int]]]) -> None:
    assert len(bars) == 100, (name, len(bars))
    for bar_index, events in enumerate(bars):
        for event in events:
            assert len(event) == 3, (name, bar_index, event)
            slot, duration, midi = event
            assert 0 <= slot < 16, (name, bar_index, event)
            assert 1 <= duration <= 16, (name, bar_index, event)
            assert 0 <= midi <= 127, (name, bar_index, event)


def validate_drums(bars: list[dict[str, list[int]]]) -> None:
    assert len(bars) == 100, len(bars)
    for bar_index, hits in enumerate(bars):
        assert set(hits) == DRUM_KEYS, (bar_index, hits.keys())
        for slots in hits.values():
            assert all(isinstance(slot, int) and 0 <= slot < 16 for slot in slots)


def validate_page() -> None:
    page = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-mode="youtube"' in page
    assert "dcEyID3okrM" in page
    assert "youtube.com/watch?v=dcEyID3okrM" in page
    assert "youtube.com/iframe_api" in page
    assert "new YT.Player" in page
    assert "window.self!==window.top" in page
    assert "mobile-focus" in page
    assert "current-note" not in page
    assert ".mp3" not in page.lower()
    assert "r2.dev" not in page.lower()
    assert "karaoke" not in page.lower()
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", page)
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
        assert result.returncode == 0, f"inline script {index}: {result.stderr}"


def main() -> None:
    transcription = load_transcription()
    for name in NOTE_TRACKS:
        validate_note_track(name, transcription[name])
    validate_drums(transcription["drums"])
    validate_page()
    print("Validated Exists official-YouTube player and 100-bar transcription")


if __name__ == "__main__":
    main()
