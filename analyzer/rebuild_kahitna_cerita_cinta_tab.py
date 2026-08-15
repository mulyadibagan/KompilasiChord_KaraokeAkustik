#!/usr/bin/env python3
"""Build the Kahitna "Cerita Cinta" tab from isolated reference-audio stems.

The input CSV files are produced independently for each instrumental stem.  This
script only quantizes detected events; it never fills empty bars from chord names
or section labels.
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


BPM = 113.238888
START = 8.218379
DURATION = 264.568163
BARS = 121
SLOT_SECONDS = 15 / BPM
BAR_SECONDS = 240 / BPM
SOURCE_SHA256 = "7e27a19edfa84e3778ff9547a8aea44d4e5410f41ed141d0f21996ae5acb3735"
GUITAR_OPEN = (64, 59, 55, 50, 45, 40)  # high E through low E

SECTIONS = [
    {"key": "intro", "label": "Intro", "length": 5},
    {"key": "verse1a", "label": "Bait 1A", "length": 12},
    {"key": "verse1b", "label": "Bait 1B", "length": 6},
    {"key": "pre1", "label": "Pra-Reff 1", "length": 7},
    {"key": "chorus1", "label": "Reff 1", "length": 11},
    {"key": "transition", "label": "Transisi", "length": 3},
    {"key": "verse2a", "label": "Bait 2A", "length": 10},
    {"key": "verse2b", "label": "Bait 2B", "length": 8},
    {"key": "pre2", "label": "Pra-Reff 2", "length": 12},
    {"key": "bridge", "label": "Bridge / Interlude", "length": 11},
    {"key": "chorus2", "label": "Reff 2", "length": 11},
    {"key": "final1", "label": "Reff Akhir A", "length": 11},
    {"key": "final2", "label": "Reff Akhir B", "length": 11},
    {"key": "outro", "label": "Outro", "length": 3},
]

# Beat-synchronous chord context estimated from the isolated guitar and bass.
# These labels are display-only and are never used by any instrument builder.
CHORD_TOKENS = """
C# F#>C# C#>F# F#>C# F#>C# C#>F# A#m>F# B>G#m F#>A#m F#>B
F#>C# C# F# C#>B C#>G#m F#>A#m G#m C#>F# F# B>C# C#>F# A#m>G#m
G#m>C# D#m F# F# D#m>F# G#m G#m>B B F# F#>B C#>F# F#>A#m F#>B
C#>F# F# B>C# F# G#m>F# F#>C# F# F# C#>F# F#>C# B>F# G#m>F# F#
G#m>B F# F#>B B>C# F# A#m>G#m C#>D#m D#m>F# F# F#>B F#>E#dim G#m
B B>F# F# B>C# F# F# F#>C# F# F# F# F#>G#m F# C#>F# F# B A#m>G#m
G#m>B B>A#m C# G#m>D#m G#m G#m>B C# A#m>B B>F# F# F# C# F#>C# E#dim>F#
C#>F# F# F#>C# F# G#m>F# F# F# A#m>B C#>F# F# F#>B F# F#>A#m F#>C#
D#m>F# G#m>F# F#>C# F# A#m>C# C#>F# F#>A#m F#>C# C#>F# F# F#>C# F#
A#m>F# C# F# F# C#>D#m
""".split()
assert len(CHORD_TOKENS) == BARS
CHORDS = [token.split(">") for token in CHORD_TOKENS]


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
    """Choose the largest physically playable six-string voicing for one onset."""
    strongest = sorted(candidates, key=lambda item: item["velocity"], reverse=True)[:7]
    for size in range(min(6, len(strongest)), 0, -1):
        best = None
        for subset in itertools.combinations(strongest, size):
            notes = sorted(subset, key=lambda item: item["midi"], reverse=True)
            for strings in itertools.combinations(range(6), size):
                frets = [note["midi"] - GUITAR_OPEN[string] for note, string in zip(notes, strings)]
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
                    assigned = []
                    for note, string, fret in zip(notes, strings, frets):
                        assigned.append({**note, "string": string, "fret": fret})
                    best = (score, assigned)
        if best is not None:
            return best[1]
    return []


def build_guitar(csv_path: Path, stem_path: Path) -> list[list[list[int]]]:
    buckets = read_candidates(
        csv_path,
        velocity_min=40,
        midi_min=40,
        midi_max=84,
        rms=bar_rms_db(stem_path),
        rms_min=-55,
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
        velocity_min=45,
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
        if rms[bar] < -50:
            continue
        for instrument in event["instruments"]:
            key = name_map.get(instrument)
            if key:
                output[bar][key].add(slot)
    return [
        {key: sorted(slots) for key, slots in bar.items()}
        for bar in output
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stems", type=Path, required=True)
    parser.add_argument("--guitar-csv", type=Path, required=True)
    parser.add_argument("--bass-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    assert sum(section["length"] for section in SECTIONS) == BARS
    assert len(CHORDS) == BARS
    guitar = build_guitar(args.guitar_csv, args.stems / "guitar.wav")
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
            "start": round(START, 6),
            "duration": DURATION,
            "grid": "1/16",
            "bars": BARS,
            "method": "htdemucs_6s stem separation + Basic Pitch polyphonic note analysis + DrumScript onset and spectral classification + source-timed 1/16 quantization + no generated fallback",
            "preservePitch": True,
            "silencePolicy": "preserve",
            "vocalTrack": False,
            "sourceSha256": SOURCE_SHA256,
            "detectedInstruments": ["guitar_electric", "bass", "drums"],
            "excludedStems": ["vocals", "piano_residual", "other_residual"],
            "guitarTracks": 1,
            "mixStereoCorrelation": 0.998701,
            "guitarStereoCorrelation": 0.999287,
            "pianoResidualRmsDb": -94.76,
            "otherResidualRmsDb": -89.43,
            "drumComponents": [
                component_names[key] for key, count in drum_counts.items() if count
            ],
        },
        "sections": SECTIONS,
        "chords": CHORDS,
        "guitar": guitar,
        "bass": bass,
        "drums": drums,
    }
    source = "window.KC_KAHITNA_CERITA_CINTA_TRANSCRIPTION=" + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"
    args.output.write_text(source, encoding="utf-8")
    print(
        "Cerita Cinta rebuilt:",
        sum(map(len, guitar)),
        "guitar notes,",
        sum(map(len, bass)),
        "bass notes,",
        sum(drum_counts.values()),
        "drum hits",
    )


if __name__ == "__main__":
    main()
