"""Everything that talks to YouTube: video IDs, metadata, transcripts, playlists.

Transcripts come from captions first (fast, free). If a video has no captions or
YouTube blocks the request, ytmaxxing can fall back to transcribing the audio
locally with Whisper: faster-whisper (the `whisper` extra) or, if that isn't
installed, a whisper.cpp `whisper-cli` already on the machine with a ggml model.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import httpx

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class YtmaxxingError(Exception):
    """A problem worth showing to the user as-is."""


# ---------------------------------------------------------------- video IDs

def video_id(url_or_id: str) -> str:
    """Return the 11-character video ID from any common YouTube link (or a bare ID)."""
    s = url_or_id.strip()
    if ID_RE.match(s):
        return s
    u = urlparse(s if "://" in s else "https://" + s)
    host = (u.hostname or "").lower()
    for prefix in ("www.", "m.", "music."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    cand = ""
    if host == "youtu.be":
        cand = u.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "youtube-nocookie.com"):
        q = parse_qs(u.query)
        if "v" in q:
            cand = q["v"][0]
        else:
            m = re.match(r"^/(?:shorts|live|embed|v)/([^/?#]+)", u.path)
            cand = m.group(1) if m else ""
    if ID_RE.match(cand):
        return cand
    raise YtmaxxingError(f"Couldn't find a YouTube video ID in: {url_or_id}")


def watch_url(vid: str, seconds: float | None = None) -> str:
    return f"https://youtu.be/{vid}" + (f"?t={int(seconds)}" if seconds else "")


def timestamp(seconds: float) -> str:
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------- metadata

@dataclass
class Video:
    id: str
    title: str = "Unknown title"
    channel: str = "Unknown channel"
    upload_date: str | None = None  # YYYY-MM-DD
    duration: int | None = None  # seconds
    description: str = ""
    chapters: list[dict] = field(default_factory=list)  # [{"start": float, "title": str}]

    @property
    def url(self) -> str:
        return watch_url(self.id)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "channel": self.channel, "url": self.url,
            "upload_date": self.upload_date, "duration": self.duration,
            "description": self.description, "chapters": self.chapters,
        }


class _QuietLogger:
    """yt-dlp must never print to stdout: over MCP stdio that would corrupt the protocol."""

    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _ydl_opts(**extra) -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True, "noplaylist": True,
            "logger": _QuietLogger()}
    proxy = os.environ.get("YTMAXXING_PROXY")
    if proxy:
        opts["proxy"] = proxy
    opts.update(extra)
    return opts


def fetch_metadata(vid: str) -> Video:
    """Title, channel, date, duration and chapters. Falls back to oEmbed (title + channel only)."""
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
            info = ydl.extract_info(watch_url(vid), download=False)
        d = info.get("upload_date")
        return Video(
            id=vid,
            title=info.get("title") or "Unknown title",
            channel=info.get("channel") or info.get("uploader") or "Unknown channel",
            upload_date=f"{d[:4]}-{d[4:6]}-{d[6:]}" if d and len(d) == 8 else None,
            duration=info.get("duration"),
            description=(info.get("description") or "")[:2000],
            chapters=[{"start": c.get("start_time", 0), "title": c.get("title", "")}
                      for c in (info.get("chapters") or [])],
        )
    except Exception:
        pass
    try:
        r = httpx.get("https://www.youtube.com/oembed",
                      params={"url": watch_url(vid), "format": "json"}, timeout=10)
        if r.status_code == 200:
            j = r.json()
            return Video(id=vid, title=j.get("title", "Unknown title"),
                         channel=j.get("author_name", "Unknown channel"))
    except Exception:
        pass
    return Video(id=vid)


# ---------------------------------------------------------------- transcripts

@dataclass
class Line:
    start: float
    text: str


@dataclass
class Transcript:
    lines: list[Line]
    language: str
    source: str  # "captions" | "auto-captions" | "whisper"


def _preferred_languages(languages: list[str] | None) -> list[str]:
    if languages:
        return languages
    env = os.environ.get("YTMAXXING_LANGUAGES")
    return [x.strip() for x in env.split(",") if x.strip()] if env else ["en"]


def _transcript_api():
    from youtube_transcript_api import YouTubeTranscriptApi

    proxy = os.environ.get("YTMAXXING_PROXY")
    if proxy:
        from youtube_transcript_api.proxies import GenericProxyConfig

        return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy))
    return YouTubeTranscriptApi()


WHISPER_HINT = ("install local transcription with: pip install 'ytmaxxing[whisper]', "
                "or install whisper.cpp (e.g. `brew install whisper-cpp`) and put a ggml model in ~/.cache/whisper")

# Preferred whisper.cpp models, best first; any other ggml-*.bin in the folder is used after these.
_GGML_PREFERENCE = ("ggml-large-v3-turbo.bin", "ggml-large-v3.bin", "ggml-medium.bin", "ggml-small.bin",
                    "ggml-base.bin")


def faster_whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def _whisper_cpp_binary() -> str | None:
    explicit = os.environ.get("YTMAXXING_WHISPER_CPP")
    if explicit:
        return explicit if Path(explicit).is_file() else shutil.which(explicit)
    return shutil.which("whisper-cli")


def _whisper_cpp_model() -> Path | None:
    explicit = os.environ.get("YTMAXXING_WHISPER_CPP_MODEL")
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_file() else None
    folder = Path(os.environ.get("YTMAXXING_WHISPER_CPP_DIR", "~/.cache/whisper")).expanduser()
    if not folder.is_dir():
        return None
    for name in _GGML_PREFERENCE:
        if (folder / name).is_file():
            return folder / name
    others = sorted(p for p in folder.glob("ggml-*.bin") if p.is_file())
    return others[0] if others else None


def whisper_cpp_available() -> bool:
    """whisper.cpp needs its binary, a ggml model and ffmpeg (to turn the audio into 16 kHz WAV)."""
    return bool(_whisper_cpp_binary() and _whisper_cpp_model() and shutil.which("ffmpeg"))


def whisper_available() -> bool:
    return faster_whisper_available() or whisper_cpp_available()


def fetch_captions(vid: str, languages: list[str] | None = None) -> Transcript:
    from youtube_transcript_api import NoTranscriptFound

    prefs = _preferred_languages(languages)
    listing = _transcript_api().list(vid)
    available = [t.language_code for t in listing]
    if not available:
        raise YtmaxxingError("This video has no captions.")
    # Human captions in a preferred language beat auto captions; any language beats nothing.
    try:
        chosen = listing.find_manually_created_transcript(prefs)
    except NoTranscriptFound:
        try:
            chosen = listing.find_generated_transcript(prefs)
        except NoTranscriptFound:
            chosen = listing.find_transcript(available)
    fetched = chosen.fetch()
    lines = [Line(s.start, " ".join(s.text.split())) for s in fetched if s.text.strip()]
    return Transcript(lines, chosen.language_code, "auto-captions" if chosen.is_generated else "captions")


def _decode_audio(path: str):
    """Decode to 16 kHz mono float32 ourselves: faster-whisper's own decoder breaks on newer PyAV."""
    import av
    import numpy as np

    chunks = []
    with av.open(path) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(stream):
            chunks.extend(f.to_ndarray() for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray() for f in resampler.resample(None))
    if not chunks:
        raise YtmaxxingError("The downloaded audio was empty.")
    return np.concatenate(chunks, axis=1).flatten().astype(np.float32) / 32768.0


