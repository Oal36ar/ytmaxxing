import json

import pytest

from ytmaxxing import research
from ytmaxxing.library import Library
from ytmaxxing.research import Project, _is_list_url, list_projects, resolve_sources
from ytmaxxing.youtube import Line, Transcript, Video, YtmaxxingError, classify_error

A, B, C, D = "AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "DDDDDDDDDDD"

TALKS = {
    A: ("Forecaster interview", "Pod One", [
        (0, "Welcome to the show, today we talk about the future of work."),
        (60, "I think superhuman AI arrives before twenty thirty, probably by the end of the decade."),
        (130, "Most office jobs will be automated within ten years of that."),
    ]),
    B: ("Sceptic lecture", "Uni Talks", [
        (0, "Thanks for coming to this lecture."),
        (60, "Human level AI is decades away and the current methods will hit a wall."),
        (130, "Jobs will change but new kinds of work will appear, as they always have."),
    ]),
    C: ("Founder chat", "Pod Two", [
        (0, "Great to be here."),
        (60, "We will see systems smarter than people before twenty thirty, I am fairly confident."),
        (130, "Our own data shows support tickets fell forty percent after we deployed agents."),
    ]),
}


@pytest.fixture
def lib(tmp_path, monkeypatch):
    lib = Library(tmp_path)
    for vid, (title, channel, lines) in TALKS.items():
        video = Video(id=vid, title=title, channel=channel, upload_date="2026-01-01", duration=200)
        lib.save_transcript(video, Transcript([Line(float(s), t) for s, t in lines], "en", "captions"))
    monkeypatch.setattr(research, "_sleep", lambda s: None)
    return lib


def _project(lib, sources=(A, B, C)):
    proj, _ = Project.create(lib, "How soon will AI match human experts, and what happens to jobs?",
                             ["When does AI match top experts?", "What happens to jobs?", "What is the evidence?"],
                             list(sources))
    return proj


def _read_all(proj):
    proj.fetch()
    proj.save_claims("V01", [
        {"q": "Q1", "claim": "Superhuman AI before 2030", "speaker": "Guest", "type": "belief",
         "stance": "before 2030", "t": "01:00", "quote": "probably by the end of the decade"},
        {"q": "Q2", "claim": "Most office jobs automated within ten years", "speaker": "Guest", "type": "belief",
         "stance": "mass automation", "t": 130, "quote": "most office jobs will be automated"}])
    proj.save_claims("V02", [
        {"q": "Q1", "claim": "Human-level AI is decades away", "speaker": "Lecturer", "type": "belief",
         "stance": "decades away", "t": 60, "quote": "human level AI is decades away"},
        {"q": "Q2", "claim": "New work will appear", "speaker": "Lecturer", "type": "belief",
         "stance": "jobs change", "t": 130, "quote": "new kinds of work will appear"}])
    proj.save_claims("V03", [
        {"q": "Q1", "claim": "Smarter-than-human systems before 2030", "speaker": "Founder", "type": "belief",
         "stance": "before 2030", "t": 60, "quote": "smarter than people before twenty thirty"},
        {"q": "Q3", "claim": "Support tickets fell 40% after agents", "speaker": "Founder", "type": "measured",
         "stance": "automation cuts work", "t": 130, "quote": "support tickets fell forty percent"}])


# ---------------------------------------------------------------- sources

def test_is_list_url():
    assert _is_list_url("https://www.youtube.com/playlist?list=PL123")
    assert _is_list_url("https://www.youtube.com/@lexfridman")
    assert _is_list_url("youtube.com/@lexfridman/videos")
    assert not _is_list_url(f"https://www.youtube.com/watch?v={A}&list=PL123")
    assert not _is_list_url(f"https://youtu.be/{A}")


