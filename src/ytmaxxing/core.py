"""Shared logic for the MCP server and the CLI."""

from __future__ import annotations

from .library import Library
from .youtube import fetch_metadata, fetch_transcript, video_id


def ensure_video(lib: Library, url: str, languages: list[str] | None = None,
                 refresh: bool = False) -> tuple[dict, list[str]]:
    """Fetch a video into the library if needed. Returns (meta, transcript parts)."""
    vid = video_id(url)
    meta = lib.load_meta(vid)
    parts = lib.transcript_parts(vid)
    if refresh or not meta or not parts:
        video = fetch_metadata(vid)
        tr = fetch_transcript(vid, languages)
        lib.save_transcript(video, tr)
        meta = lib.load_meta(vid)
        parts = lib.transcript_parts(vid)
    return meta, parts


def header(meta: dict, part: int, total: int) -> str:
    from .youtube import timestamp

    length = timestamp(meta["duration"]) if meta.get("duration") else "unknown"
    lines = [
        f"# {meta['title']}",
        f"Channel: {meta['channel']} | Published: {meta.get('upload_date') or 'unknown'} | "
        f"Length: {length} | Transcript: {meta.get('source')} ({meta.get('language')})",
        f"Link: {meta['url']}",
        f"Transcript part {part} of {total}.",
    ]
    if meta.get("chapters") and part == 1:
        from .youtube import timestamp as ts

        lines.append("Chapters: " + " · ".join(f"{ts(c['start'])} {c['title']}" for c in meta["chapters"]))
    return "\n".join(lines)
