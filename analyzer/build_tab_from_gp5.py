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
                events.append({"slot": slot,"duration": slots,"string": max(0, safe_int(note.string, 1) - 1),"fret": safe_int(note.value),"velocity": safe_int(getattr(note, "velocity", 95), 95),"tie": bool(getattr(getattr(note, "type", None), "name", "").lower() == "tie")})
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
            measures.append({"number": measure_index + 1,"section": section,"events": measure_events(measure)})
        tracks.append({"id": f"track-{index + 1}","name": (track.name or f"Track {index + 1}").strip(),"program": safe_int(getattr(track.channel, "instrument", 0)),"percussion": bool(track.isPercussionTrack),"strings": [{"number": item.number, "midi": item.value, "name": string_name(item.value)} for item in strings],"measures": measures})
    return {"tempo": safe_int(getattr(song, "tempo", 120), 120),"measureCount": len(headers),"tracks": tracks}


RHYTHM_QUARTERS = {"Longa":16.0,"DoubleWhole":8.0,"Whole":4.0,"Half":2.0,"Quarter":1.0,"Eighth":0.5,"16th":0.25,"32nd":0.125,"64th":0.0625,"128th":0.03125}


def gpif_text(node, path: str, default="") -> str:
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None else default


def gpif_refs(node, path: str) -> list[int]:
    return [safe_int(value, -1) for value in gpif_text(node, path).split() if safe_int(value, -1) >= 0]


def gpif_rhythm_quarters(rhythm) -> float:
    base_value = RHYTHM_QUARTERS.get(gpif_text(rhythm, "NoteValue"), 1.0)
    value = base_value
    dot = rhythm.find("AugmentationDot") if rhythm is not None else None
    dots = safe_int(dot.get("count"), 0) if dot is not None else 0
    addition = 0.5
    for _ in range(dots):
        value += base_value * addition; addition *= 0.5
    tuplet = rhythm.find("PrimaryTuplet") if rhythm is not None else None
    if tuplet is not None:
        numerator = safe_int(tuplet.get("num") or gpif_text(tuplet, "Num"), 1)
        denominator = safe_int(tuplet.get("den") or gpif_text(tuplet, "Den"), 1)
        if numerator > 0: value *= denominator / numerator
    return max(value, 1 / 128)


def gpif_property(node, name: str, child: str, default="") -> str:
    if node is None: return default
    prop = node.find(f"./Properties/Property[@name='{name}']/{child}")
    return (prop.text or "").strip() if prop is not None else default


def extract_gpif(source: Path) -> tuple[dict, str, str, str]:
    with zipfile.ZipFile(source) as archive:
        try:
            score_info = archive.getinfo("Content/score.gpif")
            if score_info.file_size > 20 * 1024 * 1024: raise SystemExit("Data score.gpif terlalu besar (maksimal 20 MB)")
            root = ET.fromstring(archive.read(score_info))
        except KeyError as exc: raise SystemExit("Arsip .gp tidak memiliki Content/score.gpif") from exc
    score = root.find("Score"); title = gpif_text(score,"Title",source.stem); artist = gpif_text(score,"Artist","Artis belum diisi"); version = gpif_text(root,"GPVersion","GP7/GP8")
    tempo = 120
    for automation in root.findall("./MasterTrack/Automations/Automation"):
        if gpif_text(automation,"Type") == "Tempo": tempo = safe_int(gpif_text(automation,"Value").split()[0],120); break
    tracks_by_id={safe_int(n.get("id"),-1):n for n in root.findall("./Tracks/Track")}; bars_by_id={safe_int(n.get("id"),-1):n for n in root.findall("./Bars/Bar")}; voices_by_id={safe_int(n.get("id"),-1):n for n in root.findall("./Voices/Voice")}; beats_by_id={safe_int(n.get("id"),-1):n for n in root.findall("./Beats/Beat")}; notes_by_id={safe_int(n.get("id"),-1):n for n in root.findall("./Notes/Note")}; rhythms_by_id={safe_int(n.get("id"),-1):n for n in root.findall("./Rhythms/Rhythm")}; master_bars=root.findall("./MasterBars/MasterBar"); master_track_ids=gpif_refs(root.find("MasterTrack"),"Tracks") or sorted(tracks_by_id)
    tracks=[]
    for track_position, track_id in enumerate(master_track_ids):
        track_node=tracks_by_id.get(track_id)
        if track_node is None: continue
        name=gpif_text(track_node,"Name",f"Track {track_position+1}"); kind=gpif_text(track_node,"InstrumentSet/Type").lower(); percussion="drum" in kind or "percussion" in kind; program=safe_int(gpif_text(track_node,"Sounds/Sound/MIDI/Program"),0)
        pitches=[safe_int(v) for v in gpif_property(track_node.find("Staves/Staff"),"Tuning","Pitches").split()] or ([36,38,42,46,49,51] if percussion else [40,45,50,55,59,64]); display_pitches=list(reversed(pitches)); strings=[{"number":i+1,"midi":m,"name":string_name(m)} for i,m in enumerate(display_pitches)]; measures=[]
        for measure_index, master_bar in enumerate(master_bars):
            bar_refs=gpif_refs(master_bar,"Bars"); bar_node=bars_by_id.get(bar_refs[track_position]) if track_position < len(bar_refs) else None; numerator,_,denominator=gpif_text(master_bar,"Time","4/4").partition("/"); measure_quarters=max(.25,safe_int(numerator,4)*4/max(1,safe_int(denominator,4))); events=[]
            for voice_id in gpif_refs(bar_node,"Voices"):
                voice=voices_by_id.get(voice_id); position=0.0
                for beat_id in gpif_refs(voice,"Beats"):
                    beat=beats_by_id.get(beat_id); rhythm_ref=safe_int(beat.find("Rhythm").get("ref"),-1) if beat is not None and beat.find("Rhythm") is not None else -1; duration=gpif_rhythm_quarters(rhythms_by_id.get(rhythm_ref)); slot=max(0,min(15,round(position/measure_quarters*16))); slots=max(1,min(16-slot,round(duration/measure_quarters*16)))
                    for note_id in gpif_refs(beat,"Notes"):
                        note=notes_by_id.get(note_id); fret=safe_int(gpif_property(note,"Fret","Fret"),0); gp_string=safe_int(gpif_property(note,"String","String"),-1); midi=safe_int(gpif_property(note,"Midi","Number"),0); string_index=len(pitches)-1-gp_string if gp_string>=0 else (midi%len(pitches)); tie=note.find("Tie") if note is not None else None; events.append({"slot":slot,"duration":slots,"string":max(0,min(len(pitches)-1,string_index)),"fret":fret if gp_string>=0 else midi,"velocity":95,"tie":bool(tie is not None and tie.get("destination")=="true")})
                    position += duration
            measures.append({"number":measure_index+1,"section":"","events":events})
        if percussion:
            drum_lanes=[("Cymbal",{49,51,52,53,55,57,59}),("Hi-Hat",{42,44,46}),("Tom",{41,43,45,47,48,50}),("Snare",{37,38,40}),("Kick",{35,36}),("Perc.",set())]; strings=[{"number":i+1,"midi":0,"name":label} for i,(label,_) in enumerate(drum_lanes)]
            for measure in measures:
                for event in measure["events"]:
                    midi=event["fret"]; event["string"]=next((i for i,(_,notes) in enumerate(drum_lanes[:-1]) if midi in notes),len(drum_lanes)-1); event["fret"]="●"
        tracks.append({"id":f"track-{track_position+1}","name":name,"program":program,"percussion":percussion,"strings":strings,"measures":measures})
    duplicate_totals={}
    for item in tracks: duplicate_totals[item["name"]]=duplicate_totals.get(item["name"],0)+1
    duplicate_seen={}
    for item in tracks:
        if duplicate_totals[item["name"]]>1:
            original=item["name"]; duplicate_seen[original]=duplicate_seen.get(original,0)+1; item["name"]=f"{original} {duplicate_seen[original]}"
    return {"tempo":tempo,"measureCount":len(master_bars),"tracks":tracks},title,artist,version


