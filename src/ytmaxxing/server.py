"""ytmaxxing MCP server.

The server fetches, structures and stores. Your own AI (Claude, Cursor, any MCP
client) does the thinking by following the mode guides, so there is no API key
to set up and nothing to pay for beyond the AI you already use.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__
from .core import ensure_video, header
from .library import OUTPUT_MODES, Library
from .modes import MODES, build_guide
from .research import Project, list_projects
from .verify import check_output, load_paragraphs
from .youtube import YtmaxxingError, list_videos, timestamp, video_id

INSTRUCTIONS = """ytmaxxing turns YouTube videos into skills, knowledge and outcomes the user keeps.
When the user shares a YouTube link (or a playlist or channel), call `maxx` with the mode that fits
what they want (default `max`), then follow the guide it returns: read every transcript part with
`get_video`, write the output, and save it with `save_output` (it checks the citations; fix what it
flags). When the user wants a question answered from many videos (a channel, playlist, search or list),
use `research_start` and follow the guide it returns. Before answering questions about videos the user
has watched or saved, check `search_library` first."""

mcp = MCPServer("ytmaxxing", title="ytmaxxing", version=__version__, instructions=INSTRUCTIONS,
                website_url="https://github.com/Oal36ar/ytmaxxing")

READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
LOCAL_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
FETCH_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)


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
    lib = _lib()
    vid = video_id(url)
    path = lib.save_output(vid, mode, markdown, name=skill_name or target_name)
    return f"Saved to {path}\n{_check_citations(lib, vid, markdown)}"


def _check_citations(lib: Library, vid: str, markdown: str) -> str:
    """Check every timestamp link (and quotes next to them) in a saved output against the transcript."""
    d = lib.find_video_dir(vid)
    if not d or not (d / "transcript.md").exists():
        return "Citation check skipped: no saved transcript."
    meta = lib.load_meta(vid) or {}
    return check_output(markdown, vid, load_paragraphs(d / "transcript.md"), meta.get("duration")).summary()


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


# ---------------------------------------------------------------- research: many videos, one report

class Claim(BaseModel):
    q: str = Field(description="Sub-question ID this claim answers, e.g. Q2")
    claim: str = Field(description="The point in your own words: one short, specific sentence")
    speaker: str = Field("", description="Who says it (name, or 'host'/'guest'); empty if unclear")
    type: str = Field(description="shown, measured, belief or story")
    stance: str = Field(description="2-5 plain words naming the position, worded so other videos' claims line up")
    t: int | str = Field(description="Time of the transcript paragraph where it's said: seconds or mm:ss")
    quote: str = Field("", description="3-25 words copied exactly from that paragraph (caption typos included)")


class Side(BaseModel):
    label: str = Field(description="The position, in a few words")
    claims: list[str] = Field(description="Claim IDs (like V03.4) that hold this position")


class Position(BaseModel):
    q: str = Field(description="Sub-question ID, e.g. Q1")
    kind: str = Field(description="agree (one position held in 2+ videos) or contradict (2+ sides)")
    label: str = Field("", description="For agree: the shared position. For contradict: what they split on, "
                                       "as a short title (e.g. 'Is AI already costing jobs?')")
    claims: list[str] = Field(default_factory=list, description="For agree: claim IDs holding it")
    sides: list[Side] = Field(default_factory=list, description="For contradict: each side with its claim IDs")


def _project(project: str) -> Project:
    return Project(_lib(), project.strip())


@tool(READ)
def search_videos(query: str, limit: int = 20) -> str:
    """Search YouTube for videos (no API key). Use it to build a source list for research.

    Args:
        query: Search words, as you'd type them into YouTube.
        limit: Maximum number of results (up to 50).
    """
    from . import youtube

    hits = youtube.search_videos(query, limit)
    if not hits:
        return "No videos found."
    return "\n".join(f"{i}. {h['title']} · {h.get('channel') or '?'} · "
                     f"{timestamp(h['duration']) if h.get('duration') else '?'} · {h['url']}"
                     for i, h in enumerate(hits, 1))


@tool(FETCH_WRITE)
def research_start(question: str, sub_questions: list[str], sources: list[str], limit: int = 20,
                   allow_whisper: bool = False) -> str:
    """Start a research project: one question answered from many videos, with every citation checked.

    Returns the project ID, the video list and the guide to follow. Confirm the video list with the user
    before reading more than 20 videos.

    Args:
        question: The user's research question, as a full sentence.
        sub_questions: 3 to 7 sub-questions that break the question down; every video is read against them.
        sources: Any mix of video links, playlist or channel links, and "search:<words>" for a YouTube search.
        limit: Most videos to take from the sources (up to 50).
        allow_whisper: Transcribe videos without captions locally (slow; needs the whisper extra).
    """
    proj, notes = Project.create(_lib(), question, sub_questions, sources, limit, allow_whisper)
    return "\n\n".join([f"Research project `{proj.slug}` created with {len(proj.sources)} video(s).",
                         " ".join(notes), proj.status(), "Next: confirm the list with the user if needed, then "
                         "call research_fetch until all sources are fetched.", proj.guide()]).replace("\n\n\n", "\n\n")


@tool(FETCH_WRITE)
def research_edit(project: str, drop: list[str] | None = None, add: list[str] | None = None) -> str:
    """Drop videos from a research project (by ID, like V04) or add more sources.

    Args:
        project: Project ID from research_start.
        drop: Video IDs to remove, e.g. ["V04", "V11"].
        add: More sources: video links, playlist or channel links, or "search:<words>".
    """
    proj = _project(project)
    return proj.edit(drop or [], add or []) + "\n\n" + proj.status()


@tool(FETCH_WRITE)
def research_fetch(project: str, batch: int = 5) -> str:
    """Fetch the next transcripts for a research project, paced so YouTube doesn't block. Call until done.

    Args:
        project: Project ID from research_start.
        batch: How many videos to fetch in this call (1-10).
    """
    return _project(project).fetch(batch)


@tool(LOCAL_READ)
def research_status(project: str = "") -> str:
    """Show a research project's videos and what's been read, skipped or is still queued.

    Args:
        project: Project ID. Leave empty to list all research projects.
    """
    if not project.strip():
        projects = list_projects(_lib())
        if not projects:
            return "No research projects yet. Start one with research_start."
        return "\n".join(f"- {p['slug']}: {p['question']} ({p['read']} of {p['videos']} read"
                         f"{', report saved' if p['report'] else ''})" for p in projects)
    return _project(project).status()


@tool(LOCAL_READ)
def research_brief(project: str, video: str) -> str:
    """The instructions for reading one video in a research project. Hand this text to a subagent as-is.

    Args:
        project: Project ID.
        video: Video ID in the project, e.g. V07.
    """
    return _project(project).brief(video)


@tool(WRITE)
def save_claims(project: str, video: str, claims: list[Claim], replace: bool = False,
                nothing_relevant: bool = False) -> str:
    """Save the claims from one video. Each is checked against the transcript; rejected ones come back with reasons.

    Args:
        project: Project ID.
        video: Video ID in the project, e.g. V07.
        claims: The claims from this video.
        replace: Replace this video's earlier claims instead of adding to them.
        nothing_relevant: Set true, with no claims, if the whole video was read and says nothing on the question.
    """
    return _project(project).save_claims(video, [c.model_dump() for c in claims], replace, nothing_relevant)


@tool(LOCAL_READ)
def research_claims(project: str, q: str = "", offset: int = 0) -> str:
    """All checked claims in a research project, one line each, for finding agreements and contradictions.

    Args:
        project: Project ID.
        q: Only this sub-question (e.g. Q2). Leave empty for all.
        offset: Start from this row, for long lists.
    """
    return _project(project).claims_text(q, offset)


@tool(WRITE)
def save_report(project: str, answer: str, positions: list[Position], notes: str = "", gaps: str = "") -> str:
    """Save the research report. ytmaxxing checks every claim ID, counts the videos per position,
    turns IDs into timestamp links and adds the coverage line.

    Args:
        project: Project ID.
        answer: One or two paragraphs answering the question. Cite claim IDs in braces, like {V03.4}.
        positions: Agreements and contradictions, built from claim IDs.
        notes: Evidence quality: shown or measured versus belief, conflicts of interest, dated videos.
        gaps: What no video answered well.
    """
    return _project(project).save_report(answer, [p.model_dump() for p in positions], notes, gaps)


def _register_prompts() -> None:
    for key, info in MODES.items():
        def make(mode: str):
            def prompt(url: str, goal: str = "", target: str = "") -> str:
                extra = (f" My goal: {goal}." if goal else "") + (f" Compare it with: {target}." if target else "")
                return (f"Use ytmaxxing in {mode} mode on {url}.{extra} "
                        f"Call maxx(url, mode='{mode}', goal, target) and follow the guide it returns.")
            return prompt
        mcp.prompt(name=key, description=info['what'])(make(key))

    def research_prompt(question: str, sources: str = "") -> str:
        where = f" Use these sources: {sources}." if sources else " Suggest sources (a YouTube search or channel) first."
        return (f"Use ytmaxxing research to answer: {question}.{where} Call research_start and follow the guide "
                "it returns: every video read in full, every citation checked, one report.")

    mcp.prompt(name="research", description="One question, many videos: a checked report of where they agree "
               "and contradict each other.")(research_prompt)


_register_prompts()


def run() -> None:
    mcp.run()


assert set(OUTPUT_MODES) <= set(MODES)
