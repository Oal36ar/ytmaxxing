"""ytmaxxing MCP server.

The server fetches, structures and stores. Your own AI (Claude, Cursor, any MCP
client) does the thinking by following the mode guides, so there is no API key
to set up and nothing to pay for beyond the AI you already use.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__
from .core import ensure_video, header
from .library import OUTPUT_MODES, Library
from .modes import MODES, build_guide
from .youtube import YtmaxxingError, list_videos, video_id

INSTRUCTIONS = """ytmaxxing turns YouTube videos into skills, knowledge and outcomes the user keeps.
When the user shares a YouTube link (or a playlist or channel), call `maxx` with the mode that fits
what they want (default `max`), then follow the guide it returns: read every transcript part with
`get_video`, write the output, and save it with `save_output`. Before answering questions about
videos the user has watched or saved, check `search_library` first."""

mcp = MCPServer("ytmaxxing", title="ytmaxxing", version=__version__, instructions=INSTRUCTIONS,
                website_url="https://github.com/Oal36ar/ytmaxxing")

READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
LOCAL_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)


def _lib() -> Library:
    return Library()


def tool(annotations: ToolAnnotations):
    """Register a tool and pass expected errors (bad link, no captions, blocked) to the AI as-is."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (YtmaxxingError, ValueError) as e:
                raise ToolError(str(e)) from e
        return mcp.tool(annotations=annotations)(wrapper)
    return decorator


@tool(READ)
def maxx(url: str, mode: str = "max", goal: str = "", target: str = "") -> str:
    """Start turning a YouTube video into something useful. Returns the step-by-step guide to follow.

    Args:
        url: YouTube link (watch, youtu.be, shorts, live or embed) or an 11-character video ID.
        mode: max (everything), skill, knowledge, summary, learn, outcomes or check.
        goal: For outcomes/max: what the user is trying to achieve, in their words.
        target: For check/max: a file or folder path, or a description of the skill, project or plan to compare with.
    """
    if mode not in MODES:
        raise YtmaxxingError(f"Unknown mode '{mode}'. Choose one of: {', '.join(MODES)}.")
    meta, parts = ensure_video(_lib(), url)
    guide = build_guide(mode, video_id=meta["id"], title=meta["title"], date=meta.get("upload_date"),
                        parts=len(parts), goal=goal, target=target)
    return (f"Video ready: {meta['title']} ({meta['channel']}), {len(parts)} transcript part(s).\n"
            f"Next: call get_video(url, part=1) through part={len(parts)}, then follow this guide.\n\n"
            f"{guide}")


@tool(READ)
def get_video(url: str, part: int = 1, refresh: bool = False) -> str:
    """Get a video's details and transcript (cached in the library after the first fetch).

    Long videos come in parts of about 6,000 words. Read every part before writing about the video.

    Args:
        url: YouTube link or video ID.
        part: Which part to return, starting at 1.
        refresh: Fetch again from YouTube instead of using the saved copy.
    """
    meta, parts = ensure_video(_lib(), url, refresh=refresh)
    total = len(parts)
    if not 1 <= part <= total:
        raise YtmaxxingError(f"This video has {total} part(s); ask for part 1 to {total}.")
    tail = (f"\n\n(End of part {part}. Next: get_video(url, part={part + 1}).)" if part < total
            else "\n\n(End of transcript.)")
    return f"{header(meta, part, total)}\n\n{parts[part - 1]}{tail}"


@tool(WRITE)
def save_output(url: str, mode: str, markdown: str, skill_name: str = "", target_name: str = "") -> str:
    """Save what you made from a video into the user's library.

    Args:
        url: YouTube link or video ID the output came from.
        mode: summary, knowledge, skill, learn, outcomes or check.
        markdown: The full output.
        skill_name: For skills: the skill's name (taken from its frontmatter if left empty).
        target_name: For check: a short name for what was compared, used in the filename.
    """
    path = _lib().save_output(video_id(url), mode, markdown, name=skill_name or target_name)
    return f"Saved to {path}"


@tool(READ)
def list_playlist(url: str, limit: int = 25) -> str:
    """List the videos in a YouTube playlist or channel, so you can max them one by one.

    Args:
        url: Playlist link, or a channel link like https://www.youtube.com/@handle (newest first).
        limit: Maximum number of videos to list.
    """
    vids = list_videos(url, limit)
    if not vids:
        return "No videos found at that link."
    return json.dumps(vids, indent=2, ensure_ascii=False)


@tool(LOCAL_READ)
def search_library(query: str, limit: int = 15) -> str:
    """Search everything saved in the library (transcripts, notes, skills) for words or a phrase.

    Args:
        query: Words to look for. Lines containing all of the first three words rank first.
        limit: Maximum number of matching lines.
    """
    lib = _lib()
    hits = lib.search(query, limit)
    if not hits:
        return f"Nothing in the library matches '{query}'. Library: {lib.root}"
    return "\n".join(f"{h['file']}:{h['line']}  {h['text']}" for h in hits) + f"\n\n(Library root: {lib.root})"


@tool(LOCAL_READ)
def list_library() -> str:
    """List every video in the library and what has been made from it, plus all saved skills."""
    lib = _lib()
    entries = lib.entries()
    if not entries:
        return f"The library is empty. Share a YouTube link to start. (Location: {lib.root})"
    lines = [f"- {e['title']} — {e['channel']} ({e['date'] or '?'}) [{e['id']}]: "
             f"{', '.join(e['outputs']) or 'transcript only'}" for e in entries]
    skills = lib.skill_names()
    if skills:
        lines += ["", "Skills: " + ", ".join(skills)]
    return "\n".join(lines) + f"\n\n(Location: {lib.root})"


@tool(LOCAL_READ)
def read_output(url: str, mode: str) -> str:
    """Read something already saved for a video.

    Args:
        url: YouTube link or video ID.
        mode: transcript, summary, knowledge, skill (lists its skills), learn or outcomes.
    """
    text = _lib().read_output(video_id(url), mode)
    if text is None:
        return f"Nothing saved for mode '{mode}' on that video yet."
    return text


@tool(WRITE)
def install_skill(skill_name: str, where: str = "user", project_dir: str = "") -> str:
    """Install a skill from the library so the user's agent loads it automatically. Ask the user first.

    Args:
        skill_name: Name of a skill in the library.
        where: "user" (~/.claude/skills, every project), "project" (<project_dir>/.claude/skills),
            or any folder path (for other agents' skill folders).
        project_dir: Project folder, needed when where="project".
    """
    if where == "user":
        target = Path.home() / ".claude" / "skills"
    elif where == "project":
        if not project_dir:
            raise YtmaxxingError("Give project_dir when installing into a project.")
        target = Path(project_dir) / ".claude" / "skills"
    else:
        target = Path(where)
    path = _lib().install_skill(skill_name, target)
    return f"Installed: {path}. The agent will pick it up in its next session."


def _register_prompts() -> None:
    for key, info in MODES.items():
        def make(mode: str):
            def prompt(url: str, goal: str = "", target: str = "") -> str:
                extra = (f" My goal: {goal}." if goal else "") + (f" Compare it with: {target}." if target else "")
                return (f"Use ytmaxxing in {mode} mode on {url}.{extra} "
                        f"Call maxx(url, mode='{mode}', goal, target) and follow the guide it returns.")
            return prompt
        mcp.prompt(name=key, description=info['what'])(make(key))


_register_prompts()


def run() -> None:
    mcp.run()


assert set(OUTPUT_MODES) <= set(MODES)
