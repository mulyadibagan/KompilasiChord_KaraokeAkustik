#!/usr/bin/env python3
"""Build compact, playable 1/16-grid tab data from temporary separated stems."""

import argparse
import json
import math
import re
from pathlib import Path

import librosa
import numpy as np
from scipy.signal import butter, sosfilt


SONGS = {
    "aiman": {
        "namespace": "KC_AIMAN_TRANSCRIPTION",
        "bpm": 73,
        "start": 2.312,
        "bars": 66,
        "lead_stem": "Other",
        "chords": ["A", "D", "E", "C#m", "F#m", "Bm"],
        "sections": [
            ["intro", "Intro", 3],
            ["verse1", "Verse 1", 16],
            ["reff", "Reff 1", 16],
            ["interlude", "Interlude", 4],
            ["reff2", "Reff 2", 16],
            ["ending", "Ending", 8],
            ["outro", "Outro", 3],
        ],
    },
    "romeo": {
        "namespace": "KC_ROMEO_TRANSCRIPTION",
        "bpm": 73,
        "start": -2.088,
        "bars": 88,
        "lead_stem": "Guitar",
        "chords": ["F#m", "Bm", "G#m7b5", "C#7", "E", "D", "C#m", "A", "Em", "F#", "G#dim"],
        "sections": [
            ["intro", "Intro", 4],
            ["verse1", "Verse 1", 7],
            ["reff", "Reff 1", 10],
            ["verse2", "Verse 2", 11],
            ["reff2", "Reff 2", 14],
            ["interlude", "Interlude", 3],
            ["verse3", "Verse Ulang", 10],
            ["reff3", "Reff Akhir", 12],
            ["outro", "Outro", 17],
        ],
    },
    "sultan": {
        "namespace": "KC_SULTAN_TRANSCRIPTION",
        "bpm": 125,
        "start": 1.52,
        "bars": 158,
        "lead_stem": "Guitar",
        "chords": ["Gm", "Cm", "D", "D#", "A", "F", "A#", "Dm"],
        "sections": [
            ["intro", "Intro", 1],
            ["verse1", "Verse 1", 14],
            ["verse2", "Verse 2", 16],
            ["pre", "Pra-Reff 1", 13],
            ["reff", "Reff 1", 21],
            ["interlude", "Interlude", 18],
            ["pre2", "Pra-Reff 2", 13],
            ["reff2", "Reff 2", 21],
            ["reff3", "Reff Tambahan", 11],
            ["outro", "Ending", 30],
        ],
    },
}

PITCH_CLASS = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def stem_path(root, song, stem):
    matches = list((root / song).glob(f"*({stem})*.wav"))
    if not matches:
        raise FileNotFoundError(f"Missing {stem} stem for {song}")
    return matches[0]


def chord_template(name):
    match = re.match(r"([A-G]#?)(.*)", name)
    root = PITCH_CLASS[match.group(1)]
    suffix = match.group(2)
    minor = suffix.startswith("m") and not suffix.startswith("maj")
    third = 3 if minor else 4
    fifth = 6 if ("dim" in suffix or "m7b5" in suffix) else 7
    template = np.full(12, 0.04)
    template[root] = 1
    template[(root + third) % 12] = 0.82
    template[(root + fifth) % 12] = 0.66
    if "7" in suffix:
        template[(root + (11 if "maj7" in suffix else 10)) % 12] = 0.56
    return template / np.linalg.norm(template)


def chord_grid(mix_path, cfg):
    y, sr = librosa.load(mix_path, sr=22050, mono=True)
    harmonic = librosa.effects.harmonic(y)
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sr, hop_length=512)
    times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=512)
    templates = np.stack([chord_template(name) for name in cfg["chords"]])
    half_bar = 120 / cfg["bpm"]
    labels = []
    margins = []
    for cell in range(cfg["bars"] * 2):
        begin = cfg["start"] + cell * half_bar
        end = begin + half_bar
        frames = np.flatnonzero((times >= max(0, begin + 0.08)) & (times < min(times[-1], end - 0.08)))
        if len(frames) < 2:
            labels.append(cfg["chords"][0])
            margins.append(0)
            continue
        vector = np.median(chroma[:, frames], axis=1)
        vector /= np.linalg.norm(vector) + 1e-9
        scores = templates @ vector
        order = np.argsort(scores)[::-1]
        labels.append(cfg["chords"][int(order[0])])
        margins.append(float(scores[order[0]] - scores[order[1]]))
    bars = []
    for bar in range(cfg["bars"]):
        first, second = labels[bar * 2 : bar * 2 + 2]
        first_margin, second_margin = margins[bar * 2 : bar * 2 + 2]
        if first != second and min(first_margin, second_margin) < 0.055:
            if first_margin >= second_margin:
                second = first
            else:
                first = second
        bars.append([first] if first == second else [first, second])
    return bars


