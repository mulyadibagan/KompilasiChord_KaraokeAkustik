#!/usr/bin/env python3
"""Validate the isolated Exists Karaoke HQ preview and its six stems."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio" / "exists-hq-preview"
PAGE = ROOT / "tabs" / "exists-karaoke-hq-preview.html"
STEMS = ["guitar-clean", "guitar-lead", "bass", "drums", "strings", "synth"]


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return float(result.stdout.strip())


manifest = json.loads((AUDIO / "manifest.json").read_text(encoding="utf-8"))
assert manifest["vocal"] is False
assert manifest["stems"] == STEMS
assert abs(float(manifest["duration"]) - 75.0) < 0.01

for name in STEMS + ["full-band-preview"]:
    path = AUDIO / f"{name}.mp3"
    assert path.stat().st_size > 1_000_000, (name, path.stat().st_size)
    if shutil.which("ffprobe"):
        assert abs(duration(path) - 75.05) < 0.12, (name, duration(path))

html = PAGE.read_text(encoding="utf-8")
assert "Karaoke Full Band HQ" in html
assert "tanpa vokal" in html.lower()
for name in STEMS:
    assert f"{name}.mp3" in html

scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.S | re.I)
inline = "\n".join(script for script in scripts if script.strip())
with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
    handle.write(inline)
    handle.flush()
    subprocess.run(["node", "--check", handle.name], check=True)

print("Exists Karaoke HQ preview: 6 synchronized stems, 75.05s, no vocal, JS valid")
