#!/usr/bin/env python3
"""Build a KompilasiChord tab player from a binary GP3/GP4/GP5 file."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import guitarpro

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tab-catalog.json"
PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def slugify(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", plain))


def youtube_id(value: str) -> str:
    match = re.search(r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?.*?v=|embed/|shorts/))([\w-]{11})", value)
    if not match:
        raise ValueError("URL YouTube tidak valid atau ID video bukan 11 karakter")
    return match.group(1)


def string_name(midi: int) -> str:
    octave = midi // 12 - 1
    return f"{PITCHES[midi % 12]}{octave}"


def safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def duration_ticks(beat) -> int:
    duration = getattr(beat, "duration", None)
    time = getattr(duration, "time", None)
    return max(1, safe_int(time, 240))


def measure_events(measure) -> list[dict]:
    events = []
    header = measure.header
    start = safe_int(getattr(header, "start", 0))
    length = max(1, safe_int(getattr(header, "length", 3840), 3840))
    for voice in measure.voices:
        for beat in voice.beats:
            if getattr(beat, "status", None) and str(beat.status).lower().endswith("empty"):
                continue
            relative = safe_int(getattr(beat, "start", start)) - start
            slot = max(0, min(15, round(relative / length * 16)))
            slots = max(1, min(16 - slot, round(duration_ticks(beat) / length * 16)))
            for note in beat.notes:
                events.append({
                    "slot": slot,
                    "duration": slots,
                    "string": max(0, safe_int(note.string, 1) - 1),
                    "fret": safe_int(note.value),
                    "velocity": safe_int(getattr(note, "velocity", 95), 95),
                    "tie": bool(getattr(getattr(note, "type", None), "name", "").lower() == "tie"),
                })
    return events


def extract(song) -> dict:
    headers = song.measureHeaders
    tracks = []
    for index, track in enumerate(song.tracks):
        strings = sorted(track.strings, key=lambda item: item.number)
        measures = []
        for measure_index, measure in enumerate(track.measures):
            marker = getattr(measure.header, "marker", None)
            section = (getattr(marker, "title", "") or "").strip()
            measures.append({
                "number": measure_index + 1,
                "section": section,
                "events": measure_events(measure),
            })
        tracks.append({
            "id": f"track-{index + 1}",
            "name": (track.name or f"Track {index + 1}").strip(),
            "program": safe_int(getattr(track.channel, "instrument", 0)),
            "percussion": bool(track.isPercussionTrack),
            "strings": [{"number": item.number, "midi": item.value, "name": string_name(item.value)} for item in strings],
            "measures": measures,
        })
    return {
        "tempo": safe_int(getattr(song, "tempo", 120), 120),
        "measureCount": len(headers),
        "tracks": tracks,
    }


def page_html(meta: dict) -> str:
    title = meta["title"].replace("&", "&amp;").replace("<", "&lt;")
    artist = meta["artist"].replace("&", "&amp;").replace("<", "&lt;")
    slug = meta["slug"]
    return f'''<!doctype html>
<html lang="id"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Tab Musik {artist} — {title}, dibuat otomatis dari Guitar Pro.">
<title>Tab Musik — {artist} · {title}</title>
<link rel="stylesheet" href="../tab-navigation.css?v=20260821-deeplink2">
<link rel="stylesheet" href="songsterr-score.css?v=20260821-3">
<link rel="stylesheet" href="generated-tab-player.css?v=1">
</head><body class="kc-player-page">
<header class="topbar"></header>
<main class="wrap"><section class="card">
<div class="songline"><div><h1>{title}</h1><p>{artist} · <span id="song-meta">Memuat Guitar Pro…</span></p></div></div>
<div class="playerbar"><div class="transport"><button id="rewind">↶ Awal</button><button class="play" id="play">▶ Putar</button><button id="stop">■ Stop</button></div><div class="control-center"><label class="seek">Posisi <input id="seek" type="range" value="0"><span id="position-time">Birama 1</span></label></div><label class="switch"><input id="loop" type="checkbox"> Ulang</label></div>
<div class="workspace"><aside class="sidebar"><p class="side-title">Instrumen</p><div class="instrument-tabs" id="instrument-tabs"></div></aside>
<section class="score-area"><div class="score"><div class="score-head"><div><strong id="score-title">Tab</strong><span id="tuning"></span></div><span class="position" id="position">Birama 1</span></div><div class="bars" id="bars"></div><div class="info"><p id="status">Siap.</p><p class="source">Video referensi: <a href="https://www.youtube.com/watch?v={meta['youtubeId']}" target="_blank" rel="noopener">YouTube</a></p><iframe class="youtube-reference" src="https://www.youtube-nocookie.com/embed/{meta['youtubeId']}" title="Video referensi {title}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe></div></div></section></div>
</section></main>
<script src="{slug}-data.js?v=1"></script><script src="generated-tab-player.js?v=1"></script>
<script src="../tab-navigation.js?v=20260821-deeplink2" data-base=".."></script>
</body></html>'''


def update_catalog(entry: dict) -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    songs = catalog.setdefault("songs", [])
    songs[:] = [song for song in songs if song.get("slug") != entry["slug"]]
    songs.append(entry)
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def github_output(values: dict) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gp5", required=True)
    parser.add_argument("--youtube", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--artist", default="")
    parser.add_argument("--slug", default="")
    args = parser.parse_args()

    source = (ROOT / args.gp5).resolve() if not Path(args.gp5).is_absolute() else Path(args.gp5)
    try:
        source.relative_to((ROOT / "input").resolve())
    except ValueError:
        raise SystemExit("File sumber harus berada di folder input/")
    if not source.is_file() or source.suffix.lower() not in {".gp3", ".gp4", ".gp5"}:
        raise SystemExit("File sumber harus berupa .gp3, .gp4, atau .gp5 yang tersedia di repository")
    if zipfile.is_zipfile(source):
        raise SystemExit("File adalah arsip GP7/GPX, bukan GP5 biner. Ekspor ulang melalui Guitar Pro sebagai GP5.")

    song = guitarpro.parse(str(source))
    title = (args.title or getattr(song, "title", "") or source.stem).strip()
    artist = (args.artist or getattr(song, "artist", "") or "Artis belum diisi").strip()
    slug = slugify(args.slug or f"{artist}-{title}")
    if not slug:
        raise SystemExit("Slug tidak valid")
    video_id = youtube_id(args.youtube)
    data = extract(song)
    if not data["tracks"]:
        raise SystemExit("GP5 tidak berisi track")

    meta = {"slug": slug, "title": title, "artist": artist, "youtubeId": video_id}
    data.update(meta)
    data_path = ROOT / "tabs" / f"{slug}-data.js"
    page_path = ROOT / "tabs" / f"{slug}.html"
    data_path.write_text("window.KC_TAB_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    page_path.write_text(page_html(meta), encoding="utf-8")

    instruments = [track["name"] for track in data["tracks"]]
    entry = {
        "slug": slug, "path": f"tabs/{slug}.html", "title": title, "artist": artist,
        "status": f"{len(instruments)} instrumen · {data['measureCount']} birama",
        "bars": data["measureCount"], "key": "GP5", "bpmLabel": f"{data['tempo']} BPM",
        "instruments": instruments, "searchTerms": ["guitar pro", "otomatis"],
    }
    update_catalog(entry)
    github_output({"slug": slug, "page": page_path.relative_to(ROOT).as_posix(), "data": data_path.relative_to(ROOT).as_posix()})
    print(f"Generated {page_path.relative_to(ROOT)} with {len(instruments)} tracks and {data['measureCount']} measures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
