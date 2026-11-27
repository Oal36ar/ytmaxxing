"""Research: one question, many videos, one report where every citation is checked by code.

    ~/ytmaxxing/research/<slug>/
      brief.md          the question, its sub-questions and the source list
      project.json      question, sub-questions, settings
      sources.json      one row per video: V01, V02… with status and reason
      cards/V07.json    checked claims from one video (and V07.md, readable)
      rejections.jsonl  every claim save_claims turned down, with the reason, so it can be reviewed
      report.src.json   what the agent sent to save_report
      report.md         the report: answer, coverage, agreement, contradiction, who said what

The split of work: the user's AI frames the question, reads each video (one subagent per video
where the client allows it) and groups claims into positions. ytmaxxing fetches with pacing,
checks every claim against the transcript, gives claims IDs, counts videos per position, renders
links and writes the coverage line. Anything that can be checked is done here, in code.
"""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime, timezone

from .core import ensure_video
from .library import Library, slugify
from .verify import NUMBER_WORDS, check, find_exact, load_paragraphs, normalise, parse_time
from .youtube import (ID_RE, YtmaxxingError, classify_error, list_videos, search_videos, timestamp,
                      video_id, watch_url)

MAX_VIDEOS = 50
MAX_SUB_QUESTIONS = 7
CLAIM_TYPES = ("shown", "measured", "belief", "story")
CLAIM_ID_RE = re.compile(r"\bV\d{2,3}\.\d+\b")
REF_GROUP_RE = re.compile(r"\{\s*(V\d{2,3}\.\d+(?:\s*[,;]\s*V\d{2,3}\.\d+)*)\s*\}")
LIST_PATH_RE = re.compile(r"^/(playlist|@[^/]+|channel/[^/]+|c/[^/]+|user/[^/]+)(/(videos|streams|shorts))?/?$")

PACE_SECONDS = (2.0, 5.0)  # wait between new fetches, so YouTube doesn't block the user's IP
BLOCK_WAIT_SECONDS = 20.0  # wait once before retrying a blocked fetch
STOP_AFTER_BLOCKS = 2  # consecutive blocked videos before a batch gives up
_sleep = time.sleep  # replaced in tests

COLD_OPEN_SECONDS = 60  # without an intro chapter, a quote this early may be from a teaser clip
COLD_OPEN_MAX_SECONDS = 180  # an intro chapter longer than this isn't treated as a teaser
COLD_OPEN_MIN_LENGTH = 600  # only videos at least this long are treated as having a teaser
INTRO_TITLES = ("intro", "coming up", "teaser", "trailer", "preview", "cold open", "highlights", "opening",
                "sneak peek")
GENERIC_SPEAKERS = {"host", "guest", "interviewer", "narrator", "unknown", "moderator", "speaker", "audience",
                    "caller", "clip", "panel", "panelist", "presenter", "voiceover", "co", "the", "a", "an",
                    "founder", "cofounder", "ceo", "cto", "economist", "professor", "prof", "researcher",
                    "lecturer", "author", "expert", "journalist", "scientist", "engineer", "investor", "analyst",
                    "reporter", "student", "teacher", "executive", "official", "commentator", "other", "second",
                    "first", "man", "woman", "person", "unnamed", "unidentified", "and"}

