"""The library: plain markdown files on your machine that any AI agent can read.

    ~/ytmaxxing/
      index.md                          every video and what you made from it
      videos/<title>-<id>/
        transcript.md                   readable transcript with clickable timestamps
        meta.json
        summary.md  knowledge.md  learn.md  outcomes.md  check-<target>.md
      skills/<skill-name>/SKILL.md      skills extracted from videos, ready to install
      research/<question>/              many videos, one checked report (see research.py)

Change the location with the YTMAXXING_HOME environment variable.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .youtube import Transcript, Video, YtmaxxingError, render_transcript, split_parts, timestamp

OUTPUT_MODES = ("summary", "knowledge", "skill", "learn", "outcomes", "check")


def default_home() -> Path:
    return Path(os.environ.get("YTMAXXING_HOME", Path.home() / "ytmaxxing")).expanduser()


def slugify(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return (s[:max_len].rstrip("-")) or "untitled"


def skill_slug(name: str) -> str:
    """Agent Skills names: lowercase letters, digits and hyphens, at most 64 characters."""
    s = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)[:64].rstrip("-")
    if not s:
        raise YtmaxxingError("A skill needs a name made of letters, digits or hyphens.")
    return s


class Library:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_home()
        self.videos = self.root / "videos"
        self.skills = self.root / "skills"

    # ------------------------------------------------------------ videos

    def find_video_dir(self, vid: str) -> Path | None:
        if not self.videos.exists():
            return None
        for d in self.videos.iterdir():
            if d.is_dir() and d.name.endswith(f"-{vid}"):
                return d
        return None

    def video_dir(self, video: Video) -> Path:
        existing = self.find_video_dir(video.id)
        if existing:
            return existing
        d = self.videos / f"{slugify(video.title)}-{video.id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_transcript(self, video: Video, tr: Transcript) -> Path:
        d = self.video_dir(video)
        blocks = render_transcript(video, tr)
        header = [
            f"# {video.title}",
            "",
            f"- **Channel:** {video.channel}",
            f"- **Link:** {video.url}",
            f"- **Published:** {video.upload_date or 'unknown'}",
            f"- **Length:** {timestamp(video.duration) if video.duration else 'unknown'}",
            f"- **Transcript source:** {tr.source} ({tr.language})",
            "",
            "Timestamps link to that moment in the video.",
            "",
            "---",
            "",
        ]
        (d / "transcript.md").write_text("\n".join(header) + "\n\n".join(blocks) + "\n", encoding="utf-8")
        meta = video.to_dict() | {
            "language": tr.language, "source": tr.source,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "parts": len(split_parts(blocks)),
        }
        (d / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        self.update_index()
        return d / "transcript.md"

    def load_meta(self, vid: str) -> dict | None:
        d = self.find_video_dir(vid)
        if d and (d / "meta.json").exists():
            return json.loads((d / "meta.json").read_text(encoding="utf-8"))
        return None

    def transcript_parts(self, vid: str) -> list[str] | None:
        d = self.find_video_dir(vid)
        if not d or not (d / "transcript.md").exists():
            return None
        text = (d / "transcript.md").read_text(encoding="utf-8")
        body = text.split("\n---\n", 1)[-1].strip()
        return split_parts([b for b in body.split("\n\n") if b.strip()])

    # ------------------------------------------------------------ outputs

    def save_output(self, vid: str, mode: str, markdown: str, name: str = "") -> Path:
        if mode not in OUTPUT_MODES:
            raise YtmaxxingError(f"Unknown mode '{mode}'. Use one of: {', '.join(OUTPUT_MODES)}.")
        d = self.find_video_dir(vid)
        if not d:
            raise YtmaxxingError("Fetch the video first (get_video), then save outputs for it.")
        if mode == "skill":
            if not name:
                m = re.search(r"^name:\s*([^\n]+)$", markdown, flags=re.MULTILINE)
                name = m.group(1).strip().strip("'\"") if m else ""
            slug = skill_slug(name)
            target = self.skills / slug / "SKILL.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(markdown.strip() + "\n", encoding="utf-8")
            links = d / "skills.md"
            lines = links.read_text(encoding="utf-8").splitlines() if links.exists() else ["# Skills from this video", ""]
            entry = f"- [{slug}](../../skills/{slug}/SKILL.md)"
            if entry not in lines:
                lines.append(entry)
            links.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            filename = f"check-{slugify(name, 32)}.md" if mode == "check" and name else f"{mode}.md"
            target = d / filename
            target.write_text(markdown.strip() + "\n", encoding="utf-8")
        self.update_index()
        return target

    def read_output(self, vid: str, mode: str) -> str | None:
        d = self.find_video_dir(vid)
        if not d:
            return None
        if mode == "skill":
            p = d / "skills.md"
        elif mode == "transcript":
            p = d / "transcript.md"
        else:
            p = d / f"{mode}.md"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def install_skill(self, name: str, target_dir: Path) -> Path:
        src = self.skills / skill_slug(name)
        if not (src / "SKILL.md").exists():
            raise YtmaxxingError(f"No skill called '{name}' in the library yet.")
        dest = Path(target_dir).expanduser() / src.name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / "SKILL.md", dest / "SKILL.md")
        return dest / "SKILL.md"

    # ------------------------------------------------------------ browsing

    def entries(self) -> list[dict]:
        out = []
        if not self.videos.exists():
            return out
        for d in sorted(self.videos.iterdir()):
            if not (d / "meta.json").exists():
                continue
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            made = [m for m in OUTPUT_MODES if m != "skill" and (d / f"{m}.md").exists()]
            made += ["check"] if any(d.glob("check-*.md")) and "check" not in made else []
            if (d / "skills.md").exists():
                made.append("skill")
            out.append({"id": meta["id"], "title": meta["title"], "channel": meta["channel"],
                        "date": meta.get("upload_date"), "dir": d, "outputs": made})
        return out

    def skill_names(self) -> list[str]:
        if not self.skills.exists():
            return []
        return sorted(p.parent.name for p in self.skills.glob("*/SKILL.md"))

    def update_index(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        rows = ["# ytmaxxing library", "",
                "Every video you've maxxed and what you made from it. Agents: start here.", "",
                "| Video | Channel | Published | Made |", "|---|---|---|---|"]
        for e in self.entries():
            rel = e["dir"].relative_to(self.root).as_posix()
            made = ", ".join(e["outputs"]) or "transcript"
            title = e["title"].replace("|", "/")
            rows.append(f"| [{title}]({rel}/transcript.md) | {e['channel']} | {e['date'] or '?'} | {made} |")
        skills = self.skill_names()
        if skills:
            rows += ["", "## Skills", ""] + [f"- [{s}](skills/{s}/SKILL.md)" for s in skills]
        from .research import list_projects

        projects = list_projects(self)
        if projects:
            rows += ["", "## Research", ""]
            for p in projects:
                target = "report.md" if p["report"] else "brief.md"
                rows.append(f"- [{p['question']}](research/{p['slug']}/{target}) · {p['read']} of {p['videos']} "
                            f"videos read · {p['created']}{'' if p['report'] else ' · no report yet'}")
        (self.root / "index.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    def search(self, query: str, limit: int = 15) -> list[dict]:
        terms = [t for t in query.lower().split() if t]
        if not terms or not self.root.exists():
            return []
        hits = []
        for p in self.root.rglob("*.md"):
            if p.name in ("index.md", "brief.md"):
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                low = line.lower()
                score = sum(low.count(t) for t in terms)
                if score and all(t in low for t in terms[:3]):
                    hits.append({"file": p.relative_to(self.root).as_posix(), "line": i,
                                 "text": line.strip()[:300], "score": score})
        hits.sort(key=lambda h: -h["score"])
        return hits[:limit]
