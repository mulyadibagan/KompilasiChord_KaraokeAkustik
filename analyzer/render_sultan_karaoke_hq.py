#!/usr/bin/env python3
"""Render Sultan – Terpaksa Aku Lakukan as a vocal-free HQ backing track.

Only the validated MP3-derived guitar/lead, bass, and drum events are rendered.
No rhythm-guitar or other undetected part is invented. Every audible source is
loaded from the repository's CC0 sample bank.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import render_exists_hq_preview as engine


PREFIX = "window.KC_SULTAN_TRANSCRIPTION="
DEFAULT_DATA = Path(__file__).resolve().parents[1] / "tabs" / "sultan-transcription-data.js"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "audio" / "sultan-karaoke-hq"


def load_transcription(path: Path) -> dict:
    source = path.read_text(encoding="utf-8").strip()
    if not source.startswith(PREFIX) or not source.endswith(";"):
        raise ValueError(f"Unexpected Sultan transcription wrapper: {path}")
    return json.loads(source[len(PREFIX) : -1])


def section_for_bars(data: dict) -> list[str]:
    labels: list[str] = []
    for section in data["sections"]:
        labels.extend([section["key"]] * section["length"])
    if len(labels) != data["meta"]["bars"]:
        raise ValueError("Section lengths do not match the transcription bar count")
    return labels


def note_velocity(section: str, base: int) -> int:
    if section.startswith("reff"):
        return min(118, base + 15)
    if section.startswith("pre") or section in {"interlude", "outro"}:
        return min(112, base + 8)
    return base


def build_notes(data: dict) -> tuple[list[engine.Note], list[engine.Note], list[engine.Note]]:
    sections = section_for_bars(data)
    lead: list[engine.Note] = []
    bass: list[engine.Note] = []
    drums: list[engine.Note] = []

    for bar, events in enumerate(data["lead"]):
        velocity = note_velocity(sections[bar], 91)
        for slot, duration, pitch in events:
            start = bar * 16 + slot
            lead.append(engine.Note(0, start, start + duration, pitch, velocity))

    for bar, events in enumerate(data["bass"]):
        velocity = note_velocity(sections[bar], 88)
        for slot, duration, pitch in events:
            start = bar * 16 + slot
            bass.append(engine.Note(1, start, start + duration, pitch, velocity))

    drum_pitch = {"k": 36, "s": 38, "h": 42, "c": 49, "t": 45}
    drum_velocity = {"k": 104, "s": 101, "h": 78, "c": 112, "t": 96}
    for bar, hits in enumerate(data["drums"]):
        chorus = sections[bar].startswith("reff")
        for kind, pitch in drum_pitch.items():
            for slot in hits[kind]:
                start = bar * 16 + slot
                velocity = drum_velocity[kind] + (7 if chorus and kind in {"k", "s", "c"} else 0)
                drums.append(engine.Note(9, start, start + 1, pitch, min(122, velocity)))

    return lead, bass, drums


def encode_master(source: Path, destination: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-af",
            "apad,loudnorm=I=-14:LRA=8:TP=-1.2",
            "-t",
            f"{duration:.6f}",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            "-ar",
            str(engine.SAMPLE_RATE),
            str(destination),
        ],
        check=True,
    )


def render(repository: Path, data_path: Path, output: Path) -> None:
    data = load_transcription(data_path)
    meta = data["meta"]
    bpm = float(meta["bpm"])
    duration = float(meta["duration"])
    start_offset = float(meta["start"])
    frames = int(round(duration * engine.SAMPLE_RATE))
    seconds_per_slot = 15.0 / bpm
    engine.PREVIEW_SECONDS = duration

    lead_notes, bass_notes, drum_notes = build_notes(data)
    banks = engine.build_banks(repository / "samples" / "cc0")

    def tick_to_seconds(tick: int) -> float:
        return start_offset + tick * seconds_per_slot

    print(
        f"Rendering {duration:.3f}s: {len(lead_notes)} guitar/lead notes, "
        f"{len(bass_notes)} bass notes, {len(drum_notes)} drum hits"
    )

    lead = engine.render_tonal(
        lead_notes,
        banks["electric"],
        tick_to_seconds,
        frames,
        base_gain=0.19,
        pan=0.04,
        attack=0.004,
        release=0.16,
        sustain_loop=False,
    )
    lead = engine.soft_drive(engine.lowpass(engine.highpass(lead, 88), 6_200), 1.75)
    lead = engine.stereo_delay(engine.room_reverb(lead, 0.085, 71), 0.205, 0.10)
    lead = engine.level_stem(lead, -21.4)

    bass = engine.render_tonal(
        bass_notes,
        banks["bass"],
        tick_to_seconds,
        frames,
        base_gain=0.32,
        pan=0.0,
        attack=0.008,
        release=0.12,
        sustain_loop=False,
    )
    bass = engine.soft_drive(engine.lowpass(engine.highpass(bass, 34), 4_500), 1.32)
    bass = engine.level_stem(bass, -20.4)

    drums = engine.render_drums(drum_notes, repository / "samples" / "cc0", tick_to_seconds, frames)
    drums = engine.room_reverb(engine.lowpass(engine.highpass(drums, 28), 14_500), 0.055, 83)
    drums = engine.soft_drive(drums, 1.13)
    drums = engine.level_stem(drums, -18.7)

    fade_frames = min(frames, int(1.35 * engine.SAMPLE_RATE))
    fade = np.linspace(1.0, 0.0, fade_frames, dtype=np.float32)[:, None]
    lead[-fade_frames:] *= fade
    bass[-fade_frames:] *= fade
    drums[-fade_frames:] *= fade

    mix = engine.soft_drive(lead + bass + drums, 1.10)
    peak = float(np.max(np.abs(mix)))
    if peak > 0.96:
        mix *= 0.96 / peak

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kc-sultan-hq-") as temporary:
        wav = Path(temporary) / "full-band-clean.wav"
        engine.write_wav(wav, mix)
        encode_master(wav, output / "full-band-clean.mp3", duration)

    manifest = {
        "title": "Sultan – Terpaksa Aku Lakukan · Karaoke HQ",
        "kind": "full",
        "duration": duration,
        "bpm": bpm,
        "startOffset": start_offset,
        "bars": int(meta["bars"]),
        "meter": "4/4",
        "sampleRate": engine.SAMPLE_RATE,
        "channels": 2,
        "codec": "MP3 192 kbps",
        "vocal": False,
        "source": "CC0 samples rendered only from validated MP3-derived instrument events",
        "instruments": ["guitar/lead", "bass", "drums"],
        "fallback": "full-band-clean.mp3",
        "r2ObjectKey": "sultan/terpaksa-aku-lakukan/full-band-clean.mp3",
        "publicUrl": "https://pub-f24c157419c64a00886e77e672bff365.r2.dev/sultan/terpaksa-aku-lakukan/full-band-clean.mp3",
        "renderVersion": "sultan-karaoke-1",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output / 'full-band-clean.mp3'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    render(Path(args.repository).resolve(), Path(args.data).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