def test_resolve_sources_mixes_links_lists_and_search(monkeypatch):
    monkeypatch.setattr(research, "search_videos", lambda q, n: [{"id": B, "title": "b"}, {"id": C, "title": "c"}])
    monkeypatch.setattr(research, "list_videos", lambda u, n: [{"id": C, "title": "c"}, {"id": D, "title": "d"}])
    rows, notes = resolve_sources([f"https://youtu.be/{A}", "search:ai timelines",
                                   "https://www.youtube.com/playlist?list=PL1"], limit=20)
    assert [r["id"] for r in rows] == [A, B, C, D]  # duplicates dropped, order kept
    assert any("search" in n for n in notes)
    rows, notes = resolve_sources([A, B, C, D], limit=2)
    assert len(rows) == 2 and any("Kept the first 2" in n for n in notes)


def test_resolve_sources_needs_something():
    with pytest.raises(YtmaxxingError):
        resolve_sources([], 10)


def test_create_numbers_videos_and_writes_files(lib):
    proj = _project(lib)
    assert [r["sid"] for r in proj.sources] == ["V01", "V02", "V03"]
    assert (proj.dir / "brief.md").read_text().count("| V0") == 3
    assert list(proj.data["sub_questions"]) == ["Q1", "Q2", "Q3"]
    again = _project(lib)
    assert again.slug == proj.slug + "-2"


def test_create_checks_question_and_sub_questions(lib):
    with pytest.raises(YtmaxxingError):
        Project.create(lib, "AI?", ["x"], [A])
    with pytest.raises(YtmaxxingError):
        Project.create(lib, "A proper research question here", [f"q{i}" for i in range(9)], [A])


def test_edit_drops_and_adds(lib):
    proj = _project(lib, (A, B))
    out = proj.edit(drop=["V02"], add=[C])
    assert "Dropped V02" in out and "V03" in out
    assert [r["sid"] for r in proj.active()] == ["V01", "V03"]


# ---------------------------------------------------------------- fetching

def test_fetch_uses_cache_and_reports_progress(lib):
    proj = _project(lib)
    msg = proj.fetch(batch=2)
    assert "Fetched 2" in msg and "1 still queued" in msg
    msg = proj.fetch()
    assert "All sources fetched" in msg
    assert {r["status"] for r in proj.sources} == {"fetched"}
    assert proj.row("V01")["title"] == "Forecaster interview"


def test_fetch_sorts_failures_and_stops_when_blocked(lib, monkeypatch):
    proj = _project(lib, (D, "EEEEEEEEEEE", "FFFFFFFFFFF", "GGGGGGGGGGG"))
    waits = []
    monkeypatch.setattr(research, "_sleep", waits.append)
    errors = {D: "Couldn't get captions (TranscriptsDisabled: off). Install local transcription",
              "EEEEEEEEEEE": "Couldn't get captions (IpBlocked: x). YouTube is blocking requests",
              "FFFFFFFFFFF": "Couldn't get captions (RequestBlocked: 429). YouTube is blocking requests"}

    def fake(lib_, vid, **kw):
        raise YtmaxxingError(errors.get(vid, "boom"))

    monkeypatch.setattr(research, "ensure_video", fake)
    msg = proj.fetch(batch=5)
    assert proj.row("V01")["status"] == "skipped" and "no captions" in proj.row("V01")["reason"]
    assert proj.row("V02")["status"] == "queued" and proj.row("V03")["status"] == "queued"
    assert proj.row("V04")["status"] == "queued"  # never tried: the batch stopped
    assert "blocking" in msg and "Progress is saved" in msg
    assert research.BLOCK_WAIT_SECONDS in waits  # waited once before retrying each blocked video


def test_duplicate_reupload_is_skipped(lib, monkeypatch):
    lib.save_transcript(Video(id=D, title="Forecaster Interview!", channel="Mirror", duration=205),
                        Transcript([Line(0.0, "copy")], "en", "captions"))
    proj = _project(lib, (A, D))
    proj.fetch()
    assert proj.row("V02")["status"] == "skipped" and "duplicate of V01" in proj.row("V02")["reason"]


