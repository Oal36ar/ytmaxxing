"""The ways to max a video. Each mode is a guide the user's own AI follows."""

from __future__ import annotations

from importlib import resources

MODES: dict[str, dict[str, str]] = {
    "max": {"emoji": "🚀", "title": "Max", "what": "Everything useful from one video, in one go."},
    "skill": {"emoji": "🛠️", "title": "Skill", "what": "Your AI learns how to do what the video teaches (SKILL.md)."},
    "knowledge": {"emoji": "🧠", "title": "Knowledge", "what": "Cited notes: claims, frameworks, numbers, tools. Searchable forever."},
    "summary": {"emoji": "📝", "title": "Summary", "what": "TL;DR, chapter by chapter, best moments, watch/skim/skip."},
    "learn": {"emoji": "🎓", "title": "Learn", "what": "Study guide: simple explanations, quiz, practice, review plan."},
    "outcomes": {"emoji": "🎯", "title": "Outcomes", "what": "Decisions and this-week actions for your own goal."},
    "check": {"emoji": "🔍", "title": "Check", "what": "Compare the video with your skill, project or plan, and get upgrades."},
}


def _read(name: str) -> str:
    return resources.files("ytmaxxing").joinpath("guides", f"{name}.md").read_text(encoding="utf-8")


def build_guide(mode: str, *, video_id: str, title: str, date: str | None, parts: int,
                goal: str = "", target: str = "") -> str:
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose one of: {', '.join(MODES)}.")
    if mode == "max":
        sections = ["max", "summary", "knowledge", "skill", "learn"]
        if goal:
            sections.append("outcomes")
        if target:
            sections.append("check")
        body = "\n\n---\n\n".join(_read(s) for s in sections)
        save_mode = "matching each output (summary, knowledge, skill, …)"
    else:
        body = _read(mode)
        save_mode = mode
    text = f"{body}\n\n{_read('_rules')}"
    for key, value in {
        "{{VIDEO_ID}}": video_id, "{{TITLE}}": title, "{{DATE}}": date or "on an unknown date",
        "{{PARTS}}": str(parts), "{{GOAL}}": goal or "(not given)", "{{TARGET}}": target or "(not given)",
        "{{MODE}}": save_mode,
    }.items():
        text = text.replace(key, value)
    return text
