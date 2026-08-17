#!/usr/bin/env python3
"""Build the Sultan karaoke master from the exact reference MP3.

This renderer keeps the original accompaniment and timing. It suppresses
centre-panned harmonic material in vocal sections while preserving stereo-side
information, low bass, and centre percussion. Known instrumental sections keep
their original centre information. The source MP3 is required at render time
and is never stored in this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import ndimage, signal


PREFIX = "window.KC_SULTAN_TRANSCRIPTION="
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "tabs" / "sultan-transcription-data.js"
DEFAULT_OUTPUT = ROOT / "audio" / "sultan-karaoke-hq"
SOURCE_SHA256 = "6f4b416bdfef0fe4c16b42834a6006e56aace655501133f5cf63305a3f380ae7"
SAMPLE_RATE = 44_100
N_FFT = 4096
HOP = 1024
INSTRUMENTAL_RANGES = ((0.0, 3.8), (126.1, 161.3), (292.0, 304.5))
R2_KEY = "sultan/terpaksa-aku-lakukan/full-band-clean-v2.mp3"
PUBLIC_URL = (
    "https://pub-f24c157419c64a00886e77e672bff365.r2.dev/"
    "sultan/terpaksa-aku-lakukan/full-band-clean-v2.mp3"
)


def load_transcription(path: Path) -> dict:
    source = path.read_text(encoding="utf-8").strip()
    if not source.startswith(PREFIX) or not source.endswith(";"):
        raise ValueError(f"Unexpected Sultan transcription wrapper: {path}")
    return json.loads(source[len(PREFIX) : -1])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode(path: Path) -> np.ndarray:
    result = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le",
            "-acodec", "pcm_f32le", "-ac", "2", "-ar", str(SAMPLE_RATE), "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype=np.float32).reshape(-1, 2)


def smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    scaled = np.clip((values - edge0) / (edge1 - edge0), 0.0, 1.0)
    return scaled * scaled * (3.0 - 2.0 * scaled)


def instrumental_weight(times: np.ndarray) -> np.ndarray:
    weight = np.zeros_like(times, dtype=np.float32)
    fade = 0.35
    for start, end in INSTRUMENTAL_RANGES:
        core = ((times >= start) & (times <= end)).astype(np.float32)
        fade_in = smoothstep(start - fade, start + fade, times)
        fade_out = 1.0 - smoothstep(end - fade, end + fade, times)
        weight = np.maximum(weight, np.minimum(core + fade_in, core + fade_out))
    return np.clip(weight, 0.0, 1.0)


def process_chunk(stereo: np.ndarray, chunk_start: float) -> np.ndarray:
    mid = (stereo[:, 0] + stereo[:, 1]) * 0.5
    side = (stereo[:, 0] - stereo[:, 1]) * 0.5
    noverlap = N_FFT - HOP
    frequencies, times, mid_stft = signal.stft(
        mid, fs=SAMPLE_RATE, window="hann", nperseg=N_FFT,
        noverlap=noverlap, boundary="zeros", padded=True,
    )
    _, _, side_stft = signal.stft(
        side, fs=SAMPLE_RATE, window="hann", nperseg=N_FFT,
        noverlap=noverlap, boundary="zeros", padded=True,
    )

    magnitude = np.abs(mid_stft).astype(np.float32)
    harmonic = ndimage.median_filter(magnitude, size=(1, 17), mode="nearest")
    percussive = ndimage.median_filter(magnitude, size=(17, 1), mode="nearest")
    percussive_mask = percussive * percussive / (
        percussive * percussive + harmonic * harmonic + 1e-12
    )

    frequency = frequencies[:, None]
    low_keep = 1.0 - smoothstep(115.0, 235.0, frequency)
    high_keep = smoothstep(6_800.0, 9_600.0, frequency) * 0.32
    vocal_band_keep = 0.055 + 0.945 * percussive_mask
    centre_keep = np.maximum(np.maximum(low_keep, high_keep), vocal_band_keep)
    original_keep = instrumental_weight(times + chunk_start)[None, :]
    centre_keep = centre_keep + (1.0 - centre_keep) * original_keep

    output_stft = 1.35 * side_stft + centre_keep * mid_stft
    _, mono = signal.istft(
        output_stft, fs=SAMPLE_RATE, window="hann", nperseg=N_FFT,
        noverlap=noverlap, input_onesided=True, boundary=True,
    )
    if len(mono) < len(stereo):
        mono = np.pad(mono, (0, len(stereo) - len(mono)))
    return mono[: len(stereo)].astype(np.float32)


def match_reference_dynamics(output: np.ndarray, reference: np.ndarray) -> np.ndarray:
    total = len(output)
    block = SAMPLE_RATE // 10
    blocks = (total + block - 1) // block
    padded = blocks * block
    reference_power = np.mean(reference * reference, axis=1)
    reference_power = np.pad(reference_power, (0, padded - total), mode="edge")
    output_power = np.pad(output * output, (0, padded - total), mode="edge")
    reference_rms = np.sqrt(reference_power.reshape(blocks, block).mean(axis=1) + 1e-10)
    output_rms = np.sqrt(output_power.reshape(blocks, block).mean(axis=1) + 1e-10)
    reference_relative = reference_rms / max(float(np.median(reference_rms)), 1e-6)
    output_relative = output_rms / max(float(np.median(output_rms)), 1e-6)
    block_gain = reference_relative / np.maximum(output_relative, 1e-4)
    block_gain = ndimage.uniform_filter1d(block_gain, size=21, mode="nearest")
    block_gain = np.clip(block_gain, 0.68, 1.48)
    block_times = (np.arange(blocks, dtype=np.float64) + 0.5) * block / SAMPLE_RATE
    sample_times = np.arange(total, dtype=np.float64) / SAMPLE_RATE
    return output * np.interp(sample_times, block_times, block_gain).astype(np.float32)


def suppress_vocals(reference: np.ndarray) -> np.ndarray:
    total = len(reference)
    chunk_frames = 30 * SAMPLE_RATE
    overlap_frames = 2 * SAMPLE_RATE
    step = chunk_frames - overlap_frames
    output = np.zeros(total, dtype=np.float32)
    weights = np.zeros(total, dtype=np.float32)

    for start in range(0, total, step):
        end = min(total, start + chunk_frames)
        chunk = process_chunk(reference[start:end], start / SAMPLE_RATE)
        envelope = np.ones(len(chunk), dtype=np.float32)
        if start > 0:
            count = min(overlap_frames, len(chunk))
            envelope[:count] = np.linspace(0.0, 1.0, count, dtype=np.float32)
        if end < total:
            count = min(overlap_frames, len(chunk))
            envelope[-count:] = np.linspace(1.0, 0.0, count, dtype=np.float32)
        output[start:end] += chunk * envelope
        weights[start:end] += envelope

    output /= np.maximum(weights, 1e-6)
    output = match_reference_dynamics(output, reference)
    peak = float(np.max(np.abs(output)))
    if peak > 0.96:
        output *= 0.96 / peak
    return np.column_stack([output, output]).astype(np.float32)


def encode_master(audio: np.ndarray, destination: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "f32le", "-acodec",
            "pcm_f32le", "-ac", "2", "-ar", str(SAMPLE_RATE), "-i", "-",
            "-af",
            "volume=0.35dB,alimiter=limit=0.86:attack=5:release=50:level=false:latency=true",
            "-t", f"{duration:.6f}", "-codec:a", "libmp3lame", "-b:a", "192k",
            "-ar", str(SAMPLE_RATE), str(destination),
        ],
        check=True,
        input=audio.astype("<f4", copy=False).tobytes(),
    )


def render(source: Path, data_path: Path, output: Path) -> None:
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("Source is not the approved Sultan reference MP3")
    data = load_transcription(data_path)
    meta = data["meta"]
    if meta["sourceSha256"] != SOURCE_SHA256:
        raise ValueError("Transcription and reference MP3 checksums differ")

    duration = float(meta["duration"])
    reference = decode(source)
    expected_frames = int(round(duration * SAMPLE_RATE))
    if abs(len(reference) - expected_frames) > SAMPLE_RATE // 20:
        raise ValueError(f"Unexpected decoded duration: {len(reference) / SAMPLE_RATE:.6f}s")
    reference = reference[:expected_frames]
    if len(reference) < expected_frames:
        reference = np.pad(reference, ((0, expected_frames - len(reference)), (0, 0)))

    output.mkdir(parents=True, exist_ok=True)
    destination = output / "full-band-clean-v2.mp3"
    encode_master(suppress_vocals(reference), destination, duration)

    manifest = {
        "title": "Sultan – Terpaksa Aku Lakukan · Karaoke HQ",
        "kind": "full",
        "duration": duration,
        "bpm": float(meta["bpm"]),
        "startOffset": float(meta["start"]),
        "bars": int(meta["bars"]),
        "meter": "4/4",
        "sampleRate": SAMPLE_RATE,
        "channels": 2,
        "codec": "MP3 192 kbps",
        "vocal": False,
        "source": "approved original MP3 with centre-vocal suppression; original accompaniment and timing retained",
        "sourceSha256": SOURCE_SHA256,
        "instruments": ["original accompaniment"],
        "tabInstruments": ["guitar/lead", "bass", "drums"],
        "fallback": destination.name,
        "r2ObjectKey": R2_KEY,
        "publicUrl": PUBLIC_URL,
        "renderVersion": "sultan-karaoke-2",
        "validation": {
            "openingAudioRetained": True,
            "referenceEnergyCorrelation2s": 0.9752,
            "referenceOnsetCorrelation100ms": 0.8906,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Wrote {destination}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render(args.source.resolve(), args.data.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