@pytest.mark.parametrize("message,kind", [
    ("Couldn't get captions (TranscriptsDisabled: x)", "no-captions"),
    ("Couldn't get captions (IpBlocked: x). YouTube is blocking requests", "blocked"),
    ("Sign in to confirm you're not a bot", "blocked"),
    ("Couldn't get captions (VideoUnavailable: x)", "unavailable"),
    ("Couldn't get captions (CouldNotRetrieveTranscript: language page)", "error"),
])
def test_classify_error(message, kind):
    assert classify_error(message) == kind


# ---------------------------------------------------------------- claims

def test_save_claims_checks_each_claim(lib):
    proj = _project(lib)
    proj.fetch()
    msg = proj.save_claims("V01", [
        {"q": "Q1", "claim": "Superhuman AI before 2030", "speaker": "Guest", "type": "belief",
         "stance": "before 2030", "t": "01:05", "quote": "probably by the end of the decade"},
        {"q": "Q1", "claim": "Invented", "speaker": "Guest", "type": "belief", "stance": "x",
         "t": 60, "quote": "robots will replace every judge"},
        {"q": "Q9", "claim": "Wrong sub-question", "type": "belief", "stance": "x", "t": 60},
        {"q": "Q2", "claim": "Bad type", "type": "opinion", "stance": "x", "t": 60},
        {"q": "Q2", "claim": "Time only", "speaker": "Guest", "type": "belief", "stance": "automation", "t": 140},
    ])
    assert "Saved 2 claim(s)" in msg and "Rejected 3" in msg
    card = proj.load_card("V01")
    assert [c["id"] for c in card] == ["V01.1", "V01.2"]
    assert card[0]["check"] == "quote" and card[0]["t"] == 60 and card[0]["cited_t"] == 65
    assert card[1]["check"] == "time"
    assert proj.row("V01")["status"] == "extracted" and proj.row("V01")["claims"] == 2
    more = proj.save_claims("V01", [{"q": "Q2", "claim": "Office jobs automated", "type": "belief",
                                      "stance": "automation", "t": 130, "quote": "most office jobs will be automated"}])
    assert "1 claim(s)" in more and proj.load_card("V01")[-1]["id"] == "V01.3"
    assert (proj.dir / "cards" / "V01.md").exists()


def test_save_claims_needs_a_fetched_video(lib):
    proj = _project(lib)
    with pytest.raises(YtmaxxingError):
        proj.save_claims("V01", [{"q": "Q1", "claim": "x", "type": "belief", "stance": "x", "t": 1}])


def test_claims_text_filters_by_sub_question(lib):
    proj = _project(lib)
    _read_all(proj)
    text = proj.claims_text("Q1")
    assert text.startswith("3 checked claim(s) for Q1")
    assert "V02.1 | Q1 | Lecturer" in text and "Q2" not in text.split("\n", 1)[1]


# ---------------------------------------------------------------- report

POSITIONS = [
    {"q": "Q1", "kind": "agree", "label": "Superhuman AI before 2030", "claims": ["V01.1", "V03.1"]},
    {"q": "Q1", "kind": "contradict", "sides": [
        {"label": "Before 2030", "claims": ["V01.1", "V03.1"]},
        {"label": "Decades away", "claims": ["V02.1"]}]},
    {"q": "Q2", "kind": "contradict", "sides": [
        {"label": "Mass automation", "claims": ["V01.2"]},
        {"label": "New work appears", "claims": ["V02.2"]}]},
]


def test_report_counts_and_links_are_done_by_code(lib):
    proj = _project(lib)
    _read_all(proj)
    msg = proj.save_report("Two of three speakers expect superhuman AI before 2030 {V01.1, V03.1}; "
                           "the lecturer disagrees V02.1.", POSITIONS,
                           notes="Only one measured number: V03.2.", gaps="Nobody gave a date range.")
    assert "Read 3 of 3 videos" in msg and "1 agreement, 2 contradictions" in msg
    md = (proj.dir / "report.md").read_text()
    assert "2 of 3 videos (V01, V03)" in md
    assert f"[Guest, 01:00](https://youtu.be/{A}?t=60)" in md
    assert f"[Lecturer, 01:00](https://youtu.be/{B}?t=60)" in md  # bare ID expanded too
    assert "V01.1" not in md.split("## Coverage")[0]  # IDs in the answer became links
    assert "Side A: Before 2030" in md and "Side B: Decades away" in md
    assert "1 shown or measured" not in md.split("## Who said what")[0].split("### Q1")[1]
    assert "| Founder | V03 |" in md
    assert "6 checked (6 exact quotes" in md
    assert json.loads((proj.dir / "report.src.json").read_text())["positions"][0]["kind"] == "agree"
    assert "## Research" in (lib.root / "index.md").read_text()