STATUS_WORDS = {"queued": "queued", "fetched": "fetched", "extracted": "read", "skipped": "skipped",
                "dropped": "dropped"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hm(seconds: int | None) -> str:
    if not seconds:
        return "?"
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def _n(count: int, one: str, many: str = "") -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


_SMALL = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
          "sixteen seventeen eighteen nineteen").split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def _say(n: int) -> list[str]:
    """Ways a caption might spell a whole number: "16" -> sixteen; 2029 -> twenty twenty nine."""
    def under_100(k: int) -> str:
        return _SMALL[k] if k < 20 else _TENS[k // 10 - 2] + ("" if k % 10 == 0 else " " + _SMALL[k % 10])
    out = []
    if n < 100:
        out.append(under_100(n))
    elif 1900 <= n <= 2099:
        hi, lo = divmod(n, 100)
        out += [f"{under_100(hi)} {under_100(lo) if lo >= 10 else 'oh ' + _SMALL[lo]}",
                f"two thousand {under_100(lo)}" if n >= 2000 else "",
                f"two thousand and {under_100(lo)}" if n >= 2000 else "",
                f"{under_100(hi)} hundred" if lo == 0 else ""]
    return [x for x in out if x]


def opening_end(meta: dict) -> int:
    """Where a video's teaser could end: its first chapter if that's titled like an intro, else a minute."""
    ch = meta.get("chapters") or []
    if len(ch) >= 2 and any(w in (ch[0].get("title") or "").lower() for w in INTRO_TITLES):
        return min(int(ch[1]["start"]), COLD_OPEN_MAX_SECONDS)
    return COLD_OPEN_SECONDS


def numbers_not_said(claim: str, window: str, skip_years: tuple[int, ...] = ()) -> list[str]:
    """Numbers in a claim that aren't said in the cited part of the transcript (normalised text).

    `skip_years` are left out: readers are asked to date a claim by when the video was published."""
    said = " " + window + " "
    missing = []
    for raw in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", claim):
        digits = raw.replace(",", "")
        if digits.isdigit() and int(digits) in skip_years:
            continue
        forms = [normalise(digits), normalise(raw)]
        if "." not in digits:
            forms += _say(int(digits))
        if not any(f" {f} " in said for f in forms if f):
            missing.append(raw)
    return missing


def _is_list_url(s: str) -> bool:
    from urllib.parse import urlparse

    u = urlparse(s if "://" in s else "https://" + s)
    host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host != "youtube.com":
        return False
    if "list=" in u.query and "v=" not in u.query:
        return True
    return bool(LIST_PATH_RE.match(u.path))


def resolve_sources(sources: list[str] | str, limit: int) -> tuple[list[dict], list[str]]:
    """Turn links, playlist or channel links and `search:<words>` into a list of unique videos."""
    if isinstance(sources, str):
        s = sources.strip()
        items = [s] if s.lower().startswith("search:") else [x for x in re.split(r"[\s,]+", s) if x]
    else:
        items = [x.strip() for x in sources if x and x.strip()]
    if not items:
        raise YtmaxxingError("Give at least one source: video links, a playlist or channel link, "
                             "or search:<words>.")
    limit = max(1, min(int(limit or MAX_VIDEOS), MAX_VIDEOS))
    found: list[dict] = []
    notes: list[str] = []
    for item in items:
        if item.lower().startswith("search:"):
            query = item[7:].strip()
            hits = search_videos(query, limit)
            notes.append(f"YouTube search \"{query}\": {len(hits)} result(s).")
            found += hits
        elif _is_list_url(item):
            hits = list_videos(item, limit)
            notes.append(f"{item}: {len(hits)} video(s).")
            found += hits
        else:
            found.append({"id": video_id(item)})
    rows, seen = [], set()
    for v in found:
        vid = v.get("id")
        if not vid or not ID_RE.match(vid) or vid in seen:
            continue
        seen.add(vid)
        rows.append({"id": vid, "title": v.get("title") or "", "channel": v.get("channel") or "",
                     "duration": v.get("duration"), "date": None})
    if len(rows) > limit:
        notes.append(f"Kept the first {limit} of {len(rows)} videos (limit {limit}).")
        rows = rows[:limit]
    if not rows:
        raise YtmaxxingError("No videos found in those sources.")
    return rows, notes


class Project:
    """One research question and everything gathered for it."""

    def __init__(self, lib: Library, slug: str):
        self.lib = lib
        self.slug = slug
        self.dir = lib.root / "research" / slug
        if not (self.dir / "project.json").exists():
            names = ", ".join(p["slug"] for p in list_projects(lib)) or "none yet"
            raise YtmaxxingError(f"No research project called '{slug}'. Projects: {names}.")
        self.data = json.loads((self.dir / "project.json").read_text(encoding="utf-8"))
        self.sources: list[dict] = json.loads((self.dir / "sources.json").read_text(encoding="utf-8"))

    # ------------------------------------------------------------ create and save

    @classmethod
    def create(cls, lib: Library, question: str, sub_questions: list[str], sources: list[str] | str,
               limit: int = 20, allow_whisper: bool = False) -> tuple["Project", list[str]]:
        question = " ".join((question or "").split())
        if len(question) < 8:
            raise YtmaxxingError("Write the research question as a full sentence.")
        subs = [" ".join(q.split()) for q in (sub_questions or []) if q and q.strip()]
        if not 1 <= len(subs) <= MAX_SUB_QUESTIONS:
            raise YtmaxxingError(f"Give 1 to {MAX_SUB_QUESTIONS} sub-questions (3–7 works best).")
        rows, notes = resolve_sources(sources, limit)
        base = slugify(question, 48)
        slug, n = base, 2
        while (lib.root / "research" / slug).exists():
            slug, n = f"{base}-{n}", n + 1
        d = lib.root / "research" / slug
        (d / "cards").mkdir(parents=True)
        data = {"question": question, "sub_questions": {f"Q{i}": q for i, q in enumerate(subs, 1)},
                "created": _now(), "allow_whisper": bool(allow_whisper),
                "sources_given": sources if isinstance(sources, list) else [sources], "next_sid": 1}
        (d / "project.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        (d / "sources.json").write_text("[]", encoding="utf-8")
        proj = cls(lib, slug)
        proj._append_rows(rows)
        proj.save()
        return proj, notes

    def _append_rows(self, rows: list[dict]) -> list[str]:
        have = {r["id"] for r in self.sources if r["status"] != "dropped"}
        added = []
        for r in rows:
            if r["id"] in have:
                continue
            sid = f"V{self.data['next_sid']:02d}"
            self.data["next_sid"] += 1
            self.sources.append(r | {"sid": sid, "status": "queued", "reason": "", "claims": 0, "parts": None})
            have.add(r["id"])
            added.append(sid)
        return added

    def save(self) -> None:
        (self.dir / "project.json").write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.dir / "sources.json").write_text(json.dumps(self.sources, indent=2, ensure_ascii=False),
                                               encoding="utf-8")
        lines = [f"# {self.data['question']}", "", f"Research started {self.data['created'][:10]} with ytmaxxing.", "",
                 "## Sub-questions", ""]
        lines += [f"- **{k}** {v}" for k, v in self.data["sub_questions"].items()]
        lines += ["", "## Sources", "", "| ID | Video | Channel | Length | Status |", "|---|---|---|---|---|"]
        for r in self.sources:
            title = (r.get("title") or r["id"]).replace("|", "/")
            status = STATUS_WORDS[r["status"]] + (f" ({r['reason']})" if r.get("reason") else "")
            lines.append(f"| {r['sid']} | [{title}]({watch_url(r['id'])}) | {(r.get('channel') or '').replace('|', '/')}"
                         f" | {_hm(r.get('duration'))} | {status} |")
        (self.dir / "brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ sources

    def row(self, sid: str) -> dict:
        sid = sid.strip().upper()
        for r in self.sources:
            if r["sid"] == sid:
                return r
        raise YtmaxxingError(f"No video {sid} in this project. Use research_status to see the IDs.")

    def active(self) -> list[dict]:
        return [r for r in self.sources if r["status"] != "dropped"]

    def edit(self, drop: list[str] | None = None, add: list[str] | None = None, limit: int = 20) -> str:
        out = []
        for sid in drop or []:
            r = self.row(sid)
            r["status"], r["reason"] = "dropped", "removed by the user"
            out.append(f"Dropped {r['sid']}.")
        if add:
            rows, notes = resolve_sources(add, limit)
            room = MAX_VIDEOS - len(self.active())
            if room <= 0:
                raise YtmaxxingError(f"This project already has {MAX_VIDEOS} videos, the most one report handles.")
            added = self._append_rows(rows[:room])
            out += notes + [f"Added {', '.join(added) or 'nothing new'}."]
        self.save()
        return " ".join(out) or "Nothing changed."

    def fetch(self, batch: int = 5) -> str:
        """Fetch the next queued transcripts, pacing new requests and stopping if YouTube blocks."""
        batch = max(1, min(int(batch), 10))
        queued = [r for r in self.sources if r["status"] == "queued"]
        done, skipped, blocked_in_row, hit_network = [], [], 0, False
        stopped = ""
        for r in queued[:batch]:
            cached = bool(self.lib.load_meta(r["id"]) and self.lib.transcript_parts(r["id"]))
            attempts = 0
            while True:
                if not cached and hit_network:
                    _sleep(random.uniform(*PACE_SECONDS))
                hit_network = hit_network or not cached
                try:
                    meta, parts = ensure_video(self.lib, r["id"], allow_whisper=self.data.get("allow_whisper", False))
                    kind = ""
                except YtmaxxingError as e:
                    kind, msg = classify_error(str(e)), str(e)
                except Exception as e:  # noqa: BLE001 - one bad video must not end the batch
                    kind, msg = "error", f"{type(e).__name__}: {e}"
                if kind == "blocked" and attempts == 0:
                    attempts += 1
                    _sleep(BLOCK_WAIT_SECONDS)
                    continue
                break
            if not kind:
                blocked_in_row = 0
                r.update(title=meta["title"], channel=meta["channel"], duration=meta.get("duration"),
                         date=meta.get("upload_date"), parts=len(parts), status="fetched", reason="",
                         transcript=meta.get("source"))
                dup = self._duplicate_of(r)
                if dup:
                    r["status"], r["reason"] = "skipped", f"duplicate of {dup}"
                    skipped.append(f"{r['sid']} ({r['reason']})")
                else:
                    done.append(r["sid"])
            elif kind == "blocked":
                blocked_in_row += 1
                r["reason"] = "YouTube blocked the request; will retry"
                if blocked_in_row >= STOP_AFTER_BLOCKS:
                    stopped = ("YouTube is blocking requests from this network, so I stopped. Progress is saved. "
                               "Try again in an hour, set YTMAXXING_PROXY, or run `ytmaxxing research fetch "
                               f"{self.slug}` later from a terminal.")
                    break
            else:
                why = {"no-captions": "no captions", "unavailable": "video unavailable"}.get(kind, "fetch failed")
                if kind == "error":
                    why += f": {msg.splitlines()[0][:120]}"
                if kind == "no-captions" and not self.data.get("allow_whisper"):
                    why += " (Whisper is off for this project)"
                r["status"], r["reason"] = "skipped", why
                skipped.append(f"{r['sid']} ({why})")
        self.save()
        left = sum(1 for r in self.sources if r["status"] == "queued")
        msg = [f"Fetched {len(done)}: {', '.join(done)}." if done else "Fetched none this time."]
        if skipped:
            msg.append(f"Skipped {len(skipped)}: {'; '.join(skipped)}.")
        if stopped:
            msg.append(stopped)
        elif left:
            msg.append(f"{left} still queued: call research_fetch again.")
        else:
            ready = sum(1 for r in self.sources if r["status"] in ("fetched", "extracted"))
            msg.append(f"All sources fetched; {ready} ready to read. Next: research_brief for each video ID, "
                       "one subagent per video if you can start them.")
        return " ".join(msg)

    def _duplicate_of(self, row: dict) -> str:
        title, dur = normalise(row.get("title") or ""), row.get("duration") or 0
        for other in self.sources:
            if other is row or other["status"] not in ("fetched", "extracted") or not title:
                continue
            od = other.get("duration") or 0
            if normalise(other.get("title") or "") == title and dur and od and abs(dur - od) <= 0.05 * max(dur, od):
                return other["sid"]
        return ""

    # ------------------------------------------------------------ guides

    def _fill(self, name: str, extra: dict[str, str]) -> str:
        from .modes import _read

        text = _read(name)
        values = {"{{PROJECT}}": self.slug, "{{QUESTION}}": self.data["question"],
                  "{{SUBQUESTIONS}}": "\n".join(f"- **{k}** {v}" for k, v in self.data["sub_questions"].items())}
        for key, value in (values | extra).items():
            text = text.replace(key, value)
        return text

    def guide(self) -> str:
        """The main agent's guide for this project."""
        return self._fill("research", {})

    def brief(self, sid: str) -> str:
        """Everything one subagent needs to read one video for this project."""
        r = self.row(sid)
        if r["status"] not in ("fetched", "extracted"):
            raise YtmaxxingError(f"{r['sid']} isn't ready to read (status: {STATUS_WORDS[r['status']]}"
                                 f"{', ' + r['reason'] if r.get('reason') else ''}). Call research_fetch first.")
        return self._fill("research-extract", {
            "{{SID}}": r["sid"], "{{TITLE}}": r.get("title") or r["id"], "{{CHANNEL}}": r.get("channel") or "?",
            "{{DATE}}": r.get("date") or "on an unknown date", "{{PARTS}}": str(r.get("parts") or 1),
            "{{URL}}": watch_url(r["id"])})

    # ------------------------------------------------------------ status

    def status(self) -> str:
        act = self.active()
        read = [r for r in act if r["status"] == "extracted"]
        lines = [f"Research: {self.data['question']}  [{self.slug}]",
                 "Sub-questions: " + " · ".join(f"{k} {v}" for k, v in self.data["sub_questions"].items()),
                 f"Videos: {len(act)} · read {len(read)} · fetched, not read yet "
                 f"{sum(1 for r in act if r['status'] == 'fetched')} · queued "
                 f"{sum(1 for r in act if r['status'] == 'queued')} · skipped "
                 f"{sum(1 for r in act if r['status'] == 'skipped')}",
                 f"Claims checked so far: {sum(r.get('claims') or 0 for r in act)}"]
        t = self.data.get("tally")
        if t:
            lines.append(f"Claims sent to save_claims: {t['sent']} · accepted {t['accepted']} · rejected "
                         f"{t['rejected']} · duplicates ignored {t['duplicates']}"
                         + (f" (rejections are listed in {self.dir / 'rejections.jsonl'})" if t["rejected"] else ""))
        lines.append("")
        for r in self.sources:
            reason = f" ({r['reason']})" if r.get("reason") else ""
            parts = f", {r['parts']} part(s)" if r.get("parts") else ""
            claims = f", {r['claims']} claims" if r.get("claims") else ""
            lines.append(f"{r['sid']}  {STATUS_WORDS[r['status']]:<8} {_hm(r.get('duration')):>12}  "
                         f"{r.get('title') or r['id']} · {r.get('channel') or '?'}{parts}{claims}{reason}")
        if (self.dir / "report.md").exists():
            lines += ["", f"Report: {self.dir / 'report.md'}"]
        return "\n".join(lines)

    # ------------------------------------------------------------ claims

    def card_path(self, sid: str):
        return self.dir / "cards" / f"{sid}.json"

    def load_card(self, sid: str) -> list[dict]:
        p = self.card_path(sid)
        return json.loads(p.read_text(encoding="utf-8"))["claims"] if p.exists() else []

    def all_claims(self) -> dict[str, dict]:
        out = {}
        for r in self.active():
            for c in self.load_card(r["sid"]):
                out[c["id"]] = c | {"sid": r["sid"], "video": r["id"]}
        return out

    def save_claims(self, sid: str, claims: list[dict], replace: bool = False,
                    nothing_relevant: bool = False) -> str:
        r = self.row(sid)
        if r["status"] not in ("fetched", "extracted"):
            raise YtmaxxingError(f"{r['sid']} isn't ready to read (status: {STATUS_WORDS[r['status']]}"
                                 f"{', ' + r['reason'] if r.get('reason') else ''}).")
        if not claims:
            if not nothing_relevant:
                raise YtmaxxingError("Send at least one claim, or nothing_relevant=true if you read the whole "
                                     "video and it says nothing on the question.")
            if not self.load_card(r["sid"]):
                self._write_card(r, [])
            r["status"], r["reason"] = "extracted", "read in full; nothing on the question"
            self.save()
            return f"Marked {r['sid']} as read with nothing on the question."
        d = self.lib.find_video_dir(r["id"])
        if not d or not (d / "transcript.md").exists():
            raise YtmaxxingError(f"The transcript for {r['sid']} is missing. Call research_fetch again.")
        paras = load_paragraphs(d / "transcript.md")
        meta = self.lib.load_meta(r["id"]) or {}
        context = normalise(" ".join([meta.get("title") or "", meta.get("channel") or "",
                                      meta.get("description") or "", " ".join(p.norm for p in paras)]))
        duration = r.get("duration") or meta.get("duration")
        opening = opening_end(meta)
        published = str(meta.get("upload_date") or r.get("date") or "")[:4]
        years = (int(published),) if published.isdigit() else ()
        existing = [] if replace else self.load_card(r["sid"])
        n = max((int(c["id"].split(".")[1]) for c in existing), default=0)
        seen = {(c["q"], c["t"], normalise(c["claim"])) for c in existing}
        qs = self.data["sub_questions"]
        accepted, rejected, dupes, flagged = [], [], 0, []
        log = []
        for k, raw in enumerate(claims, 1):
            raw = raw if isinstance(raw, dict) else dict(raw)
            text = " ".join(str(raw.get("claim") or "").split())
            label = (text[:50] + "…") if len(text) > 50 else text
            q = str(raw.get("q") or "").strip().upper()
            ctype = str(raw.get("type") or "").strip().lower()
            stance = " ".join(str(raw.get("stance") or "").split())
            problem = ""
            if q not in qs:
                problem = f"q must be one of {', '.join(qs)}"
            elif not text:
                problem = "claim is empty"
            elif len(text.split()) > 60:
                problem = "claim is over 60 words; state it in one short sentence"
            elif ctype not in CLAIM_TYPES:
                problem = f"type must be one of {', '.join(CLAIM_TYPES)}"
            elif not stance:
                problem = "stance is empty (a few words naming the position this claim takes)"
            quote = " ".join(str(raw.get("quote") or "").split()).strip("\"“”")
            if not problem:
                c = check(paras, raw.get("t", ""), quote, duration)
                problem = "" if c.ok else c.reason
            if problem:
                rejected.append(f"#{k} \"{label}\": {problem}")
                log.append({"time": _now(), "video": r["sid"], "n": k, "q": q, "claim": text,
                            "t": str(raw.get("t", "")), "quote": quote, "reason": problem})
                continue
            flags = []
            if quote and c.t < opening and (duration or 0) >= COLD_OPEN_MIN_LENGTH:
                later = find_exact(paras, quote, after=opening)
                body = [p for p in paras if p.start >= opening]  # so the teaser can't match again
                again = check(body, later, quote, duration) if later is not None else None
                if again and again.ok:
                    c = again
                else:
                    flags.append("said in the opening, which may be a teaser clip; the words aren't repeated later")
            i = max(j for j, p in enumerate(paras) if p.start <= c.t)
            window = " ".join(p.norm for p in paras[max(0, i - 1):i + 2])
            missing = numbers_not_said(text, window, years)
            if missing:
                flags.append(f"{', '.join(missing)} isn't said at this moment")
            speaker = " ".join(str(raw.get("speaker") or "").split()) or "unknown"
            name = [w for w in normalise(speaker).split() if len(w) >= 3 and w not in GENERIC_SPEAKERS]
            named = None if not name else f" {name[-1]} " in f" {context} "
            key = (q, c.t, normalise(text))
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            n += 1
            claim = {"id": f"{r['sid']}.{n}", "q": q, "claim": text, "speaker": speaker,
                     "type": ctype, "stance": stance[:80], "t": c.t, "at": c.at if c.at is not None else c.t,
                     "cited_t": parse_time(raw.get("t")), "quote": quote, "check": c.status}
            if named is False:
                claim["speaker_inferred"] = True
            if flags:
                claim["flags"] = flags
                flagged.append(f"{claim['id']}: {'; '.join(flags)}")
            accepted.append(claim)
        card = existing + accepted
        self._write_card(r, card)
        if log:
            with (self.dir / "rejections.jsonl").open("a", encoding="utf-8") as f:
                f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in log)
        tally = self.data.setdefault("tally", {"sent": 0, "accepted": 0, "rejected": 0, "duplicates": 0})
        tally["sent"] += len(claims)
        tally["accepted"] += len(accepted)
        tally["rejected"] += len(rejected)
        tally["duplicates"] += dupes
        r["rejected"] = (r.get("rejected") or 0) + len(rejected)
        r["status"], r["claims"] = ("extracted" if card else "fetched"), len(card)
        if card:
            r["reason"] = ""
        self.save()
        by = {s: sum(1 for c in accepted if c["check"] == s) for s in ("quote", "quote-close", "time")}
        msg = (f"Saved {len(accepted)} claim(s) for {r['sid']} ({by['quote']} exact quote, "
               f"{by['quote-close']} close match, {by['time']} time only); {len(card)} in total. "
               f"This call: {len(accepted)} accepted, {len(rejected)} rejected.")
        if dupes:
            msg += f" Ignored {dupes} duplicate(s)."
        if flagged:
            msg += ("\nSaved, but check these (send a corrected claim with replace=false if one is wrong):\n"
                    + "\n".join(flagged))
        if rejected:
            msg += (f"\nRejected {len(rejected)}. Fix and send just these again (copy the words exactly from "
                    "the transcript, and use the time of the paragraph they're in):\n" + "\n".join(rejected))
        return msg

    def _write_card(self, r: dict, card: list[dict]) -> None:
        self.card_path(r["sid"]).write_text(json.dumps({"sid": r["sid"], "id": r["id"], "claims": card},
                                                       indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [f"# {r['sid']} · {r.get('title') or r['id']}", "",
                 f"{r.get('channel') or ''} · {watch_url(r['id'])} · research: {self.data['question']}", "",
                 "| ID | Q | Speaker | Type | Stance | Claim | Quote | Moment | Check |",
                 "|---|---|---|---|---|---|---|---|---|"]
        for c in card:
            cells = [c["id"], c["q"], c["speaker"], c["type"], c["stance"], c["claim"],
                     f"“{c['quote']}”" if c["quote"] else "",
                     f"[{timestamp(self._at(c))}]({watch_url(r['id'], self._at(c))})",
                     c["check"] + "".join(f"; {x}" for x in c.get("flags", []))]
            lines.append("| " + " | ".join(str(x).replace("|", "/") for x in cells) + " |")
        (self.dir / "cards" / f"{r['sid']}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def claims_text(self, q: str = "", offset: int = 0, limit: int = 300) -> str:
        allc = list(self.all_claims().values())
        if q:
            q = q.strip().upper()
            if q not in self.data["sub_questions"]:
                raise YtmaxxingError(f"Unknown sub-question {q}. Use one of: {', '.join(self.data['sub_questions'])}.")
            allc = [c for c in allc if c["q"] == q]
        page = allc[offset:offset + limit]
        head = (f"{len(allc)} checked claim(s){' for ' + q if q else ''}, showing {offset + 1 if page else 0}–"
                f"{offset + len(page)}. Columns: ID | Q | speaker | type | stance | claim | quote")
        lines = [head] + [f"{c['id']} | {c['q']} | {c['speaker']} | {c['type']} | {c['stance']} | {c['claim']}"
                          + (f" | “{c['quote']}”" if c["quote"] else "") for c in page]
        if offset + len(page) < len(allc):
            lines.append(f"(More: research_claims(project, q='{q}', offset={offset + len(page)}).)")
        return "\n".join(lines)

    # ------------------------------------------------------------ report

    def save_report(self, answer: str, positions: list[dict], notes: str = "", gaps: str = "") -> str:
        claims = self.all_claims()
        if not claims:
            raise YtmaxxingError("No checked claims yet. Read the videos and save_claims first.")
        qs = self.data["sub_questions"]
        errors: list[str] = []
        norm: list[dict] = []
        for i, p in enumerate(positions or [], 1):
            p = p if isinstance(p, dict) else dict(p)
            q = str(p.get("q") or "").strip().upper()
            kind = str(p.get("kind") or "").strip().lower()
            sides = [s if isinstance(s, dict) else dict(s) for s in (p.get("sides") or [])]
            if not sides and p.get("claims"):
                sides = [{"label": p.get("label") or "", "claims": p.get("claims")}]
            where = f"position {i}"
            if q not in qs:
                errors.append(f"{where}: q must be one of {', '.join(qs)}")
                continue
            if kind not in ("agree", "contradict"):
                errors.append(f"{where}: kind must be agree or contradict")
                continue
            clean = []
            for s in sides:
                ids = [x.strip().upper() for x in (s.get("claims") or []) if str(x).strip()]
                unknown = [x for x in ids if x not in claims]
                if unknown:
                    errors.append(f"{where}: unknown claim ID(s) {', '.join(unknown)}")
                ids = [x for x in ids if x in claims]
                if ids:
                    clean.append({"label": " ".join(str(s.get("label") or "").split()), "claims": ids})
            if kind == "agree":
                if len(clean) != 1:
                    errors.append(f"{where}: an agreement has one side with its claim IDs")
                elif len({claims[x]["sid"] for x in clean[0]["claims"]}) < 2:
                    errors.append(f"{where}: an agreement needs claims from at least 2 videos; put a "
                                  "single-video point in notes instead")
            elif len(clean) < 2:
                errors.append(f"{where}: a contradiction needs at least 2 sides, each with claim IDs")
            norm.append({"q": q, "kind": kind, "label": " ".join(str(p.get("label") or "").split()),
                         "sides": clean})
        if not norm and not errors:
            errors.append("Send at least one position (agree or contradict).")
        texts = {"answer": answer or "", "notes": notes or "", "gaps": gaps or ""}
        for name, text in texts.items():
            unknown = sorted({x for x in CLAIM_ID_RE.findall(text) if x not in claims})
            if unknown:
                errors.append(f"{name}: unknown claim ID(s) {', '.join(unknown)}")
        if not texts["answer"].strip():
            errors.append("answer is empty")
        if errors:
            raise YtmaxxingError("The report wasn't saved. Fix these and call save_report again:\n- "
                                 + "\n- ".join(errors))
        (self.dir / "report.src.json").write_text(json.dumps(
            {"answer": answer, "positions": norm, "notes": notes, "gaps": gaps, "saved": _now()},
            indent=2, ensure_ascii=False), encoding="utf-8")
        md = self._render(texts, norm, claims)
        path = self.dir / "report.md"
        path.write_text(md, encoding="utf-8")
        self.lib.update_index()
        agree = sum(1 for p in norm if p["kind"] == "agree")
        msg = (f"Saved the report: {path}\n{self._coverage_line()} {_n(agree, 'agreement')}, "
               f"{_n(len(norm) - agree, 'contradiction')}.")
        overlaps = [w for p in norm if p["kind"] == "contradict" for w in self._overlaps(p["sides"], claims)]
        if overlaps:
            msg += "\nThe report flags these; check each is a real split:\n" + "\n".join(f"- {w}" for w in overlaps)
        return msg

    @staticmethod
    def _at(c: dict) -> int:
        return c.get("at", c["t"])

    @staticmethod
    def _who(c: dict) -> str:
        return c["speaker"] + (" (name inferred)" if c.get("speaker_inferred") else "")

    def _cite(self, c: dict) -> str:
        return f"[{self._who(c)}, {timestamp(self._at(c))}]({watch_url(c['video'], self._at(c))})"

    def _overlaps(self, sides: list[dict], claims: dict) -> list[str]:
        """Videos that appear on more than one side of a contradiction, and whether it's one speaker."""
        out = []
        by_video: dict[str, list[tuple[int, str]]] = {}
        for i, s in enumerate(sides):
            for x in s["claims"]:
                by_video.setdefault(claims[x]["sid"], []).append((i, claims[x]["speaker"]))
        for sid, hits in sorted(by_video.items()):
            if len({i for i, _ in hits}) < 2:
                continue
            per_side = {i: sorted({sp for j, sp in hits if j == i}) for i in sorted({i for i, _ in hits})}
            names = [{normalise(sp) for sp in v} for v in per_side.values()]
            shared = set.intersection(*names) if names else set()
            where = "; ".join(f"Side {chr(65 + i)}: {', '.join(v)}" for i, v in per_side.items())
            if shared:
                out.append(f"{sid} has the same speaker on more than one side ({where}). Check the claims "
                           "really disagree.")
            else:
                out.append(f"{sid} is on more than one side through different speakers ({where}), so its "
                           "video counts once on each side.")
        return out

    def _expand(self, text: str, claims: dict) -> str:
        def group(m):
            ids = [x.strip() for x in re.split(r"[,;]", m.group(1))]
            return "(" + "; ".join(self._cite(claims[x]) for x in ids) + ")"
        text = REF_GROUP_RE.sub(group, text)
        return CLAIM_ID_RE.sub(lambda m: "(" + self._cite(claims[m.group(0)]) + ")", text)

    def _coverage_line(self) -> str:
        act = self.active()
        read = [r for r in act if r["status"] == "extracted"]
        hours = _hm(sum(r.get("duration") or 0 for r in read))
        line = f"Read {len(read)} of {len(act)} videos ({hours} of video)."
        empty = [r["sid"] for r in read if not r.get("claims")]
        if empty:
            line += f" Read but nothing on the question: {', '.join(empty)}."
        missed = [r for r in act if r["status"] != "extracted"]
        if missed:
            line += " Not read: " + "; ".join(
                f"{r['sid']} ({r['reason'] or STATUS_WORDS[r['status']]})" for r in missed) + "."
        t = self.data.get("tally")
        if t:
            line += (f" Readers sent {_n(t['sent'], 'claim')} to the check: {t['accepted']} accepted, "
                     f"{t['rejected']} rejected (a rejected claim can be fixed and sent again).")
        return line

    def _side_lines(self, ids: list[str], claims: dict, show: int = 6) -> list[str]:
        out = []
        for x in ids[:show]:
            c = claims[x]
            quote = f" “{c['quote']}”" if c["quote"] else ""
            close = " (close match: captions spell a name differently)" if c["check"] == "quote-close" else ""
            flags = "".join(f" *Check: {f}.*" for f in c.get("flags", []))
            out.append(f"- **{c['sid']} · {self._who(c)}:** {c['claim']}{quote}{close} "
                       f"([{timestamp(self._at(c))}]({watch_url(c['video'], self._at(c))})){flags}")
        if len(ids) > show:
            out.append("- Also: " + "; ".join(
                f"{x} {self._cite(claims[x])}{' (check: ' + '; '.join(claims[x]['flags']) + ')' if claims[x].get('flags') else ''}"
                for x in ids[show:]))
        return out

    def _side_head(self, label: str, ids: list[str], claims: dict, total_read: int) -> str:
        vids = sorted({claims[x]["sid"] for x in ids})
        speakers = {(claims[x]["sid"], normalise(claims[x]["speaker"])) for x in ids}
        hard = sum(1 for x in ids if claims[x]["type"] in ("shown", "measured"))
        soft = len(ids) - hard
        evidence = ", ".join(s for s in (f"{hard} shown or measured" if hard else "",
                                         f"{soft} belief or story" if soft else "") if s)
        return (f"**{label or 'Position'}** · {len(vids)} of {total_read} videos ({', '.join(vids)}) · "
                f"{_n(len(speakers), 'speaker')} · {_n(len(ids), 'claim')}: {evidence}")

    @staticmethod
    def _flag_line(claims: dict) -> list[str]:
        nums = sum(1 for c in claims.values() if any("isn't said" in f for f in c.get("flags", [])))
        opening = sum(1 for c in claims.values() if any("teaser clip" in f for f in c.get("flags", [])))
        inferred = len({(c["sid"], c["speaker"]) for c in claims.values() if c.get("speaker_inferred")})
        def verb(n: int, one: str, many: str) -> str:
            return one if n == 1 else many
        parts = [x for x in (
            f"{_n(nums, 'claim')} {verb(nums, 'gives', 'give')} a number not said at the cited moment" if nums else "",
            f"{_n(opening, 'claim')} {verb(opening, 'comes', 'come')} from a video's opening, which may be a "
            "teaser clip" if opening else "",
            f"{_n(inferred, 'speaker name')} {verb(inferred, 'is', 'are')} not said in the video, its title or "
            "description" if inferred else "") if x]
        return ["Flagged for a second look: " + "; ".join(parts) + "."] if parts else []

    def _render(self, texts: dict, positions: list[dict], claims: dict) -> str:
        qs = self.data["sub_questions"]
        act = self.active()
        total_read = sum(1 for r in act if r["status"] == "extracted")
        checks = {s: sum(1 for c in claims.values() if c["check"] == s) for s in ("quote", "quote-close", "time")}
        out = [f"# {self.data['question']}", "",
               f"> Research report · {datetime.now(timezone.utc):%Y-%m-%d} · made with "
               "[ytmaxxing](https://github.com/Oal36ar/ytmaxxing). Every citation below was checked by code "
               "against the video's transcript.", "",
               "## Answer", "", self._expand(texts["answer"].strip(), claims), "",
               "## Coverage", "", self._coverage_line(),
               f"Claims: {len(claims)} checked ({_n(checks['quote'], 'exact quote')}, "
               f"{_n(checks['quote-close'], 'close match', 'close matches')} where captions spell a name differently, "
               f"{checks['time']} checked by time only).", *self._flag_line(claims), "",
               "## Sub-questions", ""]
        out += [f"- **{k}** {v}" for k, v in qs.items()]
        for kind, title in (("agree", "Where they agree"), ("contradict", "Where they contradict each other")):
            out += ["", f"## {title}", ""]
            items = [p for p in positions if p["kind"] == kind]
            if not items:
                out.append("None found." if kind == "agree" else "No direct contradictions found.")
                continue
            for q in qs:
                group = [p for p in items if p["q"] == q]
                if not group:
                    continue
                out += [f"### {q} · {qs[q]}", ""]
                for n, p in enumerate(group, 1):
                    if kind == "contradict":
                        out += [f"#### {p.get('label') or f'Contradiction {n}'}", ""]
                    for i, s in enumerate(p["sides"]):
                        label = s["label"] if kind == "agree" else f"Side {chr(65 + i)}: {s['label'] or 'Position'}"
                        out += [self._side_head(label, s["claims"], claims, total_read)]
                        out += self._side_lines(s["claims"], claims) + [""]
                    if kind == "contradict":
                        out += [f"*Note: {w}*" for w in self._overlaps(p["sides"], claims)]
                        if out[-1] != "":
                            out.append("")
        out += ["## Who said what", "", "| Speaker | Video | " + " | ".join(qs) + " |",
                "|---|---|" + "---|" * len(qs)]
        grid: dict[tuple[str, str], dict[str, list[str]]] = {}
        for c in claims.values():
            cell = grid.setdefault((self._who(c), c["sid"]), {}).setdefault(c["q"], [])
            if c["stance"] not in cell:
                cell.append(c["stance"])
        for (speaker, sid), cells in sorted(grid.items(), key=lambda kv: (kv[0][1], kv[0][0]))[:60]:
            row = [speaker, sid] + ["; ".join(cells.get(q, [])[:2])[:60] or "—" for q in qs]
            out.append("| " + " | ".join(x.replace("|", "/") for x in row) + " |")
        unanswered = [q for q in qs if not any(c["q"] == q for c in claims.values())]
        if texts["notes"].strip():
            out += ["", "## Evidence notes", "", self._expand(texts["notes"].strip(), claims)]
        if texts["gaps"].strip() or unanswered:
            out += ["", "## Gaps", ""]
            if texts["gaps"].strip():
                out.append(self._expand(texts["gaps"].strip(), claims))
            if unanswered:
                out.append("No video made a checkable claim on: "
                           + "; ".join(f"{q} ({qs[q]})" for q in unanswered) + ".")
        out += ["", "## Sources", "", "| ID | Video | Channel | Published | Length | Status |",
                "|---|---|---|---|---|---|"]
        for r in act:
            title = (r.get("title") or r["id"]).replace("|", "/")
            status = STATUS_WORDS[r["status"]] + (f" ({r['reason']})" if r.get("reason") else "")
            out.append(f"| {r['sid']} | [{title}]({watch_url(r['id'])}) | {(r.get('channel') or '?').replace('|', '/')} | "
                       f"{r.get('date') or '?'} | {_hm(r.get('duration'))} | {status} |")
        out += ["", "Limits: a checked quote proves those words were said at that moment. It doesn't prove the "
                "paraphrase next to it is fair, and captions don't record who is speaking, so speakers come from "
                "context."]
        return "\n".join(out) + "\n"


def list_projects(lib: Library) -> list[dict]:
    root = lib.root / "research"
    out = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        p = d / "project.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        srcs = json.loads((d / "sources.json").read_text(encoding="utf-8")) if (d / "sources.json").exists() else []
        out.append({"slug": d.name, "question": data.get("question", ""), "created": data.get("created", "")[:10],
                    "videos": sum(1 for r in srcs if r.get("status") != "dropped"),
                    "read": sum(1 for r in srcs if r.get("status") == "extracted"),
                    "report": (d / "report.md").exists()})
    return out