def playable_midi(value, lowest, highest):
    """Keep the detected pitch class while moving octave errors into instrument range."""
    midi = int(round(value))
    while midi < lowest:
        midi += 12
    while midi > highest:
        midi -= 12
    return midi


def pitch_grid(path, cfg, fmin, fmax, max_events, lowest_midi, highest_midi):
    y, sr = librosa.load(path, sr=22050, mono=True)
    frame_length = 2048
    hop = 512
    harmonic = librosa.effects.harmonic(y, margin=2.0)
    f0 = librosa.yin(harmonic, fmin=fmin, fmax=fmax, sr=sr, frame_length=frame_length, hop_length=hop)
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop, center=True)[0]
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop)
    threshold = max(np.percentile(rms, 35) * 1.35, np.max(rms) * 0.015)
    slot_seconds = 15 / cfg["bpm"]
    total_slots = cfg["bars"] * 16
    buckets = [[] for _ in range(total_slots)]
    for index, frequency in enumerate(f0):
        if not np.isfinite(frequency) or rms[index] < threshold:
            continue
        slot = int(round((times[index] - cfg["start"]) / slot_seconds))
        if 0 <= slot < total_slots:
            buckets[slot].append(69 + 12 * math.log2(float(frequency) / 440))
    slot_notes = [None] * total_slots
    for index, values in enumerate(buckets):
        if values:
            slot_notes[index] = playable_midi(float(np.median(values)), lowest_midi, highest_midi)
    for index in range(1, total_slots - 1):
        if slot_notes[index] is None and slot_notes[index - 1] == slot_notes[index + 1]:
            slot_notes[index] = slot_notes[index - 1]
    result = [[] for _ in range(cfg["bars"])]
    for bar in range(cfg["bars"]):
        notes = slot_notes[bar * 16 : (bar + 1) * 16]
        runs = []
        cursor = 0
        while cursor < 16:
            note = notes[cursor]
            if note is None:
                cursor += 1
                continue
            end = cursor + 1
            while end < 16 and notes[end] is not None and abs(notes[end] - note) <= 1:
                end += 1
            duration = max(1, end - cursor)
            runs.append([cursor, duration, int(round(np.median([n for n in notes[cursor:end] if n is not None])))])
            cursor = end
        if len(runs) > max_events:
            ranked = sorted(range(len(runs)), key=lambda i: (runs[i][1], -runs[i][0]), reverse=True)[:max_events]
            runs = [runs[i] for i in sorted(ranked)]
        result[bar] = runs
    return result


