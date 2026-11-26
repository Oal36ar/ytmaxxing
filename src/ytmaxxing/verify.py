"""Check citations against the saved transcript, in code, so a made-up moment can't slip through.

A citation is a time in a video, optionally with a short quote. The check:

1. finds the transcript paragraph that contains the time (paragraphs are about 45 seconds long),
2. looks for the quote in that paragraph and its neighbours, exactly or as a close match
   (auto-captions garble names, so "Kokotajlo" may appear as "Cocatello"),
3. snaps the time to the start of the paragraph where the words are, so the link lands on them.

It proves the words were said at that moment. It can't prove a paraphrase is fair, or who said it.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

CLOSE_MATCH = 0.85  # character-level similarity needed for a garbled-caption quote to pass
MAX_QUOTE_WORDS = 30
MIN_QUOTE_WORDS = 3

# A rendered transcript paragraph: [12:34](https://youtu.be/<id>?t=754) words words words
PARA_RE = re.compile(r"^\[(?P<label>\d+(?::\d{2}){1,2})\]\(https://youtu\.be/(?P<id>[A-Za-z0-9_-]{11})"
                     r"(?:\?t=(?P<t>\d+))?\)\s*(?P<text>.*)$")
# Any YouTube timestamp link inside an output (youtu.be/<id>?t=N or youtube.com/watch?v=<id>&t=N)
LINK_RE = re.compile(r"\]\((?P<url>https?://(?:www\.)?(?:youtu\.be/(?P<id1>[A-Za-z0-9_-]{11})"
                     r"|youtube\.com/watch\?v=(?P<id2>[A-Za-z0-9_-]{11}))(?P<rest>[^)\s]*))\)")
QUOTE_RE = re.compile(r"[\"“]([^\"“”\n]{6,300})[\"”]")


@dataclass
class Paragraph:
    start: int
    text: str
    norm: str


@dataclass
class Check:
    status: str  # "quote" | "quote-close" | "time" | "rejected"
    t: int | None = None  # snapped time in seconds
    reason: str = ""
    score: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status != "rejected"


def normalise(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text.lower().replace("’", "'").replace("'", ""), flags=re.UNICODE)
    return " ".join(text.split())


def parse_time(value) -> int:
    """Seconds from 754, 754.2, "754", "12:34", "1:02:34", "12:34s" or a link with ?t=/&t=."""
    if isinstance(value, bool):
        raise ValueError(f"Not a time: {value!r}")
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("Time can't be negative.")
        return int(value)
    s = str(value).strip()
    m = re.search(r"[?&]t=(\d+)", s)
    if m:
        return int(m.group(1))
    s = s.strip("[]() ").rstrip("s")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return int(float(s))
    if re.fullmatch(r"\d+(:\d{1,2}){1,2}", s):
        total = 0
        for piece in s.split(":"):
            total = total * 60 + int(piece)
        return total
    raise ValueError(f"Not a time: {value!r} (use seconds or mm:ss)")


def _label_seconds(label: str) -> int:
    return parse_time(label)


def parse_paragraphs(transcript_md: str) -> list[Paragraph]:
    """Timed paragraphs from a saved transcript.md (chapter headings are skipped)."""
    body = transcript_md.split("\n---\n", 1)[-1]
    paras = []
    for block in body.split("\n\n"):
        m = PARA_RE.match(block.strip())
        if not m:
            continue
        start = int(m.group("t")) if m.group("t") else _label_seconds(m.group("label"))
        text = m.group("text")
        paras.append(Paragraph(start, text, normalise(text)))
    paras.sort(key=lambda p: p.start)
    return paras


def load_paragraphs(path: Path) -> list[Paragraph]:
    return parse_paragraphs(Path(path).read_text(encoding="utf-8"))


def _best_window(quote_words: list[str], words: list[str]) -> tuple[float, int]:
    """Best close-match score of the quote against any run of words, and where that run starts."""
    target = " ".join(quote_words)
    n = len(quote_words)
    best, at = 0.0, -1
    for size in {max(1, n - 1), n, n + 1}:
        for i in range(0, max(1, len(words) - size + 1)):
            cand = " ".join(words[i:i + size])
            sm = SequenceMatcher(None, target, cand, autojunk=False)
            if sm.real_quick_ratio() < best or sm.quick_ratio() < best:
                continue
            r = sm.ratio()
            if r > best:
                best, at = r, i
    return best, at


def check(paragraphs: list[Paragraph], t, quote: str = "", duration: int | None = None) -> Check:
    """Check one citation. `t` is seconds or mm:ss; `quote` is optional exact words from the transcript."""
    if not paragraphs:
        return Check("rejected", reason="no transcript to check against")
    try:
        secs = parse_time(t)
    except ValueError as e:
        return Check("rejected", reason=str(e))
    end = duration or (paragraphs[-1].start + 120)
    if secs > end + 5:
        return Check("rejected", reason=f"time {secs}s is past the end of the video ({end}s)")
    starts = [p.start for p in paragraphs]
    i = max(0, bisect.bisect_right(starts, secs) - 1)
    lo, hi = max(0, i - 1), min(len(paragraphs), i + 2)

    quote = (quote or "").strip().strip("\"“”'")
    if not quote:
        return Check("time", t=paragraphs[i].start)
    qn = normalise(quote)
    qwords = qn.split()
    if len(qwords) < MIN_QUOTE_WORDS:
        return Check("rejected", reason=f"quote too short to check (use {MIN_QUOTE_WORDS}+ exact words)")
    if len(qwords) > MAX_QUOTE_WORDS:
        return Check("rejected", reason=f"quote is {len(qwords)} words; keep it under {MAX_QUOTE_WORDS}")

    # Words of the window, remembering which paragraph each came from (quotes can cross a boundary).
    words: list[str] = []
    owner: list[int] = []
    for j in range(lo, hi):
        w = paragraphs[j].norm.split()
        words += w
        owner += [j] * len(w)
    joined = " " + " ".join(words) + " "
    pos = joined.find(" " + qn + " ")
    if pos >= 0:
        word_index = joined[:pos + 1].count(" ") - 1
        return Check("quote", t=paragraphs[owner[max(0, word_index)]].start, score=1.0)
    score, at = _best_window(qwords, words)
    if score >= CLOSE_MATCH and at >= 0:
        return Check("quote-close", t=paragraphs[owner[at]].start, score=round(score, 3))
    where = f"{paragraphs[lo].start}s–{paragraphs[hi - 1].start + 45}s"
    return Check("rejected", score=round(score, 3),
                 reason=f"quote not found near that time (searched {where}, best match {score:.0%})")


# ---------------------------------------------------------------- whole outputs (every mode)

@dataclass
class OutputReport:
    links: int = 0
    links_ok: int = 0
    quotes: int = 0
    quotes_ok: int = 0
    problems: list[str] | None = None

    def summary(self) -> str:
        if not self.links:
            return "Citation check: no timestamp links found. Every claim should link to its moment."
        line = f"Citation check: {self.links_ok} of {self.links} timestamp links land inside the video"
        if self.quotes:
            line += f"; {self.quotes_ok} of {self.quotes} quoted phrases found at their moment"
        line += "."
        if self.problems:
            shown = self.problems[:12]
            more = len(self.problems) - len(shown)
            line += ("\nCheck these, fix what's wrong and save again. A phrase in quote marks that is your own "
                     "wording, not the speaker's, can stay; otherwise copy the transcript's exact words:\n"
                     + "\n".join(f"- {p}" for p in shown))
            if more > 0:
                line += f"\n- …and {more} more"
        return line


def check_output(markdown: str, video_id: str, paragraphs: list[Paragraph],
                 duration: int | None = None) -> OutputReport:
    """Check every timestamp link in a saved output, and every quote that shares a line with one."""
    rep = OutputReport(problems=[])
    for n, line in enumerate(markdown.splitlines(), 1):
        links = list(LINK_RE.finditer(line))
        if not links:
            continue
        times = []
        for m in links:
            rep.links += 1
            vid = m.group("id1") or m.group("id2")
            tm = re.search(r"[?&]t=(\d+)", m.group("rest") or "")
            label = line[:m.start()].rsplit("[", 1)[-1][:20]
            if vid != video_id:
                rep.problems.append(f"line {n}: link [{label}] points to another video ({vid})")
                continue
            secs = int(tm.group(1)) if tm else 0
            c = check(paragraphs, secs, duration=duration)
            if c.ok:
                rep.links_ok += 1
                times.append(secs)
            else:
                rep.problems.append(f"line {n}: link [{label}]: {c.reason}")
        for q in QUOTE_RE.findall(LINK_RE.sub("](link)", line)):
            if len(normalise(q).split()) < MIN_QUOTE_WORDS or not times:
                continue
            rep.quotes += 1
            results = [check(paragraphs, s, q, duration) for s in times]
            if any(r.ok for r in results):
                rep.quotes_ok += 1
            else:
                short = q if len(q) <= 60 else q[:57] + "…"
                rep.problems.append(f"line {n}: \"{short}\" isn't in the transcript at the linked moment")
    return rep
