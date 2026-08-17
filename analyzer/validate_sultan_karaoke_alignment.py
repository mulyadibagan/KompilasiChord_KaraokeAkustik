#!/usr/bin/env python3
"""Measure whether the Sultan karaoke master follows the approved MP3."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter1d


SOURCE_SHA256 = "6f4b416bdfef0fe4c16b42834a6006e56aace655501133f5cf63305a3f380ae7"
SAMPLE_RATE = 11_025


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
            "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype=np.float32)


def energy(audio: np.ndarray, seconds: float) -> np.ndarray:
    window = max(1, int(SAMPLE_RATE * seconds))
    envelope = np.sqrt(uniform_filter1d(audio * audio, size=window, mode="nearest") + 1e-12)
    return envelope[::220]


def onset(audio: np.ndarray, seconds: float) -> np.ndarray:
    frames = np.lib.stride_tricks.sliding_window_view(audio, 512)[::256]
    frame_energy = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    novelty = np.maximum(
        0.0,
        np.diff(np.log(frame_energy + 1e-8), prepend=np.log(frame_energy[0] + 1e-8)),
    )
    window = max(1, int(seconds * SAMPLE_RATE / 256))
    return uniform_filter1d(novelty, size=window, mode="nearest")


def correlation(left: np.ndarray, right: np.ndarray) -> float:
    count = min(len(left), len(right))
    return float(np.corrcoef(left[:count], right[:count])[0, 1])


def best_energy_lag(reference: np.ndarray, karaoke: np.ndarray) -> float:
    left = energy(reference, 0.5)
    right = energy(karaoke, 0.5)
    count = min(len(left), len(right))
    left = left[:count]
    right = right[:count]
    best_lag = 0
    best_score = -1.0
    for lag in range(-100, 101):
        if lag < 0:
            score = correlation(left[-lag:], right[: count + lag])
        elif lag > 0:
            score = correlation(left[: count - lag], right[lag:])
        else:
            score = correlation(left, right)
        if score > best_score:
            best_score = score
            best_lag = lag
    return best_lag * 220 / SAMPLE_RATE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--karaoke", type=Path, required=True)
    args = parser.parse_args()

    assert sha256(args.reference) == SOURCE_SHA256
    reference = decode(args.reference)
    karaoke = decode(args.karaoke)
    duration_difference = abs(len(reference) - len(karaoke)) / SAMPLE_RATE
    energy_correlation = correlation(energy(reference, 2.0), energy(karaoke, 2.0))
    onset_correlation = correlation(onset(reference, 0.1), onset(karaoke, 0.1))
    lag = best_energy_lag(reference, karaoke)
    opening = karaoke[: int(0.5 * SAMPLE_RATE)]
    opening_rms = float(np.sqrt(np.mean(opening * opening)))

    assert duration_difference < 0.08, duration_difference
    assert energy_correlation >= 0.97, energy_correlation
    assert onset_correlation >= 0.89, onset_correlation
    assert abs(lag) < 0.03, lag
    assert opening_rms > 0.05, opening_rms
    print(
        "Sultan karaoke aligned:",
        f"energy={energy_correlation:.4f},",
        f"onset={onset_correlation:.4f},",
        f"lag={lag:+.3f}s,",
        f"opening_rms={opening_rms:.4f}",
    )


if __name__ == "__main__":
    main()
