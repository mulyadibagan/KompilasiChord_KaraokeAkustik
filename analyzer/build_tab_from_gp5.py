#!/usr/bin/env python3
"""Build a KompilasiChord tab player from GP3/GP4/GP5 or modern GP7/GP8."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
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
    timeline = []
    elapsed = 0.0
    base_tempo = max(30, safe_int(getattr(song, "tempo", 120), 120))
    for header in headers:
        signature = getattr(header, "timeSignature", None)
        numerator = max(1, safe_int(getattr(signature, "numerator", 4), 4))
        denominator = max(1, safe_int(getattr(getattr(signature, "denominator", None), "value", 4), 4))
        quarter_beats = numerator * 4 / denominator
        duration = quarter_beats * 60 / base_tempo
        timeline.append({"start": round(elapsed, 6), "duration": round(duration, 6), "tempo": base_tempo, "timeSignature": f"{numerator}/{denominator}"})
        elapsed += duration
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
        "tempo": base_tempo,
        "measureCount": len(headers),
        "timeline": timeline,
        "scoreDuration": round(elapsed, 6),
        "tracks": tracks,
    }


RHYTHM_QUARTERS = {
    "Longa": 16.0, "DoubleWhole": 8.0, "Whole": 4.0, "Half": 2.0,
    "Quarter": 1.0, "Eighth": 0.5, "16th": 0.25, "32nd": 0.125,
    "64th": 0.0625, "128th": 0.03125,
}


def gpif_text(node, path: str, default="") -> str:
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None else default


def gpif_refs(node, path: str) -> list[int]:
    return [safe_int(value, -1) for value in gpif_text(node, path).split() if safe_int(value, -1) >= 0]


def gpif_rhythm_quarters(rhythm) -> float:
    base_value = RHYTHM_QUARTERS.get(gpif_text(rhythm, "NoteValue"), 1.0)
    value = base_value
    dot = rhythm.find("AugmentationDot")
    dots = safe_int(dot.get("count"), 0) if dot is not None else 0
    addition = 0.5
    for _ in range(dots):
        value += base_value * addition
        addition *= 0.5
    tuplet = rhythm.find("PrimaryTuplet")
    if tuplet is not None:
        numerator = safe_int(tuplet.get("num") or gpif_text(tuplet, "Num"), 1)
        denominator = safe_int(tuplet.get("den") or gpif_text(tuplet, "Den"), 1)
        if numerator > 0:
            value *= denominator / numerator
    return max(value, 1 / 128)


def gpif_property(node, name: str, child: str, default="") -> str:
    if node is None:
        return default
    prop = node.find(f"./Properties/Property[@name='{name}']/{child}")
    return (prop.text or "").strip() if prop is not None else default


def extract_gpif(source: Path) -> tuple[dict, str, str, str]:
    with zipfile.ZipFile(source) as archive:
        try:
            score_info = archive.getinfo("Content/score.gpif")
            if score_info.file_size > 20 * 1024 * 1024:
                raise SystemExit("Data score.gpif terlalu besar (maksimal 20 MB)")
            root = ET.fromstring(archive.read(score_info))
        except KeyError as exc:
            raise SystemExit("Arsip .gp tidak memiliki Content/score.gpif") from exc

    score = root.find("Score")
    title = gpif_text(score, "Title", source.stem)
    artist = gpif_text(score, "Artist", "Artis belum diisi")
    version = gpif_text(root, "GPVersion", "GP7/GP8")
    tempo = 120
    for automation in root.findall("./MasterTrack/Automations/Automation"):
        if gpif_text(automation, "Type") == "Tempo":
            tempo = safe_int(gpif_text(automation, "Value").split()[0], 120)
            break

    tracks_by_id = {safe_int(node.get("id"), -1): node for node in root.findall("./Tracks/Track")}
    bars_by_id = {safe_int(node.get("id"), -1): node for node in root.findall("./Bars/Bar")}
    voices_by_id = {safe_int(node.get("id"), -1): node for node in root.findall("./Voices/Voice")}
    beats_by_id = {safe_int(node.get("id"), -1): node for node in root.findall("./Beats/Beat")}
    notes_by_id = {safe_int(node.get("id"), -1): node for node in root.findall("./Notes/Note")}
    rhythms_by_id = {safe_int(node.get("id"), -1): node for node in root.findall("./Rhythms/Rhythm")}
    master_bars = root.findall("./MasterBars/MasterBar")
    tempo_changes = {0: tempo}
    for automation in root.findall("./MasterTrack/Automations/Automation"):
        if gpif_text(automation, "Type") == "Tempo":
            tempo_changes[max(0, safe_int(gpif_text(automation, "Bar"), 0))] = max(30, safe_int(gpif_text(automation, "Value").split()[0], tempo))
    timeline = []
    elapsed = 0.0
    active_tempo = tempo
    for measure_index, master_bar in enumerate(master_bars):
        active_tempo = tempo_changes.get(measure_index, active_tempo)
        numerator, _, denominator = gpif_text(master_bar, "Time", "4/4").partition("/")
        numerator_value = max(1, safe_int(numerator, 4))
        denominator_value = max(1, safe_int(denominator, 4))
        quarter_beats = numerator_value * 4 / denominator_value
        duration = quarter_beats * 60 / active_tempo
        timeline.append({"start": round(elapsed, 6), "duration": round(duration, 6), "tempo": active_tempo, "timeSignature": f"{numerator_value}/{denominator_value}"})
        elapsed += duration
    master_track_ids = gpif_refs(root.find("MasterTrack"), "Tracks") or sorted(tracks_by_id)

    tracks = []
    for track_position, track_id in enumerate(master_track_ids):
        track_node = tracks_by_id.get(track_id)
        if track_node is None:
            continue
        name = gpif_text(track_node, "Name", f"Track {track_position + 1}")
        kind = gpif_text(track_node, "InstrumentSet/Type").lower()
        percussion = "drum" in kind or "percussion" in kind
        program = safe_int(gpif_text(track_node, "Sounds/Sound/MIDI/Program"), 0)
        pitches = [safe_int(value) for value in gpif_property(track_node.find("Staves/Staff"), "Tuning", "Pitches").split()]
        if not pitches:
            pitches = [36, 38, 42, 46, 49, 51] if percussion else [40, 45, 50, 55, 59, 64]
        display_pitches = list(reversed(pitches))
        strings = [{"number": index + 1, "midi": midi, "name": string_name(midi)} for index, midi in enumerate(display_pitches)]
        measures = []

        for measure_index, master_bar in enumerate(master_bars):
            bar_refs = gpif_refs(master_bar, "Bars")
            bar_node = bars_by_id.get(bar_refs[track_position]) if track_position < len(bar_refs) else None
            numerator, _, denominator = gpif_text(master_bar, "Time", "4/4").partition("/")
            measure_quarters = max(0.25, safe_int(numerator, 4) * 4 / max(1, safe_int(denominator, 4)))
            events = []
            for voice_id in gpif_refs(bar_node, "Voices"):
                voice = voices_by_id.get(voice_id)
                position = 0.0
                for beat_id in gpif_refs(voice, "Beats"):
                    beat = beats_by_id.get(beat_id)
                    rhythm_ref = safe_int(beat.find("Rhythm").get("ref"), -1) if beat is not None and beat.find("Rhythm") is not None else -1
                    duration = gpif_rhythm_quarters(rhythms_by_id.get(rhythm_ref))
                    slot = max(0, min(15, round(position / measure_quarters * 16)))
                    slots = max(1, min(16 - slot, round(duration / measure_quarters * 16)))
                    for note_id in gpif_refs(beat, "Notes"):
                        note = notes_by_id.get(note_id)
                        fret = safe_int(gpif_property(note, "Fret", "Fret"), 0)
                        gp_string = safe_int(gpif_property(note, "String", "String"), -1)
                        midi = safe_int(gpif_property(note, "Midi", "Number"), 0)
                        string_index = len(pitches) - 1 - gp_string if gp_string >= 0 else (midi % len(pitches))
                        tie = note.find("Tie") if note is not None else None
                        events.append({
                            "slot": slot, "duration": slots,
                            "string": max(0, min(len(pitches) - 1, string_index)),
                            "fret": fret if gp_string >= 0 else midi,
                            "velocity": 95,
                            "tie": bool(tie is not None and tie.get("destination") == "true"),
                        })
                    position += duration
            measures.append({"number": measure_index + 1, "section": "", "events": events})
        if percussion:
            drum_lanes = [
                ("Cymbal", {49, 51, 52, 53, 55, 57, 59}),
                ("Hi-Hat", {42, 44, 46}),
                ("Tom", {41, 43, 45, 47, 48, 50}),
                ("Snare", {37, 38, 40}),
                ("Kick", {35, 36}),
                ("Perc.", set()),
            ]
            strings = [{"number": index + 1, "midi": 0, "name": label} for index, (label, _) in enumerate(drum_lanes)]
            for measure in measures:
                for event in measure["events"]:
                    midi = event["fret"]
                    event["string"] = next((index for index, (_, notes) in enumerate(drum_lanes[:-1]) if midi in notes), len(drum_lanes) - 1)
                    event["fret"] = "●"
        tracks.append({
            "id": f"track-{track_position + 1}", "name": name, "program": program,
            "percussion": percussion, "strings": strings, "measures": measures,
        })
    duplicate_totals = {}
    for item in tracks:
        duplicate_totals[item["name"]] = duplicate_totals.get(item["name"], 0) + 1
    duplicate_seen = {}
    for item in tracks:
        if duplicate_totals[item["name"]] > 1:
            original = item["name"]
            duplicate_seen[original] = duplicate_seen.get(original, 0) + 1
            item["name"] = f"{original} {duplicate_seen[original]}"
    return {"tempo": tempo, "measureCount": len(master_bars), "timeline": timeline, "scoreDuration": round(elapsed, 6), "tracks": tracks}, title, artist, version


def derive_sections(data: dict) -> list[dict]:
    count = safe_int(data.get("measureCount"), 0)
    if count <= 0:
        return []
    markers = []
    tracks = data.get("tracks") or []
    if tracks:
        for index, measure in enumerate(tracks[0].get("measures") or []):
            label = str(measure.get("section") or "").strip()
            if label and (not markers or markers[-1][1].casefold() != label.casefold()):
                markers.append((index, label))
    if markers:
        return [{"key": f"section-{index + 1}", "label": label, "start": start, "end": markers[index + 1][0] if index + 1 < len(markers) else count} for index, (start, label) in enumerate(markers)]

    timeline = data.get("timeline") or []
    boundaries = [0]
    for index in range(1, min(count, len(timeline))):
        if timeline[index].get("timeSignature") != timeline[index - 1].get("timeSignature"):
            boundaries.append(index)
    if len(boundaries) < 3:
        chunk = 16
        boundaries = list(range(0, count, chunk))
    labels = ["Intro", "Verse 1", "Pra-Reff", "Reff", "Interlude", "Verse 2", "Reff Akhir", "Outro"]
    if len(boundaries) > 1:
        labels[min(len(boundaries), len(labels)) - 1] = "Outro"
    return [{"key": f"section-{index + 1}", "label": labels[index] if index < len(labels) else f"Bagian {index + 1}", "start": start, "end": boundaries[index + 1] if index + 1 < len(boundaries) else count} for index, start in enumerate(boundaries)]


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
<link rel="stylesheet" href="generated-tab-player.css?v=20260822-7">
<link rel="stylesheet" href="generated-alphatab-player.css?v=20260822-3">
</head><body class="kc-player-page">
<header class="topbar"></header>
<main class="wrap"><section class="card">
<div class="songline"><div><h1>{title}</h1><p>{artist} · <span id="song-meta">Memuat Guitar Pro…</span></p></div></div>
<div class="playerbar"><div class="transport"><button id="rewind">↶ Awal</button><button class="play" id="play">▶ Putar</button><button id="stop">■ Stop</button></div><div class="control-center"><label class="tempo">Tempo asli <input id="tempo" type="range" disabled><strong><span id="bpm">0</span> BPM</strong></label><label class="seek">Posisi <input id="seek" type="range" value="0"><span id="position-time">0:00 / 0:00</span></label></div><div class="options"><label class="switch"><input id="metro" type="checkbox"> Metronom</label><label class="switch"><input id="loop" type="checkbox"> Ulang</label></div></div>
<div class="workspace"><aside class="sidebar"><p class="side-title">Instrumen</p><div class="instrument-tabs" id="instrument-tabs"></div><p class="side-title">Bagian Lagu</p><div class="section-tabs" id="section-tabs" aria-label="Bagian lagu"></div></aside><section class="score-area"><div class="score"><div class="score-head"><div><strong id="score-title">Tab</strong><span id="tuning"></span></div><span class="position" id="position">Birama 1</span></div><div class="now-playing" aria-live="polite"><strong id="current-chord">—</strong><span id="current-lyric">Lirik belum tersedia</span></div><div class="alphatab-score" id="alphatab-score"><div class="alphatab-loading">Memuat notasi Guitar Pro asli…</div></div><div class="info"><p id="status">Pemutar YouTube sedang disiapkan…</p></div></div></section>
<div class="youtube-panel"><div class="youtube-shell"><div id="youtube-player" class="youtube-frame" aria-label="Video referensi {title}"></div><p class="source">Video referensi: <a href="https://www.youtube.com/watch?v={meta['youtubeId']}" target="_blank" rel="noopener">YouTube</a></p></div></div></div>
</section></main>
<script src="https://cdn.jsdelivr.net/npm/@coderline/alphatab@1.8.4/dist/alphaTab.min.js" crossorigin="anonymous"></script>
<script src="{slug}-data.js?v=20260822-8"></script><script src="generated-alphatab-player.js?v=20260822-5"></script>
<script src="../tab-navigation.js?v=20260822-mobile-follow" data-base=".."></script>
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
    parser.add_argument("--youtube-offset", type=float, default=0.0)
    parser.add_argument("--title", default="")
    parser.add_argument("--artist", default="")
    parser.add_argument("--slug", default="")
    args = parser.parse_args()

    source = (ROOT / args.gp5).resolve() if not Path(args.gp5).is_absolute() else Path(args.gp5)
    try:
        source.relative_to((ROOT / "input").resolve())
    except ValueError:
        raise SystemExit("File sumber harus berada di folder input/")
    if not source.is_file() or source.suffix.lower() not in {".gp", ".gp3", ".gp4", ".gp5"}:
        raise SystemExit("File sumber harus berupa .gp, .gp3, .gp4, atau .gp5 yang tersedia di repository")
    if source.suffix.lower() == ".gp":
        if not zipfile.is_zipfile(source):
            raise SystemExit("File .gp modern harus berupa arsip Guitar Pro yang valid")
        data, detected_title, detected_artist, format_label = extract_gpif(source)
    else:
        if zipfile.is_zipfile(source):
            raise SystemExit("Arsip GP7/GP8 harus menggunakan ekstensi .gp")
        song = guitarpro.parse(str(source))
        data = extract(song)
        detected_title = getattr(song, "title", "")
        detected_artist = getattr(song, "artist", "")
        format_label = "GP5"
    title = (args.title or detected_title or source.stem).strip()
    artist = (args.artist or detected_artist or "Artis belum diisi").strip()
    slug = slugify(args.slug or f"{artist}-{title}")
    if not slug:
        raise SystemExit("Slug tidak valid")
    video_id = youtube_id(args.youtube)
    if not data["tracks"]:
        raise SystemExit("File Guitar Pro tidak berisi track")

    meta = {"slug": slug, "title": title, "artist": artist, "youtubeId": video_id, "youtubeOffset": args.youtube_offset, "gpFile": f"../input/{source.name}"}
    data["sections"] = derive_sections(data)
    data.update(meta)
    data_path = ROOT / "tabs" / f"{slug}-data.js"
    page_path = ROOT / "tabs" / f"{slug}.html"
    data_path.write_text("window.KC_TAB_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    page_path.write_text(page_html(meta), encoding="utf-8")

    instruments = [track["name"] for track in data["tracks"]]
    entry = {
        "slug": slug, "path": f"tabs/{slug}.html", "title": title, "artist": artist,
        "status": f"{len(instruments)} instrumen · {data['measureCount']} birama",
        "bars": data["measureCount"], "key": format_label, "bpmLabel": f"{data['tempo']} BPM",
        "instruments": instruments, "searchTerms": ["guitar pro", "otomatis"],
    }
    update_catalog(entry)
    github_output({"slug": slug, "page": page_path.relative_to(ROOT).as_posix(), "data": data_path.relative_to(ROOT).as_posix()})
    print(f"Generated {page_path.relative_to(ROOT)} with {len(instruments)} tracks and {data['measureCount']} measures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