def page_html(meta: dict) -> str:
    title=meta["title"].replace("&","&amp;").replace("<","&lt;"); artist=meta["artist"].replace("&","&amp;").replace("<","&lt;"); slug=meta["slug"]
    return f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Tab Musik {artist} — {title}, dibuat otomatis dari Guitar Pro."><title>Tab Musik — {artist} · {title}</title><script>if(new URLSearchParams(location.search).get('embed')==='1'||window.self!==window.top)document.documentElement.classList.add('embed');</script><link rel="stylesheet" href="../tab-navigation.css?v=20260821-deeplink2"><link rel="stylesheet" href="songsterr-score.css?v=20260821-3"><link rel="stylesheet" href="generated-tab-player.css?v=20260821-standard1"></head><body class="kc-player-page"><header class="topbar"></header><main class="wrap"><section class="card"><div class="songline"><div><h1>{title}</h1><p>{artist} · <span id="song-meta">Memuat Guitar Pro…</span></p></div></div><div class="playerbar"><div class="transport"><button id="rewind">↶ Awal</button><button class="play" id="play">▶ Putar</button><button id="stop">■ Stop</button></div><div class="control-center"><label class="seek">Posisi <input id="seek" type="range" value="0"><span id="position-time">Birama 1</span></label></div><label class="switch"><input id="loop" type="checkbox"> Ulang</label></div><div class="workspace"><section class="score-area"><div class="score"><div class="score-head"><div><strong id="score-title">Tab</strong><span id="tuning"></span></div><span class="position" id="position">Birama 1</span></div><div class="bars" id="bars"></div><div class="info"><p id="status">Spasi = putar/jeda. Semua instrumen mengikuti posisi lagu yang sama.</p></div></div></section><aside class="right-rail"><div class="youtube-panel"><iframe class="youtube-reference" src="https://www.youtube-nocookie.com/embed/{meta['youtubeId']}" title="Video referensi {title}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe><p class="source">Video referensi: <a href="https://www.youtube.com/watch?v={meta['youtubeId']}" target="_blank" rel="noopener">YouTube</a></p></div><div class="sidebar"><p class="side-title">Instrumen</p><div class="instrument-tabs" id="instrument-tabs"></div></div></aside></div></section></main><script src="{slug}-data.js?v=20260821-standard1"></script><script src="generated-tab-player.js?v=20260821-standard1"></script><script src="../tab-navigation.js?v=20260821-deeplink2" data-base=".."></script></body></html>'''


def update_catalog(entry: dict) -> None:
    catalog=json.loads(CATALOG.read_text(encoding="utf-8")); songs=catalog.setdefault("songs",[]); songs[:]=[song for song in songs if song.get("slug")!=entry["slug"]]; songs.append(entry); CATALOG.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def github_output(values: dict) -> None:
    target=os.environ.get("GITHUB_OUTPUT")