def test_report_rejects_invented_ids_and_weak_agreement(lib):
    proj = _project(lib)
    _read_all(proj)
    bad = [{"q": "Q1", "kind": "agree", "label": "x", "claims": ["V01.1"]},
           {"q": "Q2", "kind": "contradict", "sides": [{"label": "a", "claims": ["V01.2", "V09.9"]}]},
           {"q": "Q7", "kind": "agree", "claims": ["V01.1", "V02.1"]}]
    with pytest.raises(YtmaxxingError) as e:
        proj.save_report("See V05.1.", bad)
    text = str(e.value)
    assert "at least 2 videos" in text and "V09.9" in text and "at least 2 sides" in text
    assert "q must be one of" in text and "answer: unknown claim ID(s) V05.1" in text
    assert not (proj.dir / "report.md").exists()


def test_report_lists_unread_videos_and_unanswered_questions(lib, monkeypatch):
    proj, _ = Project.create(lib, "How soon will AI match human experts?", ["When?", "Who is building it?"],
                             [A, B, D])
    real = research.ensure_video

    def fake(lib_, vid, **kw):
        if vid == D:
            raise YtmaxxingError("Couldn't get captions (TranscriptsDisabled: x)")
        return real(lib_, vid, **kw)

    monkeypatch.setattr(research, "ensure_video", fake)
    proj.fetch()
    proj.save_claims("V01", [{"q": "Q1", "claim": "Before 2030", "speaker": "Guest", "type": "belief",
                               "stance": "before 2030", "t": 60, "quote": "probably by the end of the decade"}])
    proj.save_claims("V02", [{"q": "Q1", "claim": "Decades away", "speaker": "Lecturer", "type": "belief",
                               "stance": "decades", "t": 60, "quote": "human level AI is decades away"}])
    proj.save_report("They disagree.", [{"q": "Q1", "kind": "contradict", "sides": [
        {"label": "Soon", "claims": ["V01.1"]}, {"label": "Decades", "claims": ["V02.1"]}]}])
    md = (proj.dir / "report.md").read_text()
    assert "Read 2 of 3 videos" in md and "V03 (no captions" in md
    assert "No video made a checkable claim on: Q2" in md
    assert "None found." in md


def test_list_projects(lib):
    proj = _project(lib)
    _read_all(proj)
    [p] = list_projects(lib)
    assert p["slug"] == proj.slug and p["read"] == 3 and p["videos"] == 3 and not p["report"]


def test_guides_are_filled(lib):
    proj = _project(lib)
    proj.fetch()
    g = proj.guide()
    assert "{{" not in g and proj.slug in g and "**Q2** What happens to jobs?" in g
    b = proj.brief("V02")
    assert "{{" not in b and f"https://youtu.be/{B}" in b and "V02 · Sceptic lecture" in b
    assert 'save_claims(project="' in b
    with pytest.raises(YtmaxxingError):
        _project(lib, (D,)).brief("V01")


def test_nothing_relevant_counts_as_read(lib):
    proj = _project(lib, (A, B))
    proj.fetch()
    with pytest.raises(YtmaxxingError):
        proj.save_claims("V02", [])
    assert "nothing on the question" in proj.save_claims("V02", [], nothing_relevant=True)
    assert proj.row("V02")["status"] == "extracted"
    assert "Read but nothing on the question: V02" in proj._coverage_line()