def _download_audio(vid: str, folder: str) -> str:
    import yt_dlp

    opts = _ydl_opts(skip_download=False, format="bestaudio/best", outtmpl=os.path.join(folder, "%(id)s.%(ext)s"))
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(watch_url(vid), download=True)
        return ydl.prepare_filename(info)


def _transcribe_faster_whisper(path: str) -> Transcript:
    from faster_whisper import WhisperModel

    model = WhisperModel(os.environ.get("YTMAXXING_WHISPER_MODEL", "small"), device="auto", compute_type="default")
    segments, meta = model.transcribe(_decode_audio(path), vad_filter=True)
    lines = [Line(s.start, s.text.strip()) for s in segments if s.text.strip()]
    return Transcript(lines, meta.language, "whisper")


def _parse_whisper_cpp_json(data: dict) -> Transcript:
    """Read whisper-cli's `-oj` output: segments with millisecond offsets, plus the detected language."""
    lines = []
    for seg in data.get("transcription", []):
        text = " ".join(str(seg.get("text", "")).split())
        if text:
            lines.append(Line(seg.get("offsets", {}).get("from", 0) / 1000.0, text))
    return Transcript(lines, data.get("result", {}).get("language") or "und", "whisper")


def _transcribe_whisper_cpp(path: str, folder: str) -> Transcript:
    """Transcribe with a whisper.cpp binary already on the machine. Output goes to files, never stdout."""
    wav = os.path.join(folder, "audio16k.wav")
    conv = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-ar", "16000", "-ac", "1", wav],
                          capture_output=True, text=True)
    if conv.returncode != 0:
        raise YtmaxxingError(f"ffmpeg couldn't convert the audio: {conv.stderr.strip()[-300:]}")
    base = os.path.join(folder, "transcript")
    threads = str(min(8, os.cpu_count() or 4))
    run = subprocess.run([_whisper_cpp_binary(), "-m", str(_whisper_cpp_model()), "-f", wav, "-l", "auto",
                          "-t", threads, "-oj", "-of", base], capture_output=True, text=True)
    if run.returncode != 0 or not os.path.exists(base + ".json"):
        raise YtmaxxingError(f"whisper.cpp failed: {(run.stderr or run.stdout).strip()[-300:]}")
    with open(base + ".json", encoding="utf-8", errors="replace") as f:
        return _parse_whisper_cpp_json(json.load(f))


