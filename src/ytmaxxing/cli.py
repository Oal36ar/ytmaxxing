"""Command line: run the MCP server, or use ytmaxxing with any chatbot by copy-paste."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from . import __version__
from .core import ensure_video, header
from .library import Library
from .modes import MODES, build_guide
from .youtube import YtmaxxingError, list_videos

BANNER = "▶ ytmaxxing — turn YouTube into skills and knowledge your AI can use"


def _copy(text: str) -> bool:
    for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["clip"]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text.encode("utf-8"), check=False)
            return True
    return False


def cmd_prompt(a) -> str:
    """Everything a chatbot needs (guide + full transcript) in one block to paste."""
    meta, parts = ensure_video(Library(), a.url, a.lang)
    guide = build_guide(a.mode, video_id=meta["id"], title=meta["title"], date=meta.get("upload_date"),
                        parts=len(parts), goal=a.goal or "", target=a.target or "")
    guide = guide.replace("Call `get_video` for every part", "Read the full transcript below")
    guide = guide.replace("call `save_output` with mode", "give me the result as one markdown block for mode")
    transcript = "\n\n".join(parts)
    return (f"{guide}\n\n---\n\n{header(meta, 1, 1)}\n\n{transcript}\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ytmaxxing", description=BANNER)
    p.add_argument("--version", action="version", version=f"ytmaxxing {__version__}")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="run the MCP server (this is what Claude, Cursor & co. start)")

    t = sub.add_parser("transcript", help="save a video's transcript to your library and print it")
    t.add_argument("url")
    t.add_argument("--lang", nargs="*", help="preferred caption languages, e.g. --lang en ar")
    t.add_argument("--refresh", action="store_true", help="fetch again instead of using the saved copy")

    pr = sub.add_parser("prompt", help="build a ready-to-paste prompt for ChatGPT, Gemini or any AI")
    pr.add_argument("url")
    pr.add_argument("--mode", default="max", choices=list(MODES))
    pr.add_argument("--goal", help="your goal, for outcomes mode")
    pr.add_argument("--target", help="what to compare with, for check mode")
    pr.add_argument("--lang", nargs="*")
    pr.add_argument("--copy", action="store_true", help="copy to the clipboard instead of printing")

    pl = sub.add_parser("playlist", help="list the videos in a playlist or channel")
    pl.add_argument("url")
    pl.add_argument("--limit", type=int, default=25)

    sub.add_parser("ls", help="list your library")
    s = sub.add_parser("search", help="search your library")
    s.add_argument("query", nargs="+")
    sub.add_parser("modes", help="show the ways to max a video")

    a = p.parse_args(argv)
    if a.cmd is None:
        if not sys.stdin.isatty():  # started by an MCP client with no arguments
            a.cmd = "serve"
        else:
            p.print_help()
            return 0

    try:
        if a.cmd == "serve":
            from .server import run

            run()
        elif a.cmd == "transcript":
            meta, parts = ensure_video(Library(), a.url, a.lang, refresh=a.refresh)
            print(header(meta, 1, 1) + "\n\n" + "\n\n".join(parts))
        elif a.cmd == "prompt":
            text = cmd_prompt(a)
            if a.copy and _copy(text):
                print(f"✅ Copied ({len(text.split()):,} words). Paste it into any AI chat.")
            else:
                print(text)
        elif a.cmd == "playlist":
            for i, v in enumerate(list_videos(a.url, a.limit), 1):
                print(f"{i:>3}. {v['title']}  {v['url']}")
        elif a.cmd == "ls":
            lib = Library()
            entries = lib.entries()
            if not entries:
                print(f"Library is empty ({lib.root}). Try: ytmaxxing transcript <youtube-url>")
            for e in entries:
                print(f"▶ {e['title']} — {e['channel']}  [{', '.join(e['outputs']) or 'transcript'}]")
            for s_ in lib.skill_names():
                print(f"🛠️  skill: {s_}")
        elif a.cmd == "search":
            for h in Library().search(" ".join(a.query)):
                print(f"{h['file']}:{h['line']}  {h['text']}")
        elif a.cmd == "modes":
            for key, m in MODES.items():
                print(f"{m['emoji']}  {key:<10} {m['what']}")
    except YtmaxxingError as e:
        print(f"✖ {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