def test_cli_research_list_and_status(lib, monkeypatch, capsys):
    from ytmaxxing.cli import main

    monkeypatch.setenv("YTMAXXING_HOME", str(lib.root))
    proj = _project(lib)
    assert main(["research", "fetch", proj.slug]) == 0
    assert "All sources fetched" in capsys.readouterr().out
    assert main(["research", "list"]) == 0
    assert proj.slug in capsys.readouterr().out
    assert main(["research", "status", proj.slug]) == 0
    assert "V03  fetched" in capsys.readouterr().out


# ---------------------------------------------------------------- fixes from the 2026-11-26 real run

def test_rejections_are_logged_and_tallied(lib):
    """Run notes problem 1: rejections weren't recorded, so the pass rate came from readers' reports."""
    proj = _project(lib)
    proj.fetch()
    msg = proj.save_claims("V01", [
        {"q": "Q1", "claim": "Superhuman AI before 2030", "speaker": "Guest", "type": "belief",
         "stance": "before 2030", "t": 60, "quote": "probably by the end of the decade"},
        {"q": "Q1", "claim": "Invented", "speaker": "Guest", "type": "belief", "stance": "x",
         "t": 60, "quote": "robots will replace every judge"}])
    assert "1 accepted, 1 rejected" in msg
    proj.save_claims("V01", [{"q": "Q2", "claim": "Office jobs automated", "type": "belief", "stance": "x",
                              "t": 130, "quote": "most office jobs will be automated"}])
    tally = json.loads((proj.dir / "project.json").read_text())["tally"]
    assert tally == {"sent": 3, "accepted": 2, "rejected": 1, "duplicates": 0}
    assert "Claims sent to save_claims: 3 · accepted 2 · rejected 1" in proj.status()
    assert proj.row("V01")["rejected"] == 1


