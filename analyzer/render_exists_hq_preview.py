#!/usr/bin/env python3
"""Render vocal-free Exists multitrack audio from CC0 samples.

The input MIDI is used only as performance/arrangement data. Every audible
sample is loaded from samples/cc0 in this repository. The script can write a
short preview or the complete song as one stereo MP3 per instrument group plus
a mastered full-band compatibility mix.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt


SAMPLE_RATE = 44_100
TARGET_BPM = 89.84
PREVIEW_SECONDS = 75.0


@dataclass(frozen=True)
class Note:
    channel: int
    start_tick: int
    end_tick: int
    pitch: int
    velocity: int


def read_varlen(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[position]
        position += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, position


def parse_midi(path: Path) -> tuple[int, dict[int, int], list[Note]]:
    data = path.read_bytes()
    if data[:4] != b"MThd":
        raise ValueError(f"Not a Standard MIDI file: {path}")
    header_length = int.from_bytes(data[4:8], "big")
    tracks = int.from_bytes(data[10:12], "big")
    ticks_per_quarter = int.from_bytes(data[12:14], "big")
    if ticks_per_quarter & 0x8000:
        raise ValueError("SMPTE MIDI timing is not supported")

    position = 8 + header_length
    programs: dict[int, int] = {}
    notes: list[Note] = []
    active: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)

    for _ in range(tracks):
        if data[position : position + 4] != b"MTrk":
            raise ValueError("Missing MIDI track header")
        length = int.from_bytes(data[position + 4 : position + 8], "big")
        track = data[position + 8 : position + 8 + length]
        position += 8 + length

        cursor = 0
        tick = 0
        running_status: int | None = None
        while cursor < len(track):
            delta, cursor = read_varlen(track, cursor)
            tick += delta
            status = track[cursor]
            if status < 0x80:
                if running_status is None:
                    raise ValueError("Invalid running status")
                status = running_status
            else:
                cursor += 1
                if status < 0xF0:
                    running_status = status

            if status == 0xFF:
                event_type = track[cursor]
                cursor += 1
                event_length, cursor = read_varlen(track, cursor)
                cursor += event_length
                if event_type == 0x2F:
                    break
                continue
            if status in (0xF0, 0xF7):
                event_length, cursor = read_varlen(track, cursor)
                cursor += event_length
                continue

            command = status & 0xF0
            channel = status & 0x0F
            data_length = 1 if command in (0xC0, 0xD0) else 2
            values = track[cursor : cursor + data_length]
            cursor += data_length
            if command == 0xC0:
                programs[channel] = values[0]
            elif command == 0x90 and values[1] > 0:
                active[(channel, values[0])].append((tick, values[1]))
            elif command == 0x80 or (command == 0x90 and values[1] == 0):
                key = (channel, values[0])
                if active[key]:
                    start_tick, velocity = active[key].pop(0)
                    notes.append(Note(channel, start_tick, tick, values[0], velocity))

    if not notes:
        raise ValueError("MIDI contains no completed notes")
    return ticks_per_quarter, programs, sorted(notes, key=lambda note: note.start_tick)


def run_checked(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


@lru_cache(maxsize=None)
def decode_audio(path_string: str) -> np.ndarray:
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        path_string,
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        "2",
        "pipe:1",
    ]
    decoded = run_checked(command, capture=True).stdout
    audio = np.frombuffer(decoded, dtype="<f4").reshape(-1, 2).astype(np.float32)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1e-7:
        audio = audio * (0.94 / peak)
    return audio


def anchor(path: Path, pitch: int) -> tuple[int, Path]:
    return pitch, path


def build_banks(samples: Path) -> dict[str, list[tuple[int, Path]]]:
    emily: list[tuple[int, Path]] = []
    for name, pitch in (("a2", 45), ("eb3", 51), ("a3", 57), ("eb4", 63), ("a4", 69), ("eb5", 75)):
        for suffix in ("", "-rr2", "-rr3"):
            emily.append(anchor(samples / "emilyguitar" / f"{name}{suffix}.wav", pitch))
    return {
        "clean": emily,
        "electric": [
            anchor(samples / "freepats-clean" / name, pitch)
            for name, pitch in (
                ("c2.mp3", 36), ("f2.mp3", 41), ("a2.mp3", 45),
                ("c3.mp3", 48), ("e3.mp3", 52), ("g3.mp3", 55),
                ("b3.mp3", 59), ("e4.mp3", 64), ("g4.mp3", 67),
                ("b4.mp3", 71), ("d5.mp3", 74), ("gs5.mp3", 80),
                ("cs6.mp3", 85),
            )
        ],
        "bass": [
            anchor(samples / "big-little-bass" / name, pitch)
            for name, pitch in (("e2.wav", 40), ("a2.wav", 45), ("d3.wav", 50), ("g3.wav", 55), ("c4.wav", 60))
        ],
        "strings": [
            anchor(samples / "vsco2-strings" / name, pitch)
            for name, pitch in (
                ("d2.mp3", 38), ("c3.mp3", 48), ("fs3.mp3", 54),
                ("c4.mp3", 60), ("g4.mp3", 67), ("d5.mp3", 74), ("c6.mp3", 84),
            )
        ],
    }


def choose_sample(bank: list[tuple[int, Path]], pitch: int, ordinal: int) -> tuple[int, Path]:
    distance = min(abs(anchor_pitch - pitch) for anchor_pitch, _ in bank)
    candidates = [item for item in bank if abs(item[0] - pitch) == distance]
    same_pitch = [item for item in bank if item[0] == candidates[0][0]]
    return same_pitch[ordinal % len(same_pitch)]


def interpolate_channels(source: np.ndarray, positions: np.ndarray) -> np.ndarray:
    floor = np.floor(positions).astype(np.int64)
    fraction = (positions - floor).astype(np.float32)[:, None]
    floor = np.clip(floor, 0, len(source) - 2)
    return source[floor] * (1.0 - fraction) + source[floor + 1] * fraction


def pitched_note(
    source: np.ndarray,
    semitones: int,
    duration: float,
    *,
    attack: float,
    release: float,
    sustain_loop: bool,
) -> np.ndarray:
    output_frames = max(1, int((duration + release) * SAMPLE_RATE))
    playback_rate = 2.0 ** (semitones / 12.0)
    positions = np.arange(output_frames, dtype=np.float64) * playback_rate

    if sustain_loop and len(source) > int(0.75 * SAMPLE_RATE):
        loop_start = min(int(0.38 * SAMPLE_RATE), len(source) // 3)
        loop_end = max(loop_start + int(0.25 * SAMPLE_RATE), len(source) - int(0.16 * SAMPLE_RATE))
        loop_length = loop_end - loop_start
        past = positions >= loop_end
        positions[past] = loop_start + np.mod(positions[past] - loop_start, loop_length)
    else:
        valid = positions < len(source) - 1
        output_frames = max(1, int(np.count_nonzero(valid)))
        positions = positions[:output_frames]

    output = interpolate_channels(source, positions)
    envelope = np.ones(len(output), dtype=np.float32)
    attack_frames = min(len(output), max(1, int(attack * SAMPLE_RATE)))
    envelope[:attack_frames] = np.linspace(0.0, 1.0, attack_frames, dtype=np.float32)
    release_frames = min(len(output), max(1, int(release * SAMPLE_RATE)))
    envelope[-release_frames:] *= np.linspace(1.0, 0.0, release_frames, dtype=np.float32)
    return output * envelope[:, None]


def pan_audio(audio: np.ndarray, pan: float) -> np.ndarray:
    pan = float(np.clip(pan, -1.0, 1.0))
    angle = (pan + 1.0) * math.pi / 4.0
    mono = np.mean(audio, axis=1)
    return np.column_stack((mono * math.cos(angle), mono * math.sin(angle))).astype(np.float32)


def add_at(buffer: np.ndarray, clip: np.ndarray, start: int, gain: float) -> None:
    if start >= len(buffer) or start + len(clip) <= 0:
        return
    source_start = max(0, -start)
    destination_start = max(0, start)
    count = min(len(clip) - source_start, len(buffer) - destination_start)
    if count > 0:
        buffer[destination_start : destination_start + count] += clip[source_start : source_start + count] * gain


def highpass(audio: np.ndarray, frequency: float) -> np.ndarray:
    return sosfilt(butter(2, frequency, btype="highpass", fs=SAMPLE_RATE, output="sos"), audio, axis=0).astype(np.float32)


def lowpass(audio: np.ndarray, frequency: float) -> np.ndarray:
    return sosfilt(butter(2, frequency, btype="lowpass", fs=SAMPLE_RATE, output="sos"), audio, axis=0).astype(np.float32)


def soft_drive(audio: np.ndarray, amount: float) -> np.ndarray:
    denominator = math.tanh(amount)
    return (np.tanh(audio * amount) / denominator).astype(np.float32)


def stereo_delay(audio: np.ndarray, delay_seconds: float, wet: float, feedback: float = 0.18) -> np.ndarray:
    result = audio.copy()
    delay = int(delay_seconds * SAMPLE_RATE)
    if delay <= 0:
        return result
    for repeat in range(1, 4):
        offset = delay * repeat
        if offset >= len(result):
            break
        gain = wet * (feedback ** (repeat - 1))
        result[offset:, 0] += audio[:-offset, 1] * gain
        result[offset:, 1] += audio[:-offset, 0] * gain
    return result


def room_reverb(audio: np.ndarray, wet: float, seed: int) -> np.ndarray:
    if wet <= 0:
        return audio
    rng = np.random.default_rng(seed)
    length = int(0.82 * SAMPLE_RATE)
    time = np.arange(length, dtype=np.float32) / SAMPLE_RATE
    decay = np.exp(-5.2 * time)
    result = audio.copy()
    for channel in range(2):
        impulse = rng.normal(0.0, 1.0, length).astype(np.float32) * decay
        impulse[0] += 7.5
        for milliseconds, level in ((23, 1.5), (41, 1.1), (67, 0.75), (103, 0.45)):
            impulse[int(milliseconds * SAMPLE_RATE / 1000)] += level * (1 if channel == 0 else -1)
        impulse /= max(1e-6, float(np.sum(np.abs(impulse))))
        reverberated = fftconvolve(audio[:, channel], impulse, mode="full")[: len(audio)]
        result[:, channel] += reverberated.astype(np.float32) * wet * 8.0
    return result


def active_rms(audio: np.ndarray) -> float:
    mono = np.mean(audio, axis=1)
    mask = np.abs(mono) > 0.002
    if not np.any(mask):
        return 0.0
    return float(np.sqrt(np.mean(np.square(mono[mask], dtype=np.float64))))


def level_stem(audio: np.ndarray, target_db: float) -> np.ndarray:
    rms = active_rms(audio)
    if rms <= 1e-8:
        return audio
    target = 10.0 ** (target_db / 20.0)
    gain = min(8.0, target / rms)
    peak = float(np.max(np.abs(audio * gain)))
    if peak > 0.94:
        gain *= 0.94 / peak
    return (audio * gain).astype(np.float32)


def render_tonal(
    notes: list[Note],
    bank: list[tuple[int, Path]],
    tick_to_seconds,
    frames: int,
    *,
    base_gain: float,
    pan: float,
    attack: float,
    release: float,
    sustain_loop: bool,
) -> np.ndarray:
    output = np.zeros((frames, 2), dtype=np.float32)
    for ordinal, note in enumerate(notes):
        start_seconds = tick_to_seconds(note.start_tick)
        if start_seconds >= PREVIEW_SECONDS:
            continue
        duration = max(0.06, tick_to_seconds(note.end_tick) - start_seconds)
        anchor_pitch, sample_path = choose_sample(bank, note.pitch, ordinal)
        source = decode_audio(str(sample_path))
        voice = pitched_note(
            source,
            note.pitch - anchor_pitch,
            duration,
            attack=attack,
            release=release,
            sustain_loop=sustain_loop,
        )
        alternating_pan = pan + (0.025 if ordinal % 2 else -0.025)
        voice = pan_audio(voice, alternating_pan)
        velocity_gain = (note.velocity / 127.0) ** 1.45
        add_at(output, voice, int(start_seconds * SAMPLE_RATE), base_gain * velocity_gain)
    return output


def drum_sample_map(samples: Path) -> dict[str, list[Path]]:
    natural = samples / "virtuosity-drums" / "natural"
    return {
        "kick": [natural / "kick-soft.flac", natural / "kick-hard-1.flac", natural / "kick-hard-2.flac"],
        "snare": [natural / "snare-soft.flac", natural / "snare-mid.flac", natural / "snare-hard.flac"],
        "rim": [natural / "snare-rim.flac"],
        "hihat": [natural / "hihat-closed-1.flac", natural / "hihat-closed-2.flac", natural / "hihat-closed-3.flac"],
        "openhat": [natural / "hihat-open.flac"],
        "ride": [natural / "ride.flac"],
        "ridebell": [natural / "ride-bell.flac"],
        "tomhigh": [natural / "tom-high-soft.flac", natural / "tom-high-hard.flac"],
        "tomlow": [natural / "tom-low-soft.flac", natural / "tom-low-hard.flac"],
        "crash": [natural / "crash.flac"],
    }


def drum_name(pitch: int) -> str | None:
    if pitch in (35, 36):
        return "kick"
    if pitch in (38, 40):
        return "snare"
    if pitch == 37:
        return "rim"
    if pitch in (42, 44):
        return "hihat"
    if pitch == 46:
        return "openhat"
    if pitch in (41, 43, 45):
        return "tomlow"
    if pitch in (47, 48, 50):
        return "tomhigh"
    if pitch in (49, 52, 55, 57):
        return "crash"
    if pitch in (51, 59):
        return "ride"
    if pitch == 53:
        return "ridebell"
    return None


def render_drums(notes: list[Note], samples: Path, tick_to_seconds, frames: int) -> np.ndarray:
    banks = drum_sample_map(samples)
    output = np.zeros((frames, 2), dtype=np.float32)
    counters: dict[str, int] = defaultdict(int)
    pans = {"hihat": 0.24, "openhat": 0.24, "tomhigh": 0.18, "tomlow": -0.16, "ride": 0.31, "ridebell": 0.31, "crash": -0.22}
    gains = {"kick": 0.72, "snare": 0.58, "rim": 0.42, "hihat": 0.25, "openhat": 0.27, "tomhigh": 0.48, "tomlow": 0.52, "ride": 0.27, "ridebell": 0.31, "crash": 0.38}
    for note in notes:
        start_seconds = tick_to_seconds(note.start_tick)
        if start_seconds >= PREVIEW_SECONDS:
            continue
        name = drum_name(note.pitch)
        if name is None:
            continue
        choices = banks[name]
        velocity = note.velocity / 127.0
        if name in ("kick", "snare") and len(choices) == 3:
            index = 0 if velocity < 0.58 else 2 if velocity > 0.82 else 1
        else:
            index = counters[name] % len(choices)
        counters[name] += 1
        voice = decode_audio(str(choices[index])).copy()
        voice = pan_audio(voice, pans.get(name, 0.0))
        gain = gains[name] * (0.38 + 0.72 * velocity ** 1.35)
        add_at(output, voice, int(start_seconds * SAMPLE_RATE), gain)
    return output


def write_wav(path: Path, audio: np.ndarray) -> None:
    wavfile.write(path, SAMPLE_RATE, np.clip(audio, -1.0, 1.0).astype(np.float32))


def encode_mp3(source: Path, destination: Path, duration: float, *, loudnorm: bool = False) -> None:
    command = ["ffmpeg", "-y", "-v", "error", "-i", str(source)]
    audio_filter = "apad"
    if loudnorm:
        audio_filter += ",loudnorm=I=-14:LRA=9:TP=-1.2"
    command += [
        "-af", audio_filter, "-t", f"{duration:.3f}",
        "-codec:a", "libmp3lame", "-b:a", "160k", "-ar", str(SAMPLE_RATE), str(destination),
    ]
    run_checked(command)


def render(args: argparse.Namespace) -> None:
    repository = Path(args.repository).resolve()
    samples = repository / "samples" / "cc0"
    output_directory = Path(args.output).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required")

    ticks_per_quarter, programs, notes = parse_midi(Path(args.midi))
    first_tick = min(note.start_tick for note in notes)
    seconds_per_tick = 60.0 / args.bpm / ticks_per_quarter

    def tick_to_seconds(tick: int) -> float:
        return (tick - first_tick) * seconds_per_tick

    frames = int(args.seconds * SAMPLE_RATE)
    global PREVIEW_SECONDS
    PREVIEW_SECONDS = args.seconds
    banks = build_banks(samples)
    by_channel: dict[int, list[Note]] = defaultdict(list)
    for note in notes:
        by_channel[note.channel].append(note)

    print(f"MIDI channels: {programs}")
    print(f"Rendering {args.seconds:.1f}s at {args.bpm:.2f} BPM from {len(notes)} MIDI notes")

    clean = render_tonal(
        by_channel[0], banks["clean"], tick_to_seconds, frames,
        base_gain=0.20, pan=-0.16, attack=0.006, release=0.12, sustain_loop=False,
    )
    clean = room_reverb(lowpass(highpass(clean, 78), 8_200), 0.10, 11)
    clean = level_stem(clean, -22.5)

    lead_left = render_tonal(
        by_channel[4], banks["electric"], tick_to_seconds, frames,
        base_gain=0.18, pan=-0.38, attack=0.004, release=0.15, sustain_loop=False,
    )
    lead_right = render_tonal(
        by_channel[6], banks["electric"], tick_to_seconds, frames,
        base_gain=0.17, pan=0.38, attack=0.004, release=0.15, sustain_loop=False,
    )
    lead = lead_left + np.roll(lead_right, int(0.007 * SAMPLE_RATE), axis=0) * 0.92
    lead = soft_drive(lowpass(highpass(lead, 92), 5_400), 2.65)
    lead = stereo_delay(room_reverb(lead, 0.075, 22), 0.218, 0.11)
    lead = level_stem(lead, -21.5)

    bass = render_tonal(
        by_channel[15], banks["bass"], tick_to_seconds, frames,
        base_gain=0.31, pan=0.0, attack=0.008, release=0.11, sustain_loop=False,
    )
    bass = soft_drive(lowpass(highpass(bass, 34), 4_600), 1.35)
    bass = level_stem(bass, -20.8)

    strings = render_tonal(
        by_channel[5] + by_channel[7], banks["strings"], tick_to_seconds, frames,
        base_gain=0.12, pan=0.08, attack=0.075, release=0.26, sustain_loop=True,
    )
    strings = room_reverb(lowpass(highpass(strings, 145), 8_800), 0.20, 33)
    strings = level_stem(strings, -28.0)

    synth = render_tonal(
        by_channel[8], banks["strings"], tick_to_seconds, frames,
        base_gain=0.10, pan=-0.08, attack=0.028, release=0.20, sustain_loop=True,
    )
    synth = stereo_delay(room_reverb(lowpass(highpass(synth, 120), 7_000), 0.16, 44), 0.265, 0.08)
    synth = level_stem(synth, -29.5)

    drums = render_drums(by_channel[9], samples, tick_to_seconds, frames)
    drums = room_reverb(lowpass(highpass(drums, 28), 14_500), 0.055, 55)
    drums = soft_drive(drums, 1.15)
    drums = level_stem(drums, -18.8)

    stems = {
        "guitar-clean": clean,
        "guitar-lead": lead,
        "bass": bass,
        "drums": drums,
        "strings": strings,
        "synth": synth,
    }

    fade_out = min(frames, int(1.25 * SAMPLE_RATE))
    fade = np.linspace(1.0, 0.0, fade_out, dtype=np.float32)[:, None]
    for audio in stems.values():
        audio[-fade_out:] *= fade

    with tempfile.TemporaryDirectory(prefix="kc-exists-hq-") as temporary:
        temp = Path(temporary)
        for name, audio in stems.items():
            source = temp / f"{name}.wav"
            write_wav(source, audio)
            encode_mp3(source, output_directory / f"{name}.mp3", args.seconds)

        mix = clean + lead + bass + drums + strings + synth
        mix = soft_drive(mix, 1.12)
        peak = float(np.max(np.abs(mix)))
        if peak > 0.96:
            mix *= 0.96 / peak
        mix_source = temp / "full-band.wav"
        write_wav(mix_source, mix)
        encode_mp3(mix_source, output_directory / f"{args.mix_name}.mp3", args.seconds, loudnorm=True)

    metadata: dict[str, object] = {
        "title": args.title,
        "kind": args.kind,
        "duration": round(args.seconds, 1),
        "bpm": round(args.bpm, 2),
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "codec": "MP3 160 kbps",
        "vocal": False,
        "source": "CC0 instrument samples rendered from multitrack performance data",
        "stems": ["guitar-clean", "guitar-lead", "bass", "drums", "strings", "synth"],
        "fallback": f"{args.mix_name}.mp3",
        "renderVersion": "exists-full-1" if args.kind == "full" else "exists-preview-1",
    }
    if args.kind == "full":
        metadata.update({"bars": 100, "meter": "4/4"})
    manifest = output_directory / "manifest.json"
    manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(stems)} stems and full mix in {output_directory}")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--midi", required=True, help="Reference multitrack MIDI path")
    parser.add_argument("--repository", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", default="audio/exists-hq-preview")
    parser.add_argument("--seconds", type=float, default=PREVIEW_SECONDS)
    parser.add_argument("--bpm", type=float, default=TARGET_BPM)
    parser.add_argument("--mix-name", default="full-band-preview")
    parser.add_argument("--title", default="Exists – Dirantai Digelangi Rindu · Karaoke HQ Preview")
    parser.add_argument("--kind", choices=("preview", "full"), default="preview")
    return parser.parse_args()


if __name__ == "__main__":
    render(arguments())
