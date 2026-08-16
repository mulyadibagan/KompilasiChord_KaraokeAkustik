#!/usr/bin/env python3
"""Validate the complete Exists karaoke render and its Tab Musik integration."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio" / "exists-karaoke-hq"
PAGE = ROOT / "tabs" / "exists-dirantai-digelangi-rindu.html"
STEMS = ["guitar-clean", "guitar-lead", "bass", "drums", "strings", "synth"]
BPM = 89.84
BARS = 100
EXPECTED_DURATION = BARS * 4 * 60 / BPM


def probe(path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(result.stdout)


manifest = json.loads((AUDIO / "manifest.json").read_text(encoding="utf-8"))
assert manifest["kind"] == "full"
assert manifest["vocal"] is False
assert manifest["stems"] == STEMS
assert abs(float(manifest["bpm"]) - BPM) < 0.001
assert abs(float(manifest["duration"]) - EXPECTED_DURATION) < 0.08
assert manifest["bars"] == BARS
assert manifest["meter"] == "4/4"
assert manifest["sampleRate"] == 44_100
assert manifest["channels"] == 2
assert manifest["fallback"] == "full-band.mp3"
assert manifest["renderVersion"] == "exists-full-1"

for name in STEMS + ["full-band"]:
    path = AUDIO / f"{name}.mp3"
    assert path.stat().st_size > 5_000_000, (name, path.stat().st_size)
    if shutil.which("ffprobe"):
        metadata = probe(path)
        stream = metadata["streams"][0]
        assert stream["codec_name"] == "mp3", (name, stream)
        assert int(stream["sample_rate"]) == 44_100, (name, stream)
        assert int(stream["channels"]) == 2, (name, stream)
        assert abs(float(metadata["format"]["duration"]) - 267.18) < 0.12, (name, metadata)

html = PAGE.read_text(encoding="utf-8")
for required in (
    "Karaoke Full Band HQ · tanpa vokal",
    "var KARAOKE_BPM=89.84",
    "mode:'karaoke'",
    "setMode('karaoke',true)",
    "https://pub-f24c157419c64a00886e77e672bff365.r2.dev/exists/dirantai-digelangi-rindu/",
    "media.crossOrigin='anonymous'",
    "Promise.all(attempts)",
    "syncKaraoke(false)",
    "full-band.mp3?v=exists-full-1",
    "mode kompatibilitas",
    "catch(ignoreWebAudio){state.karaoke.failed=true;}",
    "state.karaoke.fallback.volume=state.karaoke.fallbackMode ? .92 : 0",
):
    assert required in html, required
for name in STEMS:
    assert f"{name}.mp3?v=exists-full-1" in html, name

scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.S | re.I)
inline = "\n".join(script for script in scripts if script.strip())
with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
    handle.write(inline)
    handle.flush()
    subprocess.run(["node", "--check", handle.name], check=True)

print("Exists Karaoke HQ: 6 synchronized full stems, 267.18s, no vocal, Tab Musik JS valid")