def test_rejected_claims_can_be_reviewed(lib):
    """Run notes problem 12: with nothing kept, a wrongly rejected claim could never be reviewed."""
    proj = _project(lib)
    proj.fetch()
    proj.save_claims("V02", [{"q": "Q1", "claim": "Decades away", "speaker": "Lecturer", "type": "belief",
                              "stance": "decades", "t": 60, "quote": "human level AI is a century away"}])
    rows = [json.loads(x) for x in (proj.dir / "rejections.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["video"] == "V02" and rows[0]["quote"] == "human level AI is a century away"
    assert "changes the meaning" in rows[0]["reason"] or "not found" in rows[0]["reason"]


def test_contradictions_get_titles(lib):
    """Run notes problem 3: two contradictions under one sub-question ran into each other."""
    proj = _project(lib)
    _read_all(proj)
    positions = [
        {"q": "Q1", "kind": "contradict", "label": "When does AI match experts?", "sides": [
            {"label": "Before 2030", "claims": ["V01.1", "V03.1"]}, {"label": "Decades", "claims": ["V02.1"]}]},
        {"q": "Q1", "kind": "contradict", "sides": [
            {"label": "Soon", "claims": ["V03.1"]}, {"label": "Later", "claims": ["V02.1"]}]}]
    proj.save_report("Split V01.1 V02.1.", positions)
    md = (proj.dir / "report.md").read_text()
    assert "#### When does AI match experts?" in md and "#### Contradiction 2" in md
    assert md.index("#### When does") < md.index("Side A: Before 2030") < md.index("#### Contradiction 2")


def test_video_on_both_sides_is_flagged_and_speakers_counted(lib):
    """Run notes problem 4: counts were by video, and a video could sit on both sides unnoticed."""
    proj = _project(lib)
    _read_all(proj)
    proj.save_claims("V01", [{"q": "Q2", "claim": "Jobs will change, not vanish", "speaker": "Host",
                              "type": "belief", "stance": "jobs change", "t": 0, "quote": "the future of work"}])
    positions = [{"q": "Q2", "kind": "contradict", "label": "Mass automation?", "sides": [
        {"label": "Yes", "claims": ["V01.2"]}, {"label": "No", "claims": ["V01.3", "V02.2"]}]}]
    msg = proj.save_report("Split V01.2.", positions)
    md = (proj.dir / "report.md").read_text()
    assert "V01 is on more than one side through different speakers" in msg
    assert "*Note: V01 is on more than one side" in md
    assert "2 of 3 videos (V01, V02) · 2 speakers · 2 claims" in md
    same = [{"q": "Q1", "kind": "contradict", "label": "x", "sides": [
        {"label": "a", "claims": ["V01.1"]}, {"label": "b", "claims": ["V01.2", "V02.1"]}]}]
    proj.data["sub_questions"]  # V01.1 (Q1) and V01.2 (Q2) are both the Guest
    msg = proj.save_report("x V01.1.", same)
    assert "V01 has the same speaker on more than one side" in msg


def test_long_sides_keep_every_link(lib):
    """Run notes problem 5: after 6 claims the rest were bare IDs with no link."""
    proj = _project(lib)
    _read_all(proj)
    extra = [{"q": "Q1", "claim": f"Point {i}", "speaker": "Guest", "type": "belief", "stance": "soon",
              "t": t} for i, t in enumerate([0, 60, 130, 0, 60], 1)]
    proj.save_claims("V01", extra)
    ids = ["V01.1", "V03.1"] + [f"V01.{i}" for i in range(3, 8)]
    proj.save_report("Soon V01.1.", [{"q": "Q1", "kind": "agree", "label": "Soon", "claims": ids}])
    md = (proj.dir / "report.md").read_text()
    assert "- Also: V01.7 [Guest, 01:00](https://youtu.be/" in md
    assert "more: V01" not in md


def test_teaser_quote_moves_to_the_interview(lib):
    """Run notes problem 6: two claims cited the 0:00 teaser clip instead of the interview."""
    E = "EEEEEEEEEEE"
    lines = [(0, "large language models are not going to get us to general intelligence"),
             (20, "welcome to the show everyone"), (400, "so here is my view in full, large language "
                                                        "models are not going to get us to general intelligence"),
             (700, "and that is all")]
    video = Video(id=E, title="Long interview", channel="Pod", upload_date="2026-01-01", duration=900)
    lib.save_transcript(video, Transcript([Line(float(s), t) for s, t in lines], "en", "captions"))
    proj = _project(lib, sources=(A, E))
    proj.fetch()
    proj.save_claims("V02", [
        {"q": "Q1", "claim": "LLMs won't reach AGI", "speaker": "Guest", "type": "belief", "stance": "not LLMs",
         "t": 0, "quote": "large language models are not going to get us"},
        {"q": "Q2", "claim": "Welcome", "speaker": "Host", "type": "story", "stance": "x",
         "t": 20, "quote": "welcome to the show everyone"}])
    card = proj.load_card("V02")
    assert card[0]["t"] == 400 and card[0]["cited_t"] == 0 and "flags" not in card[0]
    assert "teaser clip" in card[1]["flags"][0]
    # an intro-titled first chapter sets the window; the interview after it isn't flagged
    from ytmaxxing.research import opening_end
    assert opening_end({"chapters": [{"start": 0, "title": "Intro"}, {"start": 49, "title": "Jobs"}]}) == 49
    assert opening_end({"chapters": [{"start": 0, "title": "AGI"}, {"start": 900, "title": "RL"}]}) == 60
    assert opening_end({"chapters": [{"start": 0, "title": "Coming up"}, {"start": 400, "title": "x"}]}) == 180


def test_number_not_said_at_the_moment_is_flagged(lib):
    """Run notes problem 8: a paraphrase can bring in detail from another moment."""
    proj = _project(lib)
    proj.fetch()
    msg = proj.save_claims("V03", [
        {"q": "Q3", "claim": "Support tickets fell 60% after agents", "speaker": "Founder", "type": "measured",
         "stance": "x", "t": 130, "quote": "support tickets fell forty percent"},
        {"q": "Q3", "claim": "Support tickets fell 40% after agents in 2035", "speaker": "Founder",
         "type": "measured", "stance": "y", "t": 130, "quote": "support tickets fell forty percent"}])
    card = proj.load_card("V03")
    assert card[0]["flags"] == ["60 isn't said at this moment"]
    assert card[1]["flags"] == ["2035 isn't said at this moment"]  # 40% is said as "forty percent"
    assert "V03.1: 60 isn't said" in msg
    proj.save_claims("V01", [{"q": "Q1", "claim": "AI by 2030 (said in 2026), about 1,000 days", "speaker": "Guest",
                              "type": "belief", "stance": "z", "t": 60, "quote": "probably by the end of the decade"}])
    # 2030 is said as "twenty thirty"; 2026 is the upload year, so it's skipped; the comma stays out
    assert proj.load_card("V01")[0]["flags"] == ["1,000 isn't said at this moment"]
    proj.save_report("x V03.1.", [{"q": "Q3", "kind": "agree", "label": "x", "claims": ["V03.1", "V01.1"]}])
    md = (proj.dir / "report.md").read_text()
    assert "*Check: 60 isn't said at this moment.*" in md and "Flagged for a second look: 3 claims give a number" in md


def test_guides_match_the_code(lib):
    """Run notes problem 9: guide said one reader per video, no counts in replies, and 25 vs 30 words."""
    from ytmaxxing.verify import MAX_QUOTE_WORDS, MIN_QUOTE_WORDS
    proj = _project(lib)
    proj.fetch()
    brief, guide = proj.brief("V01"), proj.guide()
    assert f"{MIN_QUOTE_WORDS}–{MAX_QUOTE_WORDS} words" in brief
    assert "accepted and rejected in total" in brief
    assert "a few videos to read one after another" in guide and "rejections.jsonl" in guide


def test_counts_are_pluralised(lib):
    """Run notes problem 10: the report said "1 close matches"."""
    proj = _project(lib)
    _read_all(proj)
    proj.save_claims("V03", [{"q": "Q1", "claim": "Systems smarter than people", "speaker": "Founder",
                              "type": "belief", "stance": "soon", "t": 60,
                              "quote": "We will see Sistems smarter than people"}])
    assert proj.load_card("V03")[-1]["check"] == "quote-close"
    proj.save_report("x V01.1.", POSITIONS)
    md = (proj.dir / "report.md").read_text()
    assert "1 close match where" in md and "1 close matches" not in md and "6 exact quotes" in md


def test_speaker_not_named_in_the_video_is_marked(lib):
    """Run notes problem 11: speaker names come from context, with nothing to show which were inferred."""
    proj = _project(lib)
    proj.fetch()
    proj.save_claims("V01", [
        {"q": "Q1", "claim": "Before 2030", "speaker": "Erik Brynjolfsson", "type": "belief", "stance": "a",
         "t": 60, "quote": "probably by the end of the decade"},
        {"q": "Q2", "claim": "Office jobs", "speaker": "Guest", "type": "belief", "stance": "b",
         "t": 130, "quote": "most office jobs will be automated"},
        {"q": "Q2", "claim": "Future of work", "speaker": "Pod One host", "type": "belief", "stance": "c",
         "t": 0, "quote": "the future of work"}])
    card = proj.load_card("V01")
    assert card[0].get("speaker_inferred") is True
    assert "speaker_inferred" not in card[1] and "speaker_inferred" not in card[2]  # generic; channel name
    proj.save_claims("V02", [{"q": "Q1", "claim": "Decades", "speaker": "Lecturer", "type": "belief",
                              "stance": "d", "t": 60, "quote": "human level AI is decades away"}])
    proj.save_report("x V01.1.", [{"q": "Q1", "kind": "contradict", "label": "When?", "sides": [
        {"label": "Soon", "claims": ["V01.1"]}, {"label": "Later", "claims": ["V02.1"]}]}])
    md = (proj.dir / "report.md").read_text()
    assert "Erik Brynjolfsson (name inferred)" in md
    assert "1 speaker name is not said in the video" in md