def transcribe_with_whisper(vid: str) -> Transcript:
    """Download the audio and transcribe it locally. Slower, but works without captions.
    Uses faster-whisper when installed, otherwise a local whisper.cpp."""
    if not whisper_available():
        raise YtmaxxingError(f"Local transcription isn't set up. To use it, {WHISPER_HINT}.")
    engine = _whisper_engine()
    with tempfile.TemporaryDirectory(prefix="ytmaxxing-") as tmp:
        path = _download_audio(vid, tmp)
        if engine == "faster-whisper":
            return _transcribe_faster_whisper(path)
        return _transcribe_whisper_cpp(path, tmp)


def _whisper_engine() -> str:
    """Which local engine to use. YTMAXXING_WHISPER_ENGINE picks one ("faster-whisper" or "whisper.cpp");
    otherwise faster-whisper when installed, then whisper.cpp. On Apple Silicon whisper.cpp runs on the GPU
    and is usually several times faster, so set YTMAXXING_WHISPER_ENGINE=whisper.cpp there."""
    wanted = os.environ.get("YTMAXXING_WHISPER_ENGINE", "").strip().lower().replace("_", "-")
    if wanted in ("whisper.cpp", "whisper-cpp", "cpp"):
        if not whisper_cpp_available():
            raise YtmaxxingError("YTMAXXING_WHISPER_ENGINE asks for whisper.cpp, but whisper-cli, a ggml model "
                                 "in ~/.cache/whisper or ffmpeg is missing.")
        return "whisper.cpp"
    if wanted in ("faster-whisper", "faster"):
        if not faster_whisper_available():
            raise YtmaxxingError("YTMAXXING_WHISPER_ENGINE asks for faster-whisper, but it isn't installed: "
                                 "pip install 'ytmaxxing[whisper]'")
        return "faster-whisper"
    return "faster-whisper" if faster_whisper_available() else "whisper.cpp"


def classify_error(message: str) -> str:
    """Sort a fetch failure: "blocked" (rate limit or IP block, worth retrying later), "no-captions",
    "unavailable" (private, removed, age-gated) or "error"."""
    m = message.lower()
    if any(k in m for k in ("block", "429", "too many requests", "not a bot")):
        return "blocked"
    if any(k in m for k in ("no captions", "transcriptsdisabled", "notranscriptfound", "subtitles are disabled")):
        return "no-captions"
    if any(k in m for k in ("unavailable", "private video", "removed", "age-restricted", "age restricted",
                            "agerestricted", "members-only", "members only")):
        return "unavailable"
    return "error"


