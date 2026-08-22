#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tab-catalog.json"
DRAFTS = ROOT / "drafts"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--youtube-offset", type=float, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.slug):
        raise SystemExit("Slug tidak valid")
    if not -600 <= args.youtube_offset <= 600:
        raise SystemExit("Offset harus antara -600 dan 600 detik")

    draft_path = DRAFTS / f"{args.slug}.json"
    if not draft_path.is_file():
        raise SystemExit(f"Draft {args.slug} tidak ditemukan atau sudah diterbitkan")
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    data_path = ROOT / draft["data"]
    source = data_path.read_text(encoding="utf-8")
    match = re.fullmatch(r"window\.KC_TAB_DATA\s*=\s*(\{.*\});\s*", source, re.S)
    if not match:
        raise SystemExit("Format data player tidak dikenali")
    player_data = json.loads(match.group(1))
    player_data["youtubeOffset"] = args.youtube_offset
    data_path.write_text("window.KC_TAB_DATA = " + json.dumps(player_data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    songs = catalog.setdefault("songs", [])
    songs[:] = [song for song in songs if song.get("slug") != args.slug]
    songs.append(draft["entry"])
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    draft_path.unlink()
    print(f"Published {args.slug} with YouTube offset {args.youtube_offset:g}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
