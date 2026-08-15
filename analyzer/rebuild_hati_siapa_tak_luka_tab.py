#!/usr/bin/env python3
"""Build the Hati Siapa Tak Luka tab from isolated reference-audio stems.

Every displayed note or drum hit must originate in a detected stem event.  Chord
and section labels are descriptive only and are never used to fill a bar.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf


BPM = 73
START = 2.066576
DURATION = 317.788299
BARS = 96
SLOT_SECONDS = 15 / BPM
BAR_SECONDS = 240 / BPM
SOURCE_SHA256 = "f4819f91d08cf21ec16c84db3eac949012e2be7326a45ca93a48cdb62c4745ca"
GUITAR_OPEN = (64, 59, 55, 50, 45, 40)  # high E through low E

SECTIONS = [
    {"key": "intro", "label": "Intro", "length": 8},
    {"key": "verse1a", "label": "Bait 1A", "length": 8},
    {"key": "verse1b", "label": "Bait 1B", "length": 8},
    {"key": "pre1", "label": "Pra-Reff 1", "length": 10},
    {"key": "reff1", "label": "Reff 1", "length": 8},
    {"key": "transition", "label": "Transisi", "length": 4},
    {"key": "interlude", "label": "Interlude", "length": 10},
    {"key": "verse2", "label": "Bait 2", "length": 8},
    {"key": "pre2", "label": "Pra-Reff 2", "length": 10},
    {"key": "reff2", "label": "Reff 2", "length": 8},
    {"key": "final", "label": "Reff Akhir", "length": 12},
    {"key": "outro", "label": "Outro", "length": 2},
]

# Beat-synchronous chroma and bass-root labels.  These are visual context only.
CHORDS = [
    ["Bm"], ["F#"], ["Bm"], ["C#dim"], ["Bm"], ["C#dim"], ["Bm"], ["F#7"],
    ["Bm"], ["Bm"], ["Bm"], ["Em"], ["Em"], ["Bm"], ["F#", "G"], ["F#"],
    ["Bm"], ["D"], ["Bm"], ["Em"], ["Em"], ["Bm"], ["F#"], ["Bm"],
    ["Bm"], ["F#"], ["Bm"], ["A"], ["D"], ["F#"], ["Bm"], ["A"], ["F#"], ["F#"],
    ["Bm", "A"], ["G"], ["F#"], ["Bm", "F#"], ["Bm", "A"], ["G"], ["F#"], ["Bm"],
    ["Bm"], ["Em", "A"], ["D", "G"], ["Em", "F#"],
    ["Bm"], ["G"], ["Em"], ["F#"], ["G"], ["Em"], ["F#"], ["G", "A"], ["Bm"], ["F#7"],
    ["Bm"], ["D"], ["Bm"], ["Em"], ["Em"], ["Bm"], ["F#"], ["Bm"],
    ["Bm"], ["F#"], ["Bm"], ["A"], ["D"], ["F#"], ["Bm"], ["A"], ["F#"], ["F#"],
    ["Bm", "A"], ["G"], ["F#"], ["Bm", "F#"], ["Bm", "A"], ["G"], ["F#"], ["Bm", "F#"],
    ["Bm", "A"], ["G"], ["F#"], ["Bm", "F#"], ["Bm", "A"], ["G"], ["F#"], ["Bm", "F#"],
    ["Bm", "A"], ["G"], ["F#"], ["Bm", "F#"], ["Bm"], ["Bm"],
]


def bar_rms_db(path: Path) -> list[float]:
    audio, sample_rate = sf.read(path, always_2d=True)
    mono = audio.mean(axis=1)
    values = []
    for bar in range(BARS):
        begin = round((START + bar * BAR_SECONDS) * sample_rate)
        end = round((START + (bar + 1) * BAR_SECONDS) * sample_rate)
        segment = mono[max(0, begin) : min(len(mono), end)]
        rms = math.sqrt(float(np.mean(segment * segment))) if len(segment) else 0.0
        values.append(20 * math.log10(rms + 1e-12))
    return values


def read_candidates(
    path: Path,
    *,
    velocity_min: float,
    midi_min: int,
    midi_max: int,
    rms: list[float],
    rms_min: float,
) -> dict[int, dict[int, dict]]:
    buckets: dict[int, dict[int, dict]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            midi = int(row["pitch_midi"])
            velocity = float(row["velocity"])
            begin = float(row["start_time_s"])
            end = float(row["end_time_s"])
            absolute_slot = round((begin - START) / SLOT_SECONDS)
            if not (midi_min <= midi <= midi_max and velocity >= velocity_min):
                continue
            if not 0 <= absolute_slot < BARS * 16:
                continue
            bar, slot = divmod(absolute_slot, 16)
            if rms[bar] < rms_min:
                continue
            duration = max(1, round((end - begin) / SLOT_SECONDS))
            duration = min(duration, 16 - slot)
            candidate = {"midi": midi, "velocity": velocity, "duration": duration}
            previous = buckets.setdefault(absolute_slot, {}).get(midi)
            if previous is None or (velocity, duration) > (
                previous["velocity"],
                previous["duration"],
            ):
                buckets[absolute_slot][midi] = candidate
    return buckets


def guitar_assignment(candidates: list[dict]) -> list[dict]:
    """Select the strongest physically playable six-string voicing at one onset."""
    strongest = sorted(candidates, key=lambda item: item["velocity"], reverse=True)[:8]
    for size in range(min(6, len(strongest)), 0, -1):
        best = None
        for subset in itertools.combinations(strongest, size):
            notes = sorted(subset, key=lambda item: item["midi"], reverse=True)
            for strings in itertools.combinations(range(6), size):
                frets = [
                    note["midi"] - GUITAR_OPEN[string]
                    for note, string in zip(notes, strings)
                ]
                if not all(0 <= fret <= 20 for fret in frets):
                    continue
                spread = max(frets) - min(frets)
                score = (
                    sum(frets) / size
                    + spread * 0.85
                    + max(frets) * 0.18
                    - sum(note["velocity"] for note in notes) / 350
                )
                if best is None or score < best[0]:
                    assigned = [
                        {**note, "string": string, "fret": fret}
                        for note, string, fret in zip(notes, strings, frets)
                    ]
                    best = (score, assigned)
        if best is not None:
            return best[1]
    return []


def build_guitar(csv_path: Path, stem_path: Path) -> list[list[list[int]]]:
    buckets = read_candidates(
        csv_path,
        velocity_min=55,
        midi_min=40,
        midi_max=84,
        rms=bar_rms_db(stem_path),
        rms_min=-60,
    )
    output: list[list[list[int]]] = [[] for _ in range(BARS)]
    for absolute_slot, candidates in sorted(buckets.items()):
        bar, slot = divmod(absolute_slot, 16)
        for event in guitar_assignment(list(candidates.values())):
            output[bar].append(
                [slot, event["duration"], event["midi"], event["string"], event["fret"]]
            )
    for events in output:
        events.sort(key=lambda event: (event[0], event[3], event[2]))
    return output


def select_polyphony(candidates: list[dict], maximum: int) -> list[dict]:
    if len(candidates) <= maximum:
        return candidates
    by_pitch = sorted(candidates, key=lambda event: event["midi"])
    selected = [by_pitch[0], by_pitch[-1]]
    selected_ids = {id(event) for event in selected}
    for event in sorted(candidates, key=lambda item: item["velocity"], reverse=True):
        if id(event) not in selected_ids:
            selected.append(event)
            selected_ids.add(id(event))
        if len(selected) == maximum:
            break
    return selected


def build_synth(csv_path: Path, stem_path: Path) -> list[list[list[int]]]:
    buckets = read_candidates(
        csv_path,
        velocity_min=55,
        midi_min=36,
        midi_max=96,
        rms=bar_rms_db(stem_path),
        rms_min=-55,
    )
    output: list[list[list[int]]] = [[] for _ in range(BARS)]
    for absolute_slot, by_pitch in sorted(buckets.items()):
        bar, slot = divmod(absolute_slot, 16)
        for event in select_polyphony(list(by_pitch.values()), 6):
            output[bar].append([slot, event["duration"], event["midi"]])
    for events in output:
        events.sort(key=lambda event: (event[0], -event[2]))
    return output


def choose_bass(candidates: list[dict]) -> dict:
    pitches = {event["midi"] for event in candidates}
    without_octave_doubles = [
        event for event in candidates if event["midi"] - 12 not in pitches
    ] or candidates
    return max(
        without_octave_doubles,
        key=lambda event: event["velocity"] - max(0, event["midi"] - 45) * 0.8,
    )


def bass_position(midi: int) -> tuple[int, int]:
    open_strings = (43, 38, 33, 28)  # G, D, A, E
    choices = [
        (midi - open_midi, string)
        for string, open_midi in enumerate(open_strings)
        if 0 <= midi - open_midi <= 20
    ]
    fret, string = min(choices) if choices else (max(0, midi - 28), 3)
    return string, fret


def build_bass(csv_path: Path, stem_path: Path) -> list[list[list[int]]]:
    buckets = read_candidates(
        csv_path,
        velocity_min=55,
        midi_min=28,
        midi_max=55,
        rms=bar_rms_db(stem_path),
        rms_min=-55,
    )
    output: list[list[list[int]]] = [[] for _ in range(BARS)]
    for absolute_slot, by_pitch in sorted(buckets.items()):
        bar, slot = divmod(absolute_slot, 16)
        event = choose_bass(list(by_pitch.values()))
        string, fret = bass_position(event["midi"])
        output[bar].append([slot, event["duration"], event["midi"], string, fret])
    return output


def build_drums(stem_path: Path) -> list[dict[str, list[int]]]:
    import drumscript

    audio, sample_rate = drumscript.load_audio(str(stem_path), sr=drumscript.SAMPLE_RATE)
    normalized = drumscript.normalise_audio(audio)
    onsets = drumscript.detect_onsets(normalized, sample_rate)
    events = drumscript.classify_events(normalized, sample_rate, onsets)
    rms = bar_rms_db(stem_path)
    name_map = {
        "hi_hat_closed": "h",
        "hi_hat_open": "h",
        "ride": "c",
        "crash": "c",
        "kick": "k",
        "snare": "s",
        "low_tom": "t",
        "mid_tom": "t",
        "high_tom": "t",
    }
    output = [{key: set() for key in ("h", "s", "k", "c", "t")} for _ in range(BARS)]
    for event in events:
        absolute_slot = round((event["time_sec"] - START) / SLOT_SECONDS)
        if not 0 <= absolute_slot < BARS * 16:
            continue
        bar, slot = divmod(absolute_slot, 16)
        if rms[bar] < -45:
            continue
        for instrument in event["instruments"]:
            key = name_map.get(instrument)
            if key:
                output[bar][key].add(slot)

        # This recording's half-time snare has unusually bright wire energy.  The
        # library's generic 0.85 HFER ceiling rejects some otherwise unambiguous
        # 120-450 Hz snare bodies, so retain those measured onset profiles here.
        profile = event.get("debug_features", {})
        if (
            120 <= profile.get("peak_freq", 0) <= 450
            and 0.15 <= profile.get("hfer", 0) < 0.93
            and profile.get("lfer", 1) < 0.12
        ):
            output[bar]["s"].add(slot)
    return [
        {key: sorted(slots) for key, slots in bar.items()}
        for bar in output
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stems", type=Path, required=True)
    parser.add_argument("--guitar-left-csv", type=Path, required=True)
    parser.add_argument("--guitar-right-csv", type=Path, required=True)
    parser.add_argument("--guitar-left-stem", type=Path, required=True)
    parser.add_argument("--guitar-right-stem", type=Path, required=True)
    parser.add_argument("--synth-csv", type=Path, required=True)
    parser.add_argument("--bass-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    assert sum(section["length"] for section in SECTIONS) == BARS
    assert len(CHORDS) == BARS
    guitar1 = build_guitar(args.guitar_left_csv, args.guitar_left_stem)
    guitar2 = build_guitar(args.guitar_right_csv, args.guitar_right_stem)
    synth = build_synth(args.synth_csv, args.stems / "other.wav")
    bass = build_bass(args.bass_csv, args.stems / "bass.wav")
    drums = build_drums(args.stems / "drums.wav")
    drum_counts = {
        key: sum(len(bar[key]) for bar in drums)
        for key in ("h", "s", "k", "c", "t")
    }
    component_names = {
        "h": "hi-hat",
        "s": "snare",
        "k": "kick",
        "c": "cymbal",
        "t": "tom",
    }
    data = {
        "meta": {
            "bpm": BPM,
            "start": START,
            "duration": DURATION,
            "grid": "1/16",
            "bars": BARS,
            "method": "htdemucs_6s stem separation + per-channel Basic Pitch polyphonic note analysis + DrumScript onset and spectral classification + MP3-timed 1/16 quantization + no generated fallback",
            "preservePitch": True,
            "silencePolicy": "preserve",
            "vocalTrack": False,
            "sourceSha256": SOURCE_SHA256,
            "detectedInstruments": ["guitar_left", "guitar_right", "synth", "bass", "drums"],
            "excludedStems": ["vocals", "piano_residual"],
            "guitarTracks": 2,
            "guitarChannelOnsetPitchJaccard": 0.375979,
            "drumComponents": [
                component_names[key] for key, count in drum_counts.items() if count
            ],
        },
        "sections": SECTIONS,
        "chords": CHORDS,
        "guitar1": guitar1,
        "guitar2": guitar2,
        "synth": synth,
        "bass": bass,
        "drums": drums,
    }
    source = "window.KC_HATI_SIAPA_TAK_LUKA_TRANSCRIPTION=" + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"
    args.output.write_text(source, encoding="utf-8")
    print(
        "Hati Siapa Tak Luka rebuilt:",
        sum(map(len, guitar1)),
        "guitar-1 notes,",
        sum(map(len, guitar2)),
        "guitar-2 notes,",
        sum(map(len, synth)),
        "synth notes,",
        sum(map(len, bass)),
        "bass notes,",
        sum(drum_counts.values()),
        "drum hits",
        drum_counts,
    )


if __name__ == "__main__":
    main()