def fetch_transcript(vid: str, languages: list[str] | None = None, allow_whisper: bool = True) -> Transcript:
    try:
        return fetch_captions(vid, languages)
    except Exception as e:  # noqa: BLE001 - we translate every failure into one clear message
        reason = type(e).__name__
        if allow_whisper and whisper_available():
            return transcribe_with_whisper(vid)
        hint = (
            f"YouTube is blocking requests from this network. Set YTMAXXING_PROXY to a proxy URL, or {WHISPER_HINT}"
            if "Block" in reason or "429" in str(e)
            else f"To handle videos without captions, {WHISPER_HINT}"
        )
        msg = str(e).strip().splitlines()[0] if str(e).strip() else reason
        raise YtmaxxingError(f"Couldn't get captions ({reason}: {msg}). {hint}") from e


# ---------------------------------------------------------------- rendering

def render_transcript(video: Video, tr: Transcript, paragraph_seconds: int = 45) -> list[str]:
    """Turn caption lines into readable paragraphs with clickable timestamps.

    Returns a list of markdown blocks (chapter headings and paragraphs) so callers can
    split long videos into parts at clean boundaries.
    """
    blocks: list[str] = []
    chapters = sorted(video.chapters, key=lambda c: c["start"])
    next_ch = 0
    buf: list[str] = []
    buf_start = 0.0

    def flush():
        if buf:
            blocks.append(f"[{timestamp(buf_start)}]({watch_url(video.id, buf_start)}) " + " ".join(buf))
            buf.clear()

    for line in tr.lines:
        while next_ch < len(chapters) and line.start >= chapters[next_ch]["start"]:
            flush()
            ch = chapters[next_ch]
            blocks.append(f"## {ch['title']} ({timestamp(ch['start'])})")
            next_ch += 1
        if not buf:
            buf_start = line.start
        elif line.start - buf_start >= paragraph_seconds and buf[-1][-1:] in ".?!":
            flush()
            buf_start = line.start
        elif line.start - buf_start >= paragraph_seconds * 2:
            flush()
            buf_start = line.start
        buf.append(line.text)
    flush()
    return blocks


def split_parts(blocks: list[str], max_words: int = 6000) -> list[str]:
    parts: list[list[str]] = [[]]
    words = 0
    for b in blocks:
        n = len(b.split())
        if parts[-1] and words + n > max_words:
            parts.append([])
            words = 0
        parts[-1].append(b)
        words += n
    return ["\n\n".join(p) for p in parts]


# ---------------------------------------------------------------- playlists & channels

def _normalise_list_url(url: str) -> str:
    u = urlparse(url if "://" in url else "https://" + url)
    path = u.path.rstrip("/")
    if re.match(r"^/(@[^/]+|channel/[^/]+|c/[^/]+|user/[^/]+)$", path):
        return f"https://www.youtube.com{path}/videos"
    return url


def list_videos(url: str, limit: int = 25) -> list[dict]:
    """List videos in a playlist or channel (newest first for channels)."""
    import yt_dlp

    opts = _ydl_opts(extract_flat="in_playlist", noplaylist=False, playlistend=limit)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(_normalise_list_url(url), download=False)
    out = []
    for e in info.get("entries") or []:
        vid = (e or {}).get("id")
        if vid and ID_RE.match(vid):
            out.append({"id": vid, "title": e.get("title") or "", "duration": e.get("duration"),
                        "url": watch_url(vid)})
        if len(out) >= limit:
            break
    return out


def search_videos(query: str, limit: int = 20) -> list[dict]:
    """Search YouTube (via yt-dlp's ytsearch, no API key). Returns id, title, channel, duration, url."""
    import yt_dlp

    query = " ".join(query.split())
    if not query:
        raise YtmaxxingError("Give some words to search for.")
    limit = max(1, min(int(limit), 50))
    opts = _ydl_opts(extract_flat="in_playlist", noplaylist=False)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    except Exception as e:  # noqa: BLE001
        raise YtmaxxingError(f"YouTube search failed: {str(e).splitlines()[0] if str(e) else type(e).__name__}") from e
    out = []
    for e in info.get("entries") or []:
        vid = (e or {}).get("id")
        if vid and ID_RE.match(vid):
            out.append({"id": vid, "title": e.get("title") or "", "duration": e.get("duration"),
                        "channel": e.get("channel") or e.get("uploader") or "", "url": watch_url(vid)})
    return out