def onset_slots(path, cfg, maximum=8):
    y, sr = librosa.load(path, sr=22050, mono=True)
    envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=256)
    times = librosa.onset.onset_detect(onset_envelope=envelope, sr=sr, hop_length=256, units="time", backtrack=False)
    strength_times = librosa.frames_to_time(np.arange(len(envelope)), sr=sr, hop_length=256)
    threshold = np.percentile(envelope, 58)
    slot_seconds = 15 / cfg["bpm"]
    out = [[] for _ in range(cfg["bars"])]
    scored = [[] for _ in range(cfg["bars"])]
    for time in times:
        frame = min(len(envelope) - 1, int(np.searchsorted(strength_times, time)))
        if envelope[frame] < threshold:
            continue
        absolute = int(round((float(time) - cfg["start"]) / slot_seconds))
        if 0 <= absolute < cfg["bars"] * 16:
            scored[absolute // 16].append((absolute % 16, float(envelope[frame])))
    for bar, events in enumerate(scored):
        best = {}
        for slot, strength in events:
            best[slot] = max(best.get(slot, 0), strength)
        selected = sorted(best.items(), key=lambda item: item[1], reverse=True)[:maximum]
        out[bar] = sorted(slot for slot, _ in selected)
        if not out[bar]:
            out[bar] = [0, 4, 8, 12]
    return out


def band_onsets(y, sr, low, high, cfg, percentile, maximum):
    nyquist = sr / 2
    if low <= 0:
        sos = butter(4, high / nyquist, btype="lowpass", output="sos")
    elif high >= nyquist:
        sos = butter(4, low / nyquist, btype="highpass", output="sos")
    else:
        sos = butter(4, [low / nyquist, high / nyquist], btype="bandpass", output="sos")
    filtered = sosfilt(sos, y)
    envelope = librosa.onset.onset_strength(y=filtered, sr=sr, hop_length=256)
    frames = librosa.onset.onset_detect(onset_envelope=envelope, sr=sr, hop_length=256, backtrack=False)
    threshold = np.percentile(envelope, percentile)
    slot_seconds = 15 / cfg["bpm"]
    per_bar = [[] for _ in range(cfg["bars"])]
    for frame in frames:
        if envelope[frame] < threshold:
            continue
        time = librosa.frames_to_time(frame, sr=sr, hop_length=256)
        absolute = int(round((float(time) - cfg["start"]) / slot_seconds))
        if 0 <= absolute < cfg["bars"] * 16:
            per_bar[absolute // 16].append((absolute % 16, float(envelope[frame])))
    output = []
    for events in per_bar:
        best = {}
        for slot, strength in events:
            best[slot] = max(best.get(slot, 0), strength)
        chosen = sorted(best.items(), key=lambda item: item[1], reverse=True)[:maximum]
        output.append(sorted(slot for slot, _ in chosen))
    return output


def drum_grid(path, cfg):
    y, sr = librosa.load(path, sr=22050, mono=True)
    kicks = band_onsets(y, sr, 25, 170, cfg, 55, 5)
    snares = band_onsets(y, sr, 170, 3200, cfg, 68, 4)
    hats = band_onsets(y, sr, 4200, sr / 2 - 10, cfg, 45, 8)
    section_starts = set()
    cursor = 0
    for _, _, length in cfg["sections"]:
        section_starts.add(cursor)
        cursor += length
    result = []
    for bar in range(cfg["bars"]):
        h = hats[bar]
        if len(h) < 4:
            h = sorted(set(h + [0, 2, 4, 6, 8, 10, 12, 14]))[:8]
        s = [slot for slot in snares[bar] if slot not in kicks[bar]][:4]
        if len(s) < 2:
            s = sorted(set(s + [4, 12]))[:4]
        k = kicks[bar][:5] or [0, 8]
        result.append({"h": h, "s": s, "k": k, "c": [0] if bar in section_starts and bar else [], "t": []})
    return result


def build_song(song, cfg, stems_root, audio_root):
    lead_path = stem_path(stems_root, song, cfg["lead_stem"])
    guitar_path = stem_path(stems_root, song, "Guitar")
    if song == "aiman":
        guitar_path = stem_path(stems_root, song, "Other")
    data = {
        "meta": {"bpm": cfg["bpm"], "start": cfg["start"], "grid": "1/16", "bars": cfg["bars"]},
        "sections": [{"key": key, "label": label, "length": length} for key, label, length in cfg["sections"]],
        "chords": chord_grid(audio_root / f"{song}.wav", cfg),
        "lead": pitch_grid(lead_path, cfg, librosa.note_to_hz("E3"), librosa.note_to_hz("C7"), 8, 52, 84),
        "bass": pitch_grid(stem_path(stems_root, song, "Bass"), cfg, librosa.note_to_hz("B0"), librosa.note_to_hz("C4"), 6, 28, 59),
        "vocal": pitch_grid(stem_path(stems_root, song, "Vocals"), cfg, librosa.note_to_hz("C2"), librosa.note_to_hz("C6"), 7, 40, 84),
        "guitar": onset_slots(guitar_path, cfg, 8),
        "drums": drum_grid(stem_path(stems_root, song, "Drums"), cfg),
    }
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stems-root", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    for song, cfg in SONGS.items():
        data = build_song(song, cfg, args.stems_root, args.audio_root)
        target = args.output_root / f"{song}-transcription-data.js"
        target.write_text(f"window.{cfg['namespace']}=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        print(f"{song}: {cfg['bars']} bars -> {target}")


if __name__ == "__main__":
    main()
