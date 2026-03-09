#!/usr/bin/env python3
"""
IMUSA YouTube Streams → Kodi JSON Scraper
Scrapes live/past streams from https://www.youtube.com/@IMUSATsport/streams
and outputs a Kodi-compatible JSON playlist file.

Requirements:
    pip install yt-dlp requests
"""

import json
import subprocess
import sys


CHANNEL_STREAMS_URL = "https://www.youtube.com/@IMUSATsport/streams"
OUTPUT_FILE = "imusa_kodi.json"

# Channel branding used as logo/fanart for all items
CHANNEL_LOGO = "https://yt3.googleusercontent.com/imusa-channel-logo"   # replaced at runtime
CHANNEL_FANART = "https://yt3.googleusercontent.com/imusa-channel-fanart"  # replaced at runtime


def get_channel_metadata() -> tuple[str, str]:
    """Return (logo_url, fanart_url) for the channel using yt-dlp."""
    print("[*] Fetching channel metadata …")
    cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--playlist-items", "1",          # only need one entry for channel art
        "--no-warnings",
        CHANNEL_STREAMS_URL,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        data = json.loads(result.stdout)

        # yt-dlp returns a playlist dict; channel thumbnails live in entries[0] or the root
        thumbnails = data.get("thumbnails") or (data.get("entries") or [{}])[0].get("channel_thumbnails", [])

        logo = ""
        fanart = ""

        # Try to pull channel avatar + banner from the playlist-level keys
        for t in data.get("thumbnails", []):
            url = t.get("url", "")
            if "avatar" in url or (t.get("width", 0) < 500 and url):
                logo = logo or url
            if "banner" in url or t.get("width", 0) >= 1280:
                fanart = fanart or url

        # Fallback: use the first entry's own thumbnail as logo
        entries = data.get("entries") or []
        if entries and not logo:
            entry_thumbs = sorted(entries[0].get("thumbnails", []), key=lambda x: x.get("width", 0))
            if entry_thumbs:
                logo = entry_thumbs[-1]["url"]
                fanart = entry_thumbs[-1]["url"]

        return logo, fanart
    except Exception as exc:
        print(f"[!] Could not fetch channel metadata: {exc}")
        return "", ""


def get_streams() -> list[dict]:
    """Return a list of all stream dicts with title, url, thumbnail."""
    print(f"[*] Fetching all streams from {CHANNEL_STREAMS_URL} …")
    cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--flat-playlist",
        "--no-warnings",
        CHANNEL_STREAMS_URL,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[!] yt-dlp error:\n{result.stderr}")
        sys.exit(1)

    data = json.loads(result.stdout)
    entries = data.get("entries") or []
    print(f"[*] Found {len(entries)} entries.")
    return entries


def best_thumbnail(thumbnails: list[dict]) -> str:
    """Pick the highest-resolution thumbnail URL."""
    if not thumbnails:
        return ""
    sorted_thumbs = sorted(thumbnails, key=lambda t: t.get("width", 0) or 0, reverse=True)
    return sorted_thumbs[0].get("url", "")


def build_kodi_item(entry: dict, channel_logo: str, channel_fanart: str) -> dict:
    """Convert a yt-dlp flat-playlist entry into a Kodi JSON item."""
    video_id = entry.get("id", "")
    title = entry.get("title") or entry.get("fulltitle") or video_id
    link = entry.get("url") or f"https://www.youtube.com/watch?v={video_id}"

    # Ensure link is a full YouTube watch URL
    if video_id and "youtube.com" not in link:
        link = f"https://www.youtube.com/watch?v={video_id}"

    thumbnail = best_thumbnail(entry.get("thumbnails", []))
    if not thumbnail and video_id:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

    fanart = channel_fanart or thumbnail

    return {
        "type": "item",
        "title": title,
        "link": link,
        "thumbnail": thumbnail or channel_logo,
        "fanart": fanart,
    }


def main():
    # 1. Channel art
    channel_logo, channel_fanart = get_channel_metadata()

    # 2. Stream list
    entries = get_streams()

    # 3. Build Kodi items
    items = []
    for entry in entries:
        item = build_kodi_item(entry, channel_logo, channel_fanart)
        items.append(item)
        print(f"  + {item['title'][:70]}")

    # 4. Write JSON
    kodi_json = {"items": items}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(kodi_json, fh, indent=4, ensure_ascii=False)

    print(f"\n[✓] Saved {len(items)} items → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
